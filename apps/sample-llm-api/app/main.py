import time
import uuid

from fastapi import FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from opentelemetry import trace

from app import mock_llm, ollama_llm
from app.alert_storage import AlertStore
from app.alerts import AlertEvaluator
from app.analysis import build_observability_answer
from app.config import Settings
from app.dashboard import router as dashboard_router, set_alert_evaluator
from app.metrics import CostBreakdown, RequestMetricLabels, record_error, record_llm_duration, record_success
from app.metrics import stage_timer
from app.mock_llm import postprocess, retrieve
from app.pricing import estimate_cost_usd, estimate_infra_cost_usd, estimate_tokens
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
app.include_router(dashboard_router)
setup_telemetry(app)
tracer = get_tracer()


async def _summarize_alert(prompt: str) -> str:
    summary_request = ChatRequest(question=prompt, feature="alert_summary", scenario="normal")
    answer, _, _, _ = await llm_client.llm_call(summary_request, context=[])
    if not answer:
        return ""
    return answer.strip().splitlines()[0]


alert_store = AlertStore()
alert_evaluator = AlertEvaluator(alert_store, settings, summarizer=_summarize_alert)
set_alert_evaluator(alert_evaluator)


@app.on_event("startup")
async def start_alert_evaluator() -> None:
    alert_evaluator.start()


@app.on_event("shutdown")
async def stop_alert_evaluator() -> None:
    await alert_evaluator.stop()


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
    trace_id = ""
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
        root_span = trace.get_current_span()
        root_span.set_attribute("olly.request_id", request_id)
        root_span.set_attribute("olly.feature", request.feature)
        root_span.set_attribute("olly.scenario", request.scenario)
        trace_id = format(root_span.get_span_context().trace_id, "032x")
        root_span.set_attribute("olly.trace_id", trace_id)

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
            observability_answer = await build_observability_answer(request)
            if observability_answer is not None:
                answer = observability_answer
                output_tokens = estimate_tokens(answer)
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
        latency_seconds = time.perf_counter() - start
        record_error(metric_labels, request_id, trace_id, latency_seconds)
        if request.scenario == "error":
            answer = _demo_error_answer(request_id, trace_id)
            output_tokens = estimate_tokens(answer)
            return ChatResponse(
                request_id=request_id,
                trace_id=trace_id,
                answer=answer,
                model=model_name,
                feature=request.feature,
                llm_backend=settings.llm_backend,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=0.0,
                token_cost_usd=0.0,
                infra_cost_usd=0.0,
                compute_seconds=0.0,
                compute_resource=settings.local_compute_resource,
                latency_ms=int(latency_seconds * 1000),
                status="error",
            )
        raise HTTPException(status_code=500, detail="요청 처리 중 서버 오류가 발생했습니다.") from exc

    latency_seconds = time.perf_counter() - start
    record_success(metric_labels, request_id, trace_id, input_tokens, output_tokens, cost, latency_seconds)

    return ChatResponse(
        request_id=request_id,
        trace_id=trace_id,
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


def _demo_error_answer(request_id: str, trace_id: str) -> str:
    return (
        "이 요청은 실패 요청 시나리오를 보여주기 위해 일부러 실패로 기록했습니다.\n\n"
        f"- request_id: {request_id}\n"
        f"- trace_id: {trace_id}\n"
        "- status: error\n\n"
        "즉, 지금 화면은 모델이 답을 몰라서 실패한 것이 아니라 OLLY가 실패 요청도 관측할 수 있는지 보여주는 데모입니다. "
        "운영자 대시보드의 Recent Requests와 Jaeger trace에서 이 요청을 확인하면 실패 요청도 추적 대상에 남는 것을 볼 수 있습니다."
    )
