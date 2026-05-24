import asyncio
import logging
import os
import time
from dataclasses import dataclass

import httpx

from app.alert_storage import AlertRule, AlertStore, MetricKey
from app.config import Settings


logger = logging.getLogger("olly.alerts")

EVAL_INTERVAL_SECONDS = float(os.getenv("ALERT_EVAL_INTERVAL_SECONDS", "30"))
LLM_SUMMARY_ENABLED = os.getenv("ALERT_LLM_SUMMARY", "true").lower() == "true"
LLM_SUMMARY_TIMEOUT_SECONDS = float(os.getenv("ALERT_LLM_SUMMARY_TIMEOUT", "8"))


@dataclass(frozen=True)
class MetricSpec:
    key: MetricKey
    label: str
    unit: str
    promql_template: str  # format with {window}


METRIC_CATALOG: dict[MetricKey, MetricSpec] = {
    "request_rate_per_min": MetricSpec(
        key="request_rate_per_min",
        label="요청 수 / 분",
        unit="req/min",
        promql_template="sum(rate(olly_requests_total[{window}])) * 60",
    ),
    "token_rate_per_min": MetricSpec(
        key="token_rate_per_min",
        label="토큰 수 / 분",
        unit="tokens/min",
        promql_template="sum(rate(olly_tokens_total[{window}])) * 60",
    ),
    "p95_latency_seconds": MetricSpec(
        key="p95_latency_seconds",
        label="p95 응답시간",
        unit="seconds",
        promql_template=(
            "histogram_quantile(0.95, "
            "sum by (le) (rate(olly_request_duration_seconds_bucket[{window}])))"
        ),
    ),
    "error_rate_percent": MetricSpec(
        key="error_rate_percent",
        label="에러율",
        unit="percent",
        promql_template=(
            "100 * sum(rate(olly_requests_total{{status=\"error\"}}[{window}])) "
            "/ clamp_min(sum(rate(olly_requests_total[{window}])), 1)"
        ),
    ),
    "estimated_cost_rate_per_hour": MetricSpec(
        key="estimated_cost_rate_per_hour",
        label="추정 비용 / 시간",
        unit="USD/hour",
        promql_template="sum(rate(olly_cost_usd_total[{window}])) * 3600",
    ),
    "retrieve_p95_seconds": MetricSpec(
        key="retrieve_p95_seconds",
        label="retrieve 단계 p95",
        unit="seconds",
        promql_template=(
            "histogram_quantile(0.95, "
            "sum by (le) (rate(olly_stage_duration_seconds_bucket{{stage=\"retrieve\"}}[{window}])))"
        ),
    ),
}


def build_promql(metric: MetricKey, window: str) -> str:
    spec = METRIC_CATALOG[metric]
    return spec.promql_template.format(window=window)


class AlertEvaluator:
    def __init__(self, store: AlertStore, settings: Settings, summarizer=None) -> None:
        self._store = store
        self._settings = settings
        self._summarizer = summarizer
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._history: list[dict] = []

    def history(self, limit: int = 20) -> list[dict]:
        return list(reversed(self._history[-limit:]))

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run_loop(), name="olly-alert-evaluator")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()

    async def _run_loop(self) -> None:
        async with httpx.AsyncClient(timeout=8.0) as client:
            while not self._stop.is_set():
                try:
                    await self._evaluate_once(client)
                except Exception:
                    logger.exception("alert evaluation cycle failed")
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=EVAL_INTERVAL_SECONDS)
                except asyncio.TimeoutError:
                    continue

    async def _evaluate_once(self, client: httpx.AsyncClient) -> None:
        rules = await self._store.list_rules()
        now = time.time()
        for rule in rules:
            if not rule.enabled:
                continue
            if now - rule.last_fired_at < rule.cooldown_seconds:
                continue
            value = await self._query_prometheus(client, build_promql(rule.metric, rule.window))
            if value is None:
                continue
            if not self._should_fire(rule, value):
                continue
            summary = await self._maybe_summarize(rule, value)
            ok = await self._dispatch_discord(client, rule, value, summary)
            if ok:
                await self._store.update_fired(rule.id, now, value)
                self._history.append(
                    {
                        "rule_id": rule.id,
                        "rule_name": rule.name,
                        "metric": rule.metric,
                        "value": value,
                        "threshold": rule.threshold,
                        "fired_at": now,
                        "summary": summary,
                    }
                )
                self._history = self._history[-100:]

    @staticmethod
    def _should_fire(rule: AlertRule, value: float) -> bool:
        if rule.comparator == "gt":
            return value > rule.threshold
        return value < rule.threshold

    async def _query_prometheus(self, client: httpx.AsyncClient, query: str) -> float | None:
        try:
            response = await client.get(
                f"{self._settings.prometheus_url}/api/v1/query",
                params={"query": query},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return None
        if payload.get("status") != "success":
            return None
        result = payload.get("data", {}).get("result", [])
        if not result:
            return 0.0
        try:
            raw = result[0]["value"][1]
            if raw in ("NaN", "+Inf", "-Inf"):
                return None
            return float(raw)
        except (KeyError, IndexError, TypeError, ValueError):
            return None

    async def _maybe_summarize(self, rule: AlertRule, value: float) -> str:
        if not LLM_SUMMARY_ENABLED or self._summarizer is None:
            return ""
        spec = METRIC_CATALOG[rule.metric]
        prompt = (
            "운영 알림이 발생했습니다. 운영자가 한 줄로 이해할 수 있도록 한국어로 간결히 요약하세요. "
            "추측은 하지 말고 사실만 적으세요.\n\n"
            f"- 규칙 이름: {rule.name}\n"
            f"- 지표: {spec.label} ({spec.unit})\n"
            f"- 현재값: {value:.4f}\n"
            f"- 임계값: {rule.threshold} ({rule.comparator})\n"
            f"- 평가 윈도우: {rule.window}\n"
        )
        try:
            return await asyncio.wait_for(self._summarizer(prompt), timeout=LLM_SUMMARY_TIMEOUT_SECONDS)
        except (asyncio.TimeoutError, Exception):
            logger.exception("LLM summary failed for rule %s", rule.id)
            return ""

    async def _dispatch_discord(
        self,
        client: httpx.AsyncClient,
        rule: AlertRule,
        value: float,
        summary: str,
    ) -> bool:
        spec = METRIC_CATALOG[rule.metric]
        comparator_text = "초과" if rule.comparator == "gt" else "미만"
        title = f"[OLLY] {rule.name}"
        description_lines = [
            f"**지표**: {spec.label} ({spec.unit})",
            f"**현재값**: `{value:.4f}`",
            f"**임계값**: `{rule.threshold}` {comparator_text}",
            f"**평가 윈도우**: {rule.window}",
        ]
        if summary:
            description_lines.append("")
            description_lines.append(f"**AI 요약**: {summary}")

        payload = {
            "embeds": [
                {
                    "title": title,
                    "description": "\n".join(description_lines),
                    "color": 15158332 if rule.comparator == "gt" else 3447003,
                }
            ]
        }
        try:
            response = await client.post(rule.webhook_url, json=payload, timeout=8.0)
            response.raise_for_status()
        except httpx.HTTPError:
            logger.exception("Discord dispatch failed for rule %s", rule.id)
            return False
        return True
