import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from prometheus_client import Counter, Histogram


REQUESTS_TOTAL = Counter(
    "olly_requests_total",
    "Total OLLY chat requests",
    ["model", "feature", "scenario", "status"],
)
TOKENS_TOTAL = Counter(
    "olly_tokens_total",
    "Total OLLY token usage",
    ["model", "feature", "token_type"],
)
COST_TOTAL = Counter(
    "olly_cost_usd_total",
    "Total estimated OLLY LLM cost in USD, including token API cost and local compute cost",
    ["model", "feature"],
)
TOKEN_COST_TOTAL = Counter(
    "olly_token_cost_usd_total",
    "Total estimated OLLY token API cost in USD",
    ["model", "feature"],
)
INFRA_COST_TOTAL = Counter(
    "olly_infra_cost_usd_total",
    "Total estimated OLLY local inference infrastructure cost in USD",
    ["model", "feature", "backend", "resource"],
)
COMPUTE_SECONDS_TOTAL = Counter(
    "olly_inference_compute_seconds_total",
    "Total local inference compute seconds",
    ["model", "feature", "backend", "resource"],
)
ERRORS_TOTAL = Counter(
    "olly_errors_total",
    "Total OLLY chat errors",
    ["model", "feature", "scenario"],
)
STAGE_DURATION = Histogram(
    "olly_stage_duration_seconds",
    "OLLY request stage duration in seconds",
    ["model", "feature", "scenario", "stage"],
    buckets=(0.05, 0.1, 0.3, 0.5, 1, 2, 3, 5, 10, 30, 60),
)
REQUEST_DURATION = Histogram(
    "olly_request_duration_seconds",
    "OLLY chat request duration in seconds",
    ["model", "feature", "scenario", "status"],
    buckets=(0.1, 0.3, 0.5, 1, 2, 3, 5, 10),
)
LLM_DURATION = Histogram(
    "olly_llm_duration_seconds",
    "OLLY LLM call duration in seconds",
    ["model", "feature", "scenario", "backend"],
    buckets=(0.1, 0.3, 0.5, 1, 2, 3, 5, 10, 30, 60),
)
TOKENS_PER_SECOND = Histogram(
    "olly_generation_tokens_per_second",
    "OLLY local LLM generation throughput in output tokens per second",
    ["model", "feature", "scenario", "backend"],
    buckets=(1, 3, 5, 10, 20, 40, 80, 120),
)


@dataclass(frozen=True)
class RequestMetricLabels:
    model: str
    feature: str
    scenario: str
    backend: str
    resource: str


@dataclass(frozen=True)
class CostBreakdown:
    total_usd: float
    token_usd: float
    infra_usd: float
    compute_seconds: float


@contextmanager
def stage_timer(labels: RequestMetricLabels, stage: str) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        STAGE_DURATION.labels(labels.model, labels.feature, labels.scenario, stage).observe(
            time.perf_counter() - start
        )


def record_llm_duration(labels: RequestMetricLabels, elapsed_seconds: float, tokens_per_second: float) -> None:
    LLM_DURATION.labels(labels.model, labels.feature, labels.scenario, labels.backend).observe(elapsed_seconds)
    if tokens_per_second > 0:
        TOKENS_PER_SECOND.labels(labels.model, labels.feature, labels.scenario, labels.backend).observe(
            tokens_per_second
        )


def record_success(
    labels: RequestMetricLabels,
    input_tokens: int,
    output_tokens: int,
    cost: CostBreakdown,
    latency_seconds: float,
) -> None:
    REQUESTS_TOTAL.labels(labels.model, labels.feature, labels.scenario, "success").inc()
    TOKENS_TOTAL.labels(labels.model, labels.feature, "input").inc(input_tokens)
    TOKENS_TOTAL.labels(labels.model, labels.feature, "output").inc(output_tokens)
    COST_TOTAL.labels(labels.model, labels.feature).inc(cost.total_usd)
    TOKEN_COST_TOTAL.labels(labels.model, labels.feature).inc(cost.token_usd)
    INFRA_COST_TOTAL.labels(labels.model, labels.feature, labels.backend, labels.resource).inc(cost.infra_usd)
    COMPUTE_SECONDS_TOTAL.labels(labels.model, labels.feature, labels.backend, labels.resource).inc(
        cost.compute_seconds
    )
    REQUEST_DURATION.labels(labels.model, labels.feature, labels.scenario, "success").observe(latency_seconds)


def record_error(labels: RequestMetricLabels, latency_seconds: float) -> None:
    ERRORS_TOTAL.labels(labels.model, labels.feature, labels.scenario).inc()
    REQUESTS_TOTAL.labels(labels.model, labels.feature, labels.scenario, "error").inc()
    REQUEST_DURATION.labels(labels.model, labels.feature, labels.scenario, "error").observe(latency_seconds)
