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


class AlertRulePatchPayload(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    metric: MetricKey | None = None
    comparator: Comparator | None = None
    threshold: float | None = None
    window: EvalWindow | None = None
    cooldown_seconds: int | None = Field(None, ge=10, le=86400)
    webhook_url: str | None = Field(None, min_length=10)
    enabled: bool | None = None

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
    stage_bottleneck_summary = _build_stage_bottleneck_summary(recent_requests)
    primary_insight = _build_primary_insight_aggregate(
        kpis=scalars,
        recent_requests=recent_requests,
        alerts=alerts,
        stage_bottleneck_summary=stage_bottleneck_summary,
    )

    return {
        "window": window,
        "generated_at": int(time.time()),
        "kpis": scalars,
        "breakdowns": vectors,
        "alerts": alerts,
        "recent_requests": recent_requests,
        "primary_insight": primary_insight,
        "stage_bottleneck_summary": stage_bottleneck_summary,
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
                "name": labels.get("alertname", "이름 없는 알림"),
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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_ms(ms: Any) -> str:
    value = _safe_float(ms, 0.0)
    if value >= 1000:
        return f"{(value / 1000):.2f}s"
    return f"{int(round(value))}ms"


def _dominant_stage(stages: Any) -> dict[str, Any] | None:
    if not isinstance(stages, list):
        return None
    parsed: list[dict[str, Any]] = []
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        duration = _safe_float(stage.get("duration_ms"), 0.0)
        if duration > 0:
            parsed.append(
                {
                    "name": str(stage.get("name") or "unknown"),
                    "duration_ms": duration,
                }
            )
    if not parsed:
        return None
    total = sum(item["duration_ms"] for item in parsed)
    if total <= 0:
        return None
    dominant = max(parsed, key=lambda item: item["duration_ms"])
    return {
        "name": dominant["name"],
        "duration_ms": dominant["duration_ms"],
        "ratio": dominant["duration_ms"] / total,
    }


def _build_primary_insight(
    *,
    kpis: dict[str, Any] | None,
    recent_requests: list[dict[str, Any]] | None,
    alerts: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    rows = recent_requests or []
    alert_rows = alerts or []

    error_rows = [row for row in rows if str(row.get("status", "")).lower() == "error"]
    if error_rows:
        target = error_rows[0]
        request_id = str(target.get("request_id") or "-")
        scenario = str(target.get("scenario") or "unknown")
        return {
            "severity": "critical",
            "type": "error_request",
            "badge": "needs attention",
            "title": "실패 요청이 남아 있어요.",
            "summary": f"최근 요청 중 실패 상태가 {len(error_rows)}건 확인됐어요. {request_id} 요청을 먼저 확인하는 게 좋아요.",
            "evidence": [
                f"error_requests={len(error_rows)}",
                f"request_id={request_id}",
                f"scenario={scenario}",
                f"latency={_format_ms(target.get('latency_ms'))}",
            ],
            "target_trace_id": target.get("trace_id"),
            "target_request_id": target.get("request_id"),
            "recommended_action": "요청 추적 탭에서 해당 트레이스의 실패 구간을 확인하세요.",
        }

    slow_rows = [row for row in rows if _safe_float(row.get("latency_ms"), 0.0) >= 3000]
    if slow_rows:
        target = max(slow_rows, key=lambda row: _safe_float(row.get("latency_ms"), 0.0))
        scenario = str(target.get("scenario") or "unknown")
        if scenario == "slow_retrieve":
            insight_type = "slow_retrieve"
            title = "RAG 검색 지연이 보여요."
            recommended_action = "요청 추적 탭에서 RAG 검색 구간과 문서 검색 단계를 확인하세요."
        elif scenario == "slow_llm":
            insight_type = "slow_llm"
            title = "LLM 응답 지연이 보여요."
            recommended_action = "요청 추적 탭에서 LLM 생성 구간과 모델 응답 시간을 확인하세요."
        else:
            insight_type = "slow_request"
            title = "느린 요청이 보여요."
            recommended_action = "요청 추적 탭에서 가장 오래 걸린 처리 구간을 확인하세요."

        dom = _dominant_stage(target.get("stages"))
        request_id = str(target.get("request_id") or "-")
        latency_text = _format_ms(target.get("latency_ms"))
        evidence = [
            f"request_id={request_id}",
            f"feature={target.get('feature') or 'unknown'}",
            f"scenario={scenario}",
            f"latency={latency_text}",
        ]
        if dom:
            ratio_pct = int(round(_safe_float(dom.get("ratio")) * 100))
            evidence.append(f"dominant_stage={dom['name']}")
            evidence.append(f"dominant_stage_ratio={ratio_pct}%")
            summary = (
                f"{request_id} 요청이 {latency_text}로 가장 느렸고, "
                f"{dom['name']} 단계가 전체 처리 시간의 {ratio_pct}%를 차지했어요."
            )
        else:
            summary = (
                f"{request_id} 요청이 {latency_text}로 가장 느렸어요. "
                "span 상세 정보가 없어 전체 응답 시간 기준으로 판단했어요."
            )

        return {
            "severity": "warning",
            "type": insight_type,
            "badge": "slow span",
            "title": title,
            "summary": summary,
            "evidence": evidence,
            "target_trace_id": target.get("trace_id"),
            "target_request_id": target.get("request_id"),
            "recommended_action": recommended_action,
        }

    high_token_rows = [row for row in rows if str(row.get("scenario") or "") == "high_token"]
    if high_token_rows:
        target = max(high_token_rows, key=lambda row: int(row.get("tokens") or 0))
        token_count = int(target.get("tokens") or 0)
        request_id = str(target.get("request_id") or "-")
        return {
            "severity": "warning",
            "type": "high_token",
            "badge": "token spike",
            "title": "토큰 사용량이 높은 요청이 있어요.",
            "summary": (
                f"최근 요청 중 토큰 과다 사용 시나리오가 {len(high_token_rows)}건 감지됐어요. "
                f"{request_id} 요청은 토큰 {token_count}개를 사용했어요."
            ),
            "evidence": [
                f"high_token_requests={len(high_token_rows)}",
                f"request_id={request_id}",
                f"feature={target.get('feature') or 'unknown'}",
                f"tokens={token_count}",
                f"latency={_format_ms(target.get('latency_ms'))}",
            ],
            "target_trace_id": target.get("trace_id"),
            "target_request_id": target.get("request_id"),
            "recommended_action": "프롬프트 길이와 응답 길이를 확인해 비용 증가 원인을 점검하세요.",
        }

    if alert_rows:
        critical = next(
            (a for a in alert_rows if str(a.get("severity", "")).lower() == "critical"),
            None,
        )
        selected = critical or alert_rows[0]
        alert_severity = str(selected.get("severity") or "warning").lower()
        return {
            "severity": "critical" if alert_severity == "critical" else "warning",
            "type": "active_alert",
            "badge": "alert active",
            "title": "활성 알림이 있어요.",
            "summary": (
                f"{selected.get('name', '이름 없는 알림')} 알림이 "
                f"{selected.get('summary') or selected.get('state') or '발생 중'} 상태예요."
            ),
            "evidence": [
                f"alert={selected.get('name', '이름 없는 알림')}",
                f"severity={selected.get('severity', 'warning')}",
                f"state={selected.get('state', 'unknown')}",
            ],
            "target_trace_id": None,
            "target_request_id": None,
            "recommended_action": "알림 관리 탭에서 발화 조건과 최근 이력을 확인하세요.",
        }

    return {
        "severity": "info",
        "type": "calm",
        "badge": "calm mode",
        "title": "신호가 조용해요.",
        "summary": "최근 요청에서 실패, 큰 지연, 토큰 급증 신호는 보이지 않아요.",
        "evidence": [
            f"error_requests={len(error_rows)}",
            "slow_requests=0",
            f"high_token_requests={len(high_token_rows)}",
        ],
        "target_trace_id": None,
        "target_request_id": None,
        "recommended_action": "현재 상태를 유지하면서 새 요청을 관찰하세요.",
    }


def _stage_label(name: str) -> str:
    if name == "retrieve":
        return "RAG 검색"
    if name == "llm_call":
        return "LLM 생성"
    if name == "postprocess":
        return "후처리"
    return name


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    idx = max(0, min(len(sorted_values) - 1, int((len(sorted_values) - 1) * 0.95)))
    return sorted_values[idx]


def _build_stage_bottleneck_summary(recent_requests: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = recent_requests or []
    bucket: dict[str, list[float]] = {}
    sample_size = 0
    for row in rows:
        stages = row.get("stages")
        if not isinstance(stages, list) or not stages:
            continue
        valid = False
        for stage in stages:
            if not isinstance(stage, dict):
                continue
            name = str(stage.get("name") or "")
            duration = _safe_float(stage.get("duration_ms"), 0.0)
            if not name or duration < 0:
                continue
            bucket.setdefault(name, []).append(duration)
            valid = True
        if valid:
            sample_size += 1

    if not bucket:
        return {
            "sample_size": 0,
            "dominant_stage": None,
            "dominant_stage_label": None,
            "avg_duration_ms": 0,
            "p95_duration_ms": 0,
            "ratio": 0,
            "stage_stats": [],
        }

    stage_stats: list[dict[str, Any]] = []
    grand_total = 0.0
    for name, durations in bucket.items():
        total = sum(durations)
        grand_total += total
        count = len(durations)
        stage_stats.append(
            {
                "name": name,
                "label": _stage_label(name),
                "count": count,
                "avg_duration_ms": round(total / count, 2) if count else 0.0,
                "p95_duration_ms": round(_p95(durations), 2),
                "total_duration_ms": round(total, 2),
                "ratio": 0.0,
            }
        )

    for item in stage_stats:
        item["ratio"] = round((item["total_duration_ms"] / grand_total), 4) if grand_total > 0 else 0.0

    dominant = max(stage_stats, key=lambda item: item["p95_duration_ms"])
    return {
        "sample_size": sample_size,
        "dominant_stage": dominant["name"],
        "dominant_stage_label": dominant["label"],
        "avg_duration_ms": dominant["avg_duration_ms"],
        "p95_duration_ms": dominant["p95_duration_ms"],
        "ratio": dominant["ratio"],
        "stage_stats": sorted(stage_stats, key=lambda item: item["total_duration_ms"], reverse=True),
    }


def _pick_representative_by_stage(rows: list[dict[str, Any]], stage_name: str) -> dict[str, Any] | None:
    representative: dict[str, Any] | None = None
    best_duration = -1.0
    for row in rows:
        stages = row.get("stages")
        if not isinstance(stages, list):
            continue
        for stage in stages:
            if not isinstance(stage, dict):
                continue
            if str(stage.get("name")) != stage_name:
                continue
            duration = _safe_float(stage.get("duration_ms"), 0.0)
            if duration > best_duration:
                best_duration = duration
                representative = row
    return representative


def _build_primary_insight_aggregate(
    *,
    kpis: dict[str, Any] | None,
    recent_requests: list[dict[str, Any]] | None,
    alerts: list[dict[str, Any]] | None,
    stage_bottleneck_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    rows = recent_requests or []
    alert_rows = alerts or []
    sample_size = len(rows)
    error_rows = [row for row in rows if str(row.get("status", "")).lower() == "error"]
    slow_rows = [row for row in rows if _safe_float(row.get("latency_ms"), 0.0) >= 3000]
    high_token_rows = [row for row in rows if str(row.get("scenario") or "") == "high_token"]
    error_count = len(error_rows)
    error_rate = (error_count / sample_size) if sample_size else 0.0
    high_token_count = len(high_token_rows)
    high_token_rate = (high_token_count / sample_size) if sample_size else 0.0
    total_tokens = int(sum(int(row.get("tokens") or 0) for row in rows))

    if sample_size > 0 and (error_count >= 2 or error_rate >= 0.1):
        rep = error_rows[0] if error_rows else None
        return {
            "severity": "critical",
            "type": "error_rate",
            "badge": "needs attention",
            "title": "실패 요청 비율이 높아졌어요.",
            "summary": (
                f"최근 {sample_size}개 요청 중 {error_count}건이 실패했습니다. "
                f"실패율이 {error_rate * 100:.1f}%로 올라가 요청 안정성을 먼저 확인하는 것이 좋습니다."
            ),
            "evidence": [
                f"sample_size={sample_size}",
                f"error_requests={error_count}",
                f"error_rate={error_rate * 100:.1f}%",
            ],
            "target_trace_id": rep.get("trace_id") if rep else None,
            "target_request_id": rep.get("request_id") if rep else None,
            "recommended_action": "대표 실패 트레이스를 확인하고 오류 구간과 예외 메시지를 점검하세요.",
            "scope": "aggregate",
            "basis": "recent_requests",
            "sample_size": sample_size,
        }

    stage_summary = stage_bottleneck_summary or {}
    stage_sample_size = int(stage_summary.get("sample_size") or 0)
    dominant_stage = str(stage_summary.get("dominant_stage") or "")
    dominant_label = str(stage_summary.get("dominant_stage_label") or _stage_label(dominant_stage) or "")
    dominant_p95 = _safe_float(stage_summary.get("p95_duration_ms"), 0.0)
    dominant_avg = _safe_float(stage_summary.get("avg_duration_ms"), 0.0)
    if stage_sample_size > 0 and dominant_stage and dominant_p95 >= 2000:
        severity = "critical" if dominant_p95 >= 5000 else "warning"
        if dominant_stage == "llm_call":
            title = "LLM 생성 지연이 두드러져요."
            action = "대표 트레이스를 확인하고 프롬프트 길이, 출력 길이, 모델 응답 시간을 점검하세요."
        elif dominant_stage == "retrieve":
            title = "RAG 검색 지연이 두드러져요."
            action = "대표 트레이스를 확인하고 검색 단계, 문서 수, RAG 검색 지연 시간을 점검하세요."
        elif dominant_stage == "postprocess":
            title = "후처리 지연이 두드러져요."
            action = "대표 트레이스를 확인하고 응답 후처리 로직을 점검하세요."
        else:
            title = "단계 지연이 두드러져요."
            action = "대표 트레이스를 확인하고 해당 단계의 처리 시간을 점검하세요."
        rep = _pick_representative_by_stage(rows, dominant_stage)
        return {
            "severity": severity,
            "type": "stage_latency",
            "badge": "stage latency",
            "title": title,
            "summary": (
                f"최근 {stage_sample_size}개 요청 기준 {dominant_label} 단계의 p95가 {_format_ms(dominant_p95)}로 가장 높습니다. "
                "느린 요청에서는 해당 구간이 주요 병목일 가능성이 큽니다."
            ),
            "evidence": [
                f"sample_size={stage_sample_size}",
                f"dominant_stage={dominant_label}",
                f"p95={_format_ms(dominant_p95)}",
                f"avg={_format_ms(dominant_avg)}",
            ],
            "target_trace_id": rep.get("trace_id") if rep else None,
            "target_request_id": rep.get("request_id") if rep else None,
            "recommended_action": action,
            "scope": "aggregate",
            "basis": "stage_bottleneck_summary",
            "sample_size": stage_sample_size,
        }

    if sample_size > 0 and (high_token_count >= 2 or high_token_rate >= 0.1):
        rep = max(high_token_rows, key=lambda row: int(row.get("tokens") or 0), default=None)
        return {
            "severity": "warning",
            "type": "token_usage",
            "badge": "token spike",
            "title": "토큰 사용량이 높아졌어요.",
            "summary": (
                f"최근 {sample_size}개 요청 중 {high_token_count}건에서 토큰 과다 사용 시나리오가 감지됐습니다. "
                "프롬프트 길이나 응답 길이 증가로 비용이 늘 수 있습니다."
            ),
            "evidence": [
                f"sample_size={sample_size}",
                f"high_token_requests={high_token_count}",
                f"high_token_rate={high_token_rate * 100:.1f}%",
                f"total_tokens={total_tokens}",
            ],
            "target_trace_id": rep.get("trace_id") if rep else None,
            "target_request_id": rep.get("request_id") if rep else None,
            "recommended_action": "대표 요청의 입력/출력 토큰 수를 확인하고 프롬프트 또는 응답 길이를 조정하세요.",
            "scope": "aggregate",
            "basis": "recent_requests",
            "sample_size": sample_size,
        }

    if alert_rows:
        critical = next((a for a in alert_rows if str(a.get("severity", "")).lower() == "critical"), None)
        selected = critical or alert_rows[0]
        alert_severity = str(selected.get("severity") or "warning").lower()
        return {
            "severity": "critical" if alert_severity == "critical" else "warning",
            "type": "active_alert",
            "badge": "alert active",
            "title": "활성 알림이 있어요.",
            "summary": (
                f"현재 Prometheus 알림 {selected.get('name', '이름 없는 알림')}가 활성 상태입니다. "
                "알림 규칙과 최근 발화 이력을 확인하세요."
            ),
            "evidence": [
                f"alert={selected.get('name', '이름 없는 알림')}",
                f"severity={selected.get('severity', 'warning')}",
                f"state={selected.get('state', 'unknown')}",
            ],
            "target_trace_id": None,
            "target_request_id": None,
            "recommended_action": "알림 관리 탭에서 발화 조건과 최근 이력을 확인하세요.",
            "scope": "aggregate",
            "basis": "alerts",
            "sample_size": sample_size,
        }

    if sample_size > 0 and error_count == 1:
        rep = error_rows[0]
        return {
            "severity": "warning",
            "type": "single_error_request",
            "badge": "single issue",
            "title": "실패 요청 1건이 확인됐어요.",
            "summary": "최근 요청 중 실패 요청 1건이 확인됐습니다. 전체 실패율은 높지 않지만 대표 트레이스를 확인해보는 것이 좋습니다.",
            "evidence": [
                f"sample_size={sample_size}",
                "error_requests=1",
                f"error_rate={error_rate * 100:.1f}%",
            ],
            "target_trace_id": rep.get("trace_id"),
            "target_request_id": rep.get("request_id"),
            "recommended_action": "대표 실패 트레이스를 확인하고 오류 구간과 예외 메시지를 점검하세요.",
            "scope": "single_trace",
            "basis": "recent_requests",
            "sample_size": sample_size,
        }

    if slow_rows:
        rep = max(slow_rows, key=lambda row: _safe_float(row.get("latency_ms"), 0.0))
        return {
            "severity": "warning",
            "type": "single_slow_request",
            "badge": "single slow trace",
            "title": "느린 요청 1건이 감지됐어요.",
            "summary": "최근 요청 중 지연이 큰 요청 1건이 확인됐습니다. 전체 경향으로 보긴 어렵지만 대표 트레이스를 확인해보는 것이 좋습니다.",
            "evidence": [
                f"sample_size={sample_size}",
                f"latency={_format_ms(rep.get('latency_ms'))}",
                f"scenario={rep.get('scenario') or 'unknown'}",
            ],
            "target_trace_id": rep.get("trace_id"),
            "target_request_id": rep.get("request_id"),
            "recommended_action": "대표 트레이스를 확인하고 가장 오래 걸린 구간을 점검하세요.",
            "scope": "single_trace",
            "basis": "recent_requests",
            "sample_size": sample_size,
        }

    if sample_size > 0 and high_token_count == 1:
        rep = high_token_rows[0]
        return {
            "severity": "warning",
            "type": "single_high_token_request",
            "badge": "single token spike",
            "title": "토큰 사용량이 높은 요청 1건이 감지됐어요.",
            "summary": "최근 요청 중 토큰 사용량이 높은 요청 1건이 확인됐습니다. 전체 경향은 아니지만 대표 요청을 점검해보는 것이 좋습니다.",
            "evidence": [
                f"sample_size={sample_size}",
                "high_token_requests=1",
                f"tokens={int(rep.get('tokens') or 0)}",
            ],
            "target_trace_id": rep.get("trace_id"),
            "target_request_id": rep.get("request_id"),
            "recommended_action": "대표 요청의 입력/출력 토큰 수를 확인하고 길이를 조정하세요.",
            "scope": "single_trace",
            "basis": "recent_requests",
            "sample_size": sample_size,
        }

    stage_normal = "normal"
    if stage_sample_size > 0 and dominant_p95 >= 2000:
        stage_normal = "elevated"
    return {
        "severity": "info",
        "type": "calm",
        "badge": "calm mode",
        "title": "신호가 조용해요.",
        "summary": "최근 요청에서 실패율 증가, 큰 지연, 토큰 급증 신호는 보이지 않아요.",
        "evidence": [
            f"sample_size={sample_size}",
            f"error_rate={error_rate * 100:.1f}%",
            f"stage_p95={stage_normal}",
            f"high_token_requests={high_token_count}",
        ],
        "target_trace_id": None,
        "target_request_id": None,
        "recommended_action": "현재 상태를 유지하면서 새 요청을 관찰하세요.",
        "scope": "aggregate",
        "basis": "recent_requests",
        "sample_size": sample_size,
    }


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


@router.patch("/api/alerts/rules/{rule_id}")
async def patch_alert_rule(rule_id: str, payload: AlertRulePatchPayload) -> dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        rule = await alert_store.get(rule_id)
        if rule is None:
            raise HTTPException(status_code=404, detail="rule not found")
        return _serialize_rule(rule)
    rule = await alert_store.update(rule_id, **updates)
    if rule is None:
        raise HTTPException(status_code=404, detail="rule not found")
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
