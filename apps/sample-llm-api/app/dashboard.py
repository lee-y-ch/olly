import time
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.alert_storage import AlertStore, Comparator, EvalWindow, MetricKey
from app.alerts import METRIC_CATALOG, AlertEvaluator
from app.config import Settings


router = APIRouter()
settings = Settings.from_env()
alert_store = AlertStore()
alert_evaluator: AlertEvaluator | None = None


def set_alert_evaluator(evaluator: AlertEvaluator) -> None:
    global alert_evaluator
    alert_evaluator = evaluator


class AlertRulePayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    metric: MetricKey
    comparator: Comparator
    threshold: float
    window: EvalWindow = "5m"
    cooldown_seconds: int = Field(300, ge=10, le=86400)
    webhook_url: str = Field(..., min_length=10)

WINDOWS = {
    "15m": 15 * 60,
    "1h": 60 * 60,
    "6h": 6 * 60 * 60,
    "24h": 24 * 60 * 60,
}
STAGE_NAMES = ("retrieve", "llm_call", "postprocess")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    dashboard_path = Path(__file__).parent / "static" / "dashboard.html"
    return HTMLResponse(dashboard_path.read_text(encoding="utf-8"))


@router.get("/chat-ui", response_class=HTMLResponse)
async def chat_ui() -> HTMLResponse:
    chat_ui_path = Path(__file__).parent / "static" / "chat_ui.html"
    return HTMLResponse(chat_ui_path.read_text(encoding="utf-8"))


@router.get("/api/dashboard/summary")
async def dashboard_summary(window: str = Query("1h", pattern="^(15m|1h|6h|24h)$")) -> dict[str, Any]:
    return await collect_dashboard_summary(window)


async def collect_dashboard_summary(window: str = "1h") -> dict[str, Any]:
    if window not in WINDOWS:
        window = "1h"
    async with httpx.AsyncClient(timeout=8.0) as client:
        scalar_queries = {
            "total_requests": f"sum(increase(olly_requests_total[{window}]))",
            "total_tokens": f"sum(increase(olly_tokens_total[{window}]))",
            "estimated_cost_usd": f"sum(increase(olly_cost_usd_total[{window}]))",
            "token_cost_usd": f"sum(increase(olly_token_cost_usd_total[{window}]))",
            "infra_cost_usd": f"sum(increase(olly_infra_cost_usd_total[{window}]))",
            "compute_seconds": f"sum(increase(olly_inference_compute_seconds_total[{window}]))",
            "p95_latency_seconds": (
                "histogram_quantile(0.95, "
                f"sum by (le) (increase(olly_request_duration_seconds_bucket[{window}])))"
            ),
            "avg_latency_seconds": (
                f"sum(increase(olly_request_duration_seconds_sum[{window}])) "
                f"/ clamp_min(sum(increase(olly_request_duration_seconds_count[{window}])), 1)"
            ),
            "error_rate_percent": (
                f"100 * sum(increase(olly_requests_total{{status=\"error\"}}[{window}])) "
                f"/ clamp_min(sum(increase(olly_requests_total[{window}])), 1)"
            ),
            "tokens_per_second": (
                "histogram_quantile(0.5, "
                f"sum by (le) (increase(olly_generation_tokens_per_second_bucket[{window}])))"
            ),
        }
        scalars = {
            key: await _prometheus_scalar(client, query)
            for key, query in scalar_queries.items()
        }
        vectors = {
            "cost_by_feature": await _prometheus_vector(
                client, f"sum by (feature) (increase(olly_cost_usd_total[{window}]))", "feature"
            ),
            "cost_by_model": await _prometheus_vector(
                client, f"sum by (model) (increase(olly_cost_usd_total[{window}]))", "model"
            ),
            "tokens_by_feature": await _prometheus_vector(
                client, f"sum by (feature) (increase(olly_tokens_total[{window}]))", "feature"
            ),
            "requests_by_scenario": await _prometheus_vector(
                client, f"sum by (scenario) (increase(olly_requests_total[{window}]))", "scenario"
            ),
            "stage_p95_seconds": await _prometheus_vector(
                client,
                "histogram_quantile(0.95, "
                f"sum by (stage, le) (increase(olly_stage_duration_seconds_bucket[{window}])))",
                "stage",
            ),
        }
        alerts = await _prometheus_alerts(client)
        recent_requests = await _jaeger_recent_requests(client, window)

    return {
        "window": window,
        "generated_at": int(time.time()),
        "kpis": scalars,
        "breakdowns": vectors,
        "alerts": alerts,
        "recent_requests": recent_requests,
        "links": {
            "jaeger": settings.public_jaeger_url,
            "prometheus": settings.prometheus_url,
        },
    }


@router.get("/api/dashboard/traces/{trace_id}")
async def dashboard_trace(trace_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.get(f"{settings.jaeger_url}/api/traces/{trace_id}")
        response.raise_for_status()
        traces = response.json().get("data", [])
    if not traces:
        return {"trace_id": trace_id, "found": False}

    parsed = _parse_jaeger_trace(traces[0])
    parsed["found"] = True
    return parsed


async def _prometheus_scalar(client: httpx.AsyncClient, query: str) -> float:
    result = await _prometheus_query(client, query)
    if not result:
        return 0.0
    try:
        return float(result[0]["value"][1])
    except (KeyError, IndexError, TypeError, ValueError):
        return 0.0


async def _prometheus_vector(client: httpx.AsyncClient, query: str, label: str) -> list[dict[str, Any]]:
    result = await _prometheus_query(client, query)
    rows: list[dict[str, Any]] = []
    for item in result:
        metric = item.get("metric", {})
        try:
            value = float(item["value"][1])
        except (KeyError, IndexError, TypeError, ValueError):
            value = 0.0
        rows.append({"label": metric.get(label, "unknown"), "value": value})
    return sorted(rows, key=lambda row: row["value"], reverse=True)


async def _prometheus_query(client: httpx.AsyncClient, query: str) -> list[dict[str, Any]]:
    try:
        response = await client.get(f"{settings.prometheus_url}/api/v1/query", params={"query": query})
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return []
    if payload.get("status") != "success":
        return []
    return payload.get("data", {}).get("result", [])


async def _prometheus_alerts(client: httpx.AsyncClient) -> list[dict[str, str]]:
    try:
        response = await client.get(f"{settings.prometheus_url}/api/v1/alerts")
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return []

    alerts = []
    for alert in payload.get("data", {}).get("alerts", []):
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        alerts.append(
            {
                "name": labels.get("alertname", "UnknownAlert"),
                "state": alert.get("state", "unknown"),
                "severity": labels.get("severity", "warning"),
                "summary": annotations.get("summary") or annotations.get("description", ""),
            }
        )
    return alerts


async def _jaeger_recent_requests(client: httpx.AsyncClient, window: str) -> list[dict[str, Any]]:
    lookback = window if window in WINDOWS else "1h"
    try:
        response = await client.get(
            f"{settings.jaeger_url}/api/traces",
            params={
                "service": "olly-sample-api",
                "operation": "POST /chat",
                "lookback": lookback,
                "limit": 20,
            },
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return []

    traces = [_parse_jaeger_trace(trace) for trace in payload.get("data", [])]
    return sorted(traces, key=lambda item: item.get("start_time_us", 0), reverse=True)


def _parse_jaeger_trace(trace: dict[str, Any]) -> dict[str, Any]:
    spans = trace.get("spans", [])
    root = _root_span(spans)
    all_tags = [tag for span in spans for tag in span.get("tags", [])]
    stages = []
    for stage in STAGE_NAMES:
        span = next((item for item in spans if item.get("operationName") == stage), None)
        stages.append(
            {
                "name": stage,
                "duration_ms": round((span or {}).get("duration", 0) / 1000, 2),
            }
        )

    input_tokens = _tag_number(all_tags, "olly.input_tokens")
    output_tokens = _tag_number(all_tags, "olly.output_tokens")
    cost_usd = _tag_number(all_tags, "olly.cost_usd")
    infra_cost_usd = _tag_number(all_tags, "olly.infra_cost_usd")
    token_cost_usd = _tag_number(all_tags, "olly.token_cost_usd")
    has_error = any(_tag_value(span.get("tags", []), "error") is True for span in spans)
    trace_id = trace.get("traceID", "")

    return {
        "trace_id": trace_id,
        "request_id": _tag_value(all_tags, "olly.request_id") or trace_id[:12],
        "feature": _tag_value(all_tags, "olly.feature") or "unknown",
        "scenario": _tag_value(all_tags, "olly.scenario") or "unknown",
        "model": _tag_value(all_tags, "gen_ai.request.model") or "unknown",
        "status": "error" if has_error else "success",
        "latency_ms": round(root.get("duration", 0) / 1000, 2),
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "tokens": int(input_tokens + output_tokens),
        "cost_usd": cost_usd,
        "infra_cost_usd": infra_cost_usd,
        "token_cost_usd": token_cost_usd,
        "start_time_us": root.get("startTime", 0),
        "stages": stages,
        "jaeger_url": f"{settings.public_jaeger_url}/trace/{trace_id}",
    }


def _root_span(spans: list[dict[str, Any]]) -> dict[str, Any]:
    for span in spans:
        if span.get("operationName") == "POST /chat":
            return span
    if not spans:
        return {}
    return max(spans, key=lambda span: span.get("duration", 0))


def _tag_value(tags: list[dict[str, Any]], key: str) -> Any:
    for tag in tags:
        if tag.get("key") == key:
            return tag.get("value")
    return None


def _tag_number(tags: list[dict[str, Any]], key: str) -> float:
    value = _tag_value(tags, key)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@router.get("/api/alerts/metrics")
async def list_alert_metrics() -> dict[str, Any]:
    return {
        "metrics": [
            {"key": spec.key, "label": spec.label, "unit": spec.unit}
            for spec in METRIC_CATALOG.values()
        ],
        "windows": ["1m", "5m", "15m"],
        "comparators": [
            {"key": "gt", "label": "초과 (>)"},
            {"key": "lt", "label": "미만 (<)"},
        ],
    }


@router.get("/api/alerts/rules")
async def list_alert_rules() -> dict[str, Any]:
    rules = await alert_store.list_rules()
    return {"rules": [_serialize_rule(rule) for rule in rules]}


@router.post("/api/alerts/rules", status_code=201)
async def create_alert_rule(payload: AlertRulePayload) -> dict[str, Any]:
    rule = await alert_store.create(
        name=payload.name,
        metric=payload.metric,
        comparator=payload.comparator,
        threshold=payload.threshold,
        window=payload.window,
        cooldown_seconds=payload.cooldown_seconds,
        webhook_url=payload.webhook_url,
    )
    return _serialize_rule(rule)


@router.delete("/api/alerts/rules/{rule_id}", status_code=204)
async def delete_alert_rule(rule_id: str) -> None:
    deleted = await alert_store.delete(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="rule not found")


@router.post("/api/alerts/rules/{rule_id}/toggle")
async def toggle_alert_rule(rule_id: str, enabled: bool = Query(...)) -> dict[str, Any]:
    rule = await alert_store.set_enabled(rule_id, enabled)
    if rule is None:
        raise HTTPException(status_code=404, detail="rule not found")
    return _serialize_rule(rule)


@router.get("/api/alerts/history")
async def alert_history(limit: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
    if alert_evaluator is None:
        return {"history": []}
    return {"history": alert_evaluator.history(limit=limit)}


def _serialize_rule(rule: Any) -> dict[str, Any]:
    return {
        "id": rule.id,
        "name": rule.name,
        "metric": rule.metric,
        "metric_label": METRIC_CATALOG[rule.metric].label,
        "metric_unit": METRIC_CATALOG[rule.metric].unit,
        "comparator": rule.comparator,
        "threshold": rule.threshold,
        "window": rule.window,
        "cooldown_seconds": rule.cooldown_seconds,
        "webhook_url_masked": _mask_webhook(rule.webhook_url),
        "enabled": rule.enabled,
        "created_at": rule.created_at,
        "last_fired_at": rule.last_fired_at,
        "last_value": rule.last_value,
    }


def _mask_webhook(url: str) -> str:
    if len(url) <= 24:
        return url[:4] + "***"
    return url[:24] + "***" + url[-6:]
