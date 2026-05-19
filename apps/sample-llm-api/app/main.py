import os
import time
import uuid

from fastapi import FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from app import mock_llm, ollama_llm
from app.mock_llm import postprocess, retrieve
from app.pricing import estimate_cost_usd, estimate_infra_cost_usd
from app.schemas import ChatRequest, ChatResponse
from app.telemetry import get_tracer, setup_telemetry


LLM_BACKEND = os.getenv("LLM_BACKEND", "mock").lower()
LOCAL_COMPUTE_RESOURCE = os.getenv("LOCAL_COMPUTE_RESOURCE", "cpu").lower()
LOCAL_COMPUTE_HOURLY_USD = float(os.getenv("LOCAL_COMPUTE_HOURLY_USD", "0.05"))
LLM_CLIENTS = {
    "mock": mock_llm,
    "ollama": ollama_llm,
}

if LLM_BACKEND not in LLM_CLIENTS:
    raise RuntimeError(f"Unsupported LLM_BACKEND={LLM_BACKEND}. Use one of: {', '.join(LLM_CLIENTS)}")

llm_client = LLM_CLIENTS[LLM_BACKEND]

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


app = FastAPI(title="OLLY Sample LLM API", version="0.1.0")
setup_telemetry(app)
tracer = get_tracer()


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "llm_backend": LLM_BACKEND,
        "model": llm_client.model_name(),
        "compute_resource": LOCAL_COMPUTE_RESOURCE,
        "compute_hourly_usd": str(LOCAL_COMPUTE_HOURLY_USD),
    }


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    request_id = f"req_{uuid.uuid4().hex[:8]}"
    model_name = llm_client.model_name()
    start = time.perf_counter()
    status = "success"
    input_tokens = 0
    output_tokens = 0
    cost_usd = 0.0
    token_cost_usd = 0.0
    infra_cost_usd = 0.0
    compute_seconds = 0.0

    try:
        with tracer.start_as_current_span("retrieve") as span:
            stage_start = time.perf_counter()
            span.set_attribute("olly.request_id", request_id)
            span.set_attribute("olly.feature", request.feature)
            span.set_attribute("olly.scenario", request.scenario)
            context = await retrieve(request)
            STAGE_DURATION.labels(model_name, request.feature, request.scenario, "retrieve").observe(
                time.perf_counter() - stage_start
            )
            span.set_attribute("olly.retrieved_documents", len(context))

        with tracer.start_as_current_span("llm_call") as span:
            llm_start = time.perf_counter()
            span.set_attribute("gen_ai.system", LLM_BACKEND)
            span.set_attribute("gen_ai.request.model", model_name)
            span.set_attribute("olly.feature", request.feature)
            span.set_attribute("olly.scenario", request.scenario)
            answer, input_tokens, output_tokens, llm_metadata = await llm_client.llm_call(request, context)
            llm_elapsed_seconds = time.perf_counter() - llm_start
            STAGE_DURATION.labels(model_name, request.feature, request.scenario, "llm_call").observe(
                llm_elapsed_seconds
            )
            compute_seconds = float(llm_metadata.get("ollama_total_duration_seconds") or llm_elapsed_seconds)
            token_cost_usd = estimate_cost_usd(model_name, input_tokens, output_tokens)
            infra_cost_usd = estimate_infra_cost_usd(compute_seconds, LOCAL_COMPUTE_HOURLY_USD)
            cost_usd = round(token_cost_usd + infra_cost_usd, 8)
            span.set_attribute("olly.input_tokens", input_tokens)
            span.set_attribute("olly.output_tokens", output_tokens)
            span.set_attribute("olly.cost_usd", cost_usd)
            span.set_attribute("olly.token_cost_usd", token_cost_usd)
            span.set_attribute("olly.infra_cost_usd", infra_cost_usd)
            span.set_attribute("olly.compute_seconds", compute_seconds)
            span.set_attribute("olly.compute_resource", LOCAL_COMPUTE_RESOURCE)
            span.set_attribute("olly.compute_hourly_usd", LOCAL_COMPUTE_HOURLY_USD)
            span.set_attribute("olly.llm_backend", LLM_BACKEND)
            span.set_attribute("olly.llm_elapsed_ms", int(llm_elapsed_seconds * 1000))
            for key, value in llm_metadata.items():
                span.set_attribute(f"olly.{key}", value)
            LLM_DURATION.labels(model_name, request.feature, request.scenario, LLM_BACKEND).observe(
                llm_elapsed_seconds
            )
            tokens_per_second = llm_metadata.get("tokens_per_second", 0.0)
            if tokens_per_second > 0:
                TOKENS_PER_SECOND.labels(model_name, request.feature, request.scenario, LLM_BACKEND).observe(
                    tokens_per_second
                )

        with tracer.start_as_current_span("postprocess") as span:
            stage_start = time.perf_counter()
            span.set_attribute("olly.request_id", request_id)
            answer = await postprocess(answer)
            STAGE_DURATION.labels(model_name, request.feature, request.scenario, "postprocess").observe(
                time.perf_counter() - stage_start
            )

    except Exception as exc:
        status = "error"
        ERRORS_TOTAL.labels(model_name, request.feature, request.scenario).inc()
        REQUESTS_TOTAL.labels(model_name, request.feature, request.scenario, status).inc()
        REQUEST_DURATION.labels(model_name, request.feature, request.scenario, status).observe(
            time.perf_counter() - start
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    latency_seconds = time.perf_counter() - start
    REQUESTS_TOTAL.labels(model_name, request.feature, request.scenario, status).inc()
    TOKENS_TOTAL.labels(model_name, request.feature, "input").inc(input_tokens)
    TOKENS_TOTAL.labels(model_name, request.feature, "output").inc(output_tokens)
    COST_TOTAL.labels(model_name, request.feature).inc(cost_usd)
    TOKEN_COST_TOTAL.labels(model_name, request.feature).inc(token_cost_usd)
    INFRA_COST_TOTAL.labels(model_name, request.feature, LLM_BACKEND, LOCAL_COMPUTE_RESOURCE).inc(infra_cost_usd)
    COMPUTE_SECONDS_TOTAL.labels(model_name, request.feature, LLM_BACKEND, LOCAL_COMPUTE_RESOURCE).inc(
        compute_seconds
    )
    REQUEST_DURATION.labels(model_name, request.feature, request.scenario, status).observe(latency_seconds)

    return ChatResponse(
        request_id=request_id,
        answer=answer,
        model=model_name,
        feature=request.feature,
        llm_backend=LLM_BACKEND,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        token_cost_usd=token_cost_usd,
        infra_cost_usd=infra_cost_usd,
        compute_seconds=round(compute_seconds, 4),
        compute_resource=LOCAL_COMPUTE_RESOURCE,
        latency_ms=int(latency_seconds * 1000),
        status=status,
    )
