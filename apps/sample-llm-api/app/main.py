import time
import uuid

from fastapi import FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from app.mock_llm import llm_call, postprocess, retrieve
from app.pricing import estimate_cost_usd
from app.schemas import ChatRequest, ChatResponse
from app.telemetry import get_tracer, setup_telemetry


MODEL_NAME = "gpt-4o-mini-mock"

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
    "Total estimated OLLY LLM cost in USD",
    ["model", "feature"],
)
ERRORS_TOTAL = Counter(
    "olly_errors_total",
    "Total OLLY chat errors",
    ["model", "feature", "scenario"],
)
REQUEST_DURATION = Histogram(
    "olly_request_duration_seconds",
    "OLLY chat request duration in seconds",
    ["model", "feature", "scenario", "status"],
    buckets=(0.1, 0.3, 0.5, 1, 2, 3, 5, 10),
)


app = FastAPI(title="OLLY Sample LLM API", version="0.1.0")
setup_telemetry(app)
tracer = get_tracer()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    request_id = f"req_{uuid.uuid4().hex[:8]}"
    start = time.perf_counter()
    status = "success"
    input_tokens = 0
    output_tokens = 0
    cost_usd = 0.0

    try:
        with tracer.start_as_current_span("retrieve") as span:
            span.set_attribute("olly.request_id", request_id)
            span.set_attribute("olly.feature", request.feature)
            span.set_attribute("olly.scenario", request.scenario)
            context = await retrieve(request)
            span.set_attribute("olly.retrieved_documents", len(context))

        with tracer.start_as_current_span("llm_call") as span:
            span.set_attribute("gen_ai.system", "mock")
            span.set_attribute("gen_ai.request.model", MODEL_NAME)
            span.set_attribute("olly.feature", request.feature)
            span.set_attribute("olly.scenario", request.scenario)
            answer, input_tokens, output_tokens = await llm_call(request, context)
            cost_usd = estimate_cost_usd(MODEL_NAME, input_tokens, output_tokens)
            span.set_attribute("olly.input_tokens", input_tokens)
            span.set_attribute("olly.output_tokens", output_tokens)
            span.set_attribute("olly.cost_usd", cost_usd)

        with tracer.start_as_current_span("postprocess") as span:
            span.set_attribute("olly.request_id", request_id)
            answer = await postprocess(answer)

    except Exception as exc:
        status = "error"
        ERRORS_TOTAL.labels(MODEL_NAME, request.feature, request.scenario).inc()
        REQUESTS_TOTAL.labels(MODEL_NAME, request.feature, request.scenario, status).inc()
        REQUEST_DURATION.labels(MODEL_NAME, request.feature, request.scenario, status).observe(
            time.perf_counter() - start
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    latency_seconds = time.perf_counter() - start
    REQUESTS_TOTAL.labels(MODEL_NAME, request.feature, request.scenario, status).inc()
    TOKENS_TOTAL.labels(MODEL_NAME, request.feature, "input").inc(input_tokens)
    TOKENS_TOTAL.labels(MODEL_NAME, request.feature, "output").inc(output_tokens)
    COST_TOTAL.labels(MODEL_NAME, request.feature).inc(cost_usd)
    REQUEST_DURATION.labels(MODEL_NAME, request.feature, request.scenario, status).observe(latency_seconds)

    return ChatResponse(
        request_id=request_id,
        answer=answer,
        model=MODEL_NAME,
        feature=request.feature,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        latency_ms=int(latency_seconds * 1000),
        status=status,
    )
