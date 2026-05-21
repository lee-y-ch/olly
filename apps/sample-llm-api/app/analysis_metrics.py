from dataclasses import dataclass

import httpx

from app.config import Settings


@dataclass(frozen=True)
class MetricComparison:
    current: float
    previous: float
    delta: float
    change_percent: float


settings = Settings.from_env()


async def collect_period_comparison(window: str) -> dict[str, MetricComparison]:
    query_pairs = {
        "total_requests": f"sum(increase(olly_requests_total[{window}]))",
        "total_tokens": f"sum(increase(olly_tokens_total[{window}]))",
        "estimated_cost_usd": f"sum(increase(olly_cost_usd_total[{window}]))",
        "infra_cost_usd": f"sum(increase(olly_infra_cost_usd_total[{window}]))",
        "avg_latency_seconds": (
            f"sum(increase(olly_request_duration_seconds_sum[{window}])) "
            f"/ clamp_min(sum(increase(olly_request_duration_seconds_count[{window}])), 1)"
        ),
        "error_rate_percent": (
            f"100 * sum(increase(olly_requests_total{{status=\"error\"}}[{window}])) "
            f"/ clamp_min(sum(increase(olly_requests_total[{window}])), 1)"
        ),
    }
    comparison: dict[str, MetricComparison] = {}
    async with httpx.AsyncClient(timeout=8.0) as client:
        for key, query in query_pairs.items():
            current = await _prometheus_scalar(client, query)
            previous = await _prometheus_scalar(client, _with_offset(query, window))
            comparison[key] = MetricComparison(
                current=current,
                previous=previous,
                delta=current - previous,
                change_percent=_change_percent(current, previous),
            )
    return comparison


def _with_offset(query: str, window: str) -> str:
    return query.replace(f"[{window}]", f"[{window}] offset {window}")


async def _prometheus_scalar(client: httpx.AsyncClient, query: str) -> float:
    try:
        response = await client.get(f"{settings.prometheus_url}/api/v1/query", params={"query": query})
        response.raise_for_status()
        payload = response.json()
        result = payload.get("data", {}).get("result", [])
        if payload.get("status") != "success" or not result:
            return 0.0
        return float(result[0]["value"][1])
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        return 0.0


def _change_percent(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return (current - previous) / previous * 100
