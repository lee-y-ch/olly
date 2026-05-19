import time
import uuid

from fastapi import FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app import mock_llm, ollama_llm
from app.config import Settings
from app.metrics import CostBreakdown, RequestMetricLabels, record_error, record_llm_duration, record_success
from app.metrics import stage_timer
from app.mock_llm import postprocess, retrieve
from app.pricing import estimate_cost_usd, estimate_infra_cost_usd
from app.schemas import ChatRequest, ChatResponse
from app.telemetry import get_tracer, setup_telemetry


settings = Settings.from_env()
LLM_CLIENTS = {
    "mock": mock_llm,
    "ollama": ollama_llm,
}

if settings.llm_backend not in LLM_CLIENTS:
    raise RuntimeError(f"Unsupported LLM_BACKEND={settings.llm_backend}. Use one of: {', '.join(LLM_CLIENTS)}")

llm_client = LLM_CLIENTS[settings.llm_backend]


app = FastAPI(title="OLLY Sample LLM API", version="0.1.0")
setup_telemetry(app)
tracer = get_tracer()


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "llm_backend": settings.llm_backend,
        "model": llm_client.model_name(),
        "compute_resource": settings.local_compute_resource,
        "compute_hourly_usd": str(settings.local_compute_hourly_usd),
    }


@app.on_event("shutdown")
async def shutdown() -> None:
    close_client = getattr(llm_client, "close", None)
    if close_client is not None:
        await close_client()


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    request_id = f"req_{uuid.uuid4().hex[:8]}"
    model_name = llm_client.model_name()
    metric_labels = RequestMetricLabels(
        model=model_name,
        feature=request.feature,
        scenario=request.scenario,
        backend=settings.llm_backend,
        resource=settings.local_compute_resource,
    )
    start = time.perf_counter()
    input_tokens = 0
    output_tokens = 0
    cost = CostBreakdown(total_usd=0.0, token_usd=0.0, infra_usd=0.0, compute_seconds=0.0)

    try:
        with tracer.start_as_current_span("retrieve") as span:
            span.set_attribute("olly.request_id", request_id)
            span.set_attribute("olly.feature", request.feature)
            span.set_attribute("olly.scenario", request.scenario)
            with stage_timer(metric_labels, "retrieve"):
                context = await retrieve(request)
            span.set_attribute("olly.retrieved_documents", len(context))

        with tracer.start_as_current_span("llm_call") as span:
            llm_start = time.perf_counter()
            span.set_attribute("gen_ai.system", settings.llm_backend)
            span.set_attribute("gen_ai.request.model", model_name)
            span.set_attribute("olly.feature", request.feature)
            span.set_attribute("olly.scenario", request.scenario)
            with stage_timer(metric_labels, "llm_call"):
                answer, input_tokens, output_tokens, llm_metadata = await llm_client.llm_call(request, context)
                llm_elapsed_seconds = time.perf_counter() - llm_start
            compute_seconds = float(llm_metadata.get("ollama_total_duration_seconds") or llm_elapsed_seconds)
            token_cost_usd = estimate_cost_usd(model_name, input_tokens, output_tokens)
            infra_cost_usd = estimate_infra_cost_usd(compute_seconds, settings.local_compute_hourly_usd)
            cost = CostBreakdown(
                total_usd=round(token_cost_usd + infra_cost_usd, 8),
                token_usd=token_cost_usd,
                infra_usd=infra_cost_usd,
                compute_seconds=compute_seconds,
            )
            span.set_attribute("olly.input_tokens", input_tokens)
            span.set_attribute("olly.output_tokens", output_tokens)
            span.set_attribute("olly.cost_usd", cost.total_usd)
            span.set_attribute("olly.token_cost_usd", cost.token_usd)
            span.set_attribute("olly.infra_cost_usd", cost.infra_usd)
            span.set_attribute("olly.compute_seconds", cost.compute_seconds)
            span.set_attribute("olly.compute_resource", settings.local_compute_resource)
            span.set_attribute("olly.compute_hourly_usd", settings.local_compute_hourly_usd)
            span.set_attribute("olly.llm_backend", settings.llm_backend)
            span.set_attribute("olly.llm_elapsed_ms", int(llm_elapsed_seconds * 1000))
            for key, value in llm_metadata.items():
                span.set_attribute(f"olly.{key}", value)
            record_llm_duration(metric_labels, llm_elapsed_seconds, llm_metadata.get("tokens_per_second", 0.0))

        with tracer.start_as_current_span("postprocess") as span:
            span.set_attribute("olly.request_id", request_id)
            with stage_timer(metric_labels, "postprocess"):
                answer = await postprocess(answer)

    except Exception as exc:
        record_error(metric_labels, time.perf_counter() - start)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    latency_seconds = time.perf_counter() - start
    record_success(metric_labels, input_tokens, output_tokens, cost, latency_seconds)

    return ChatResponse(
        request_id=request_id,
        answer=answer,
        model=model_name,
        feature=request.feature,
        llm_backend=settings.llm_backend,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost.total_usd,
        token_cost_usd=cost.token_usd,
        infra_cost_usd=cost.infra_usd,
        compute_seconds=round(cost.compute_seconds, 4),
        compute_resource=settings.local_compute_resource,
        latency_ms=int(latency_seconds * 1000),
        status="success",
    )
