from typing import Any

from app.dashboard import collect_dashboard_summary
from app.schemas import ChatRequest


SLOW_KEYWORDS = ("느려", "느린", "지연", "latency", "병목", "bottleneck", "rag", "openai")
COST_KEYWORDS = ("비용", "cost", "토큰", "token", "많이", "2배", "증가")
ERROR_KEYWORDS = ("실패", "에러", "오류", "error", "fail")


async def build_observability_answer(request: ChatRequest, window: str = "1h") -> str | None:
    if not is_observability_question(request):
        return None

    snapshot = await collect_dashboard_summary(window)
    question = request.question.lower()
    if request.scenario == "error" or _contains(question, ERROR_KEYWORDS):
        return _answer_error(snapshot, window)
    if request.scenario == "high_token" or _contains(question, COST_KEYWORDS):
        return _answer_cost(snapshot, window)
    if request.scenario in {"slow_retrieve", "slow_llm"} or _contains(question, SLOW_KEYWORDS):
        return _answer_latency(snapshot, window)
    return _answer_overview(snapshot, window)


def is_observability_question(request: ChatRequest) -> bool:
    question = request.question.lower()
    return (
        request.scenario != "normal"
        or _contains(question, SLOW_KEYWORDS)
        or _contains(question, COST_KEYWORDS)
        or _contains(question, ERROR_KEYWORDS)
        or "olly" in question
    )


def _contains(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _answer_latency(snapshot: dict[str, Any], window: str) -> str:
    kpis = snapshot.get("kpis", {})
    stages = _stage_summary(snapshot)
    slowest = stages[0] if stages else {"label": "unknown", "value": 0.0}
    stage_name = str(slowest["label"])
    stage_seconds = float(slowest["value"])
    stage_percent = _stage_percent(stage_seconds, stages)
    recent = _slowest_recent_trace(snapshot)

    if stage_name == "retrieve":
        cause = (
            "최근 데이터 기준으로는 LLM 자체보다 RAG 검색 단계가 병목입니다. "
            "retrieve가 길다는 것은 답변 생성 전에 관련 문서를 찾는 과정에서 시간이 많이 쓰였다는 뜻입니다."
        )
        action = "따라서 우선 확인할 곳은 모델이 아니라 벡터 검색, 문서 조회, 인덱스 상태, 검색 결과 개수입니다."
    elif stage_name == "llm_call":
        cause = (
            "최근 데이터 기준으로는 RAG 검색보다 LLM 답변 생성 단계가 병목입니다. "
            "llm_call이 길다는 것은 gemma3:1b가 프롬프트를 처리하고 답변을 생성하는 시간이 길었다는 뜻입니다."
        )
        action = "따라서 프롬프트 길이, 출력 길이, CPU/GPU 성능, 모델 크기를 먼저 확인해야 합니다."
    elif stage_name == "postprocess":
        cause = (
            "최근 데이터 기준으로는 후처리 단계가 병목입니다. "
            "postprocess가 길다는 것은 모델 답변 이후의 가공 로직이 전체 응답 시간을 늘리고 있다는 뜻입니다."
        )
        action = "따라서 응답 포맷팅, 필터링, 후처리 코드를 먼저 줄이거나 최적화해야 합니다."
    else:
        cause = "최근 trace 데이터가 충분하지 않아 어느 단계가 가장 느린지 아직 단정하기 어렵습니다."
        action = "몇 번 더 요청을 보낸 뒤 다시 분석하는 것이 좋습니다."

    evidence = [
        f"최근 {window} 기준 평균 latency는 {_seconds(kpis.get('avg_latency_seconds'))}, p95 latency는 {_seconds(kpis.get('p95_latency_seconds'))}입니다.",
        f"단계별 p95 중 가장 큰 값은 {stage_name}={_seconds(stage_seconds)}입니다.",
    ]
    if stage_percent > 0:
        evidence.append(f"단계별 합계 기준으로 {stage_name}가 약 {stage_percent:.0f}%를 차지합니다.")
    if recent:
        evidence.append(
            f"최근 가장 느린 요청은 {recent.get('request_id')}이고 latency는 {_ms(recent.get('latency_ms'))}입니다."
        )

    return "\n\n".join([cause, "\n".join(f"- {item}" for item in evidence), action])


def _answer_cost(snapshot: dict[str, Any], window: str) -> str:
    kpis = snapshot.get("kpis", {})
    breakdowns = snapshot.get("breakdowns", {})
    top_token = _top_row(breakdowns.get("tokens_by_feature", []))
    top_cost = _top_row(breakdowns.get("cost_by_feature", []))
    token_cost = float(kpis.get("token_cost_usd") or 0.0)
    infra_cost = float(kpis.get("infra_cost_usd") or 0.0)

    if top_token:
        cause = (
            f"최근 {window} 기준으로 토큰을 가장 많이 쓴 기능은 {top_token['label']}입니다. "
            "이 기능의 입력 문맥이나 출력 답변이 길어지면서 전체 토큰 사용량이 늘어난 것이 비용 증가의 주된 원인입니다."
        )
    else:
        cause = "최근 토큰 사용 데이터를 아직 충분히 찾지 못했습니다."

    if infra_cost > token_cost:
        cost_reason = (
            "현재 모델은 로컬 gemma3:1b라서 OpenAI처럼 토큰당 API 비용이 붙지 않습니다. "
            "대신 토큰이 많아질수록 llm_call 실행 시간이 길어지고, 그만큼 CPU 기반 infra_cost_usd가 증가합니다."
        )
    else:
        cost_reason = "현재 비용 증가는 token_cost_usd와 infra_cost_usd를 함께 비교해서 봐야 합니다."

    evidence = [
        f"Total Tokens는 {_number(kpis.get('total_tokens'))}입니다.",
        f"Total Cost는 {_usd(kpis.get('estimated_cost_usd'))}입니다.",
        f"Token Cost는 {_usd(token_cost)}, Infra Cost는 {_usd(infra_cost)}입니다.",
    ]
    if top_cost:
        evidence.append(f"비용을 가장 많이 만든 기능은 {top_cost['label']}={_usd(top_cost['value'])}입니다.")

    return "\n\n".join([cause, "\n".join(f"- {item}" for item in evidence), cost_reason])


def _answer_error(snapshot: dict[str, Any], window: str) -> str:
    kpis = snapshot.get("kpis", {})
    recent = snapshot.get("recent_requests", [])
    errors = [row for row in recent if row.get("status") == "error"]
    if errors:
        latest_error = errors[0]
        cause = (
            f"최근 {window} 안에 실패 요청이 기록되어 있습니다. "
            f"가장 최근 실패 요청은 {latest_error.get('request_id')}이고, scenario는 {latest_error.get('scenario')}입니다."
        )
        evidence = [
            f"현재 error rate는 {_percent(kpis.get('error_rate_percent'))}입니다.",
            f"해당 trace_id는 {latest_error.get('trace_id')}입니다.",
            f"실패 요청 latency는 {_ms(latest_error.get('latency_ms'))}입니다.",
        ]
        action = "따라서 이 요청은 성공 응답 문제가 아니라 실제 실패 이벤트로 분류해야 하며, trace_id로 실패 단계까지 추적할 수 있습니다."
    else:
        cause = f"최근 {window} 기준으로 Jaeger 최근 요청 목록에서는 실패 요청이 뚜렷하게 보이지 않습니다."
        evidence = [f"현재 error rate는 {_percent(kpis.get('error_rate_percent'))}입니다."]
        action = "만약 방금 실패 시나리오를 실행했다면 trace export가 반영될 때까지 몇 초 뒤 다시 확인해야 합니다."
    return "\n\n".join([cause, "\n".join(f"- {item}" for item in evidence), action])


def _answer_overview(snapshot: dict[str, Any], window: str) -> str:
    kpis = snapshot.get("kpis", {})
    stages = _stage_summary(snapshot)
    top_stage = stages[0] if stages else {"label": "unknown", "value": 0.0}
    return (
        f"최근 {window} 기준 OLLY 상태는 요청 {_number(kpis.get('total_requests'))}건, "
        f"토큰 {_number(kpis.get('total_tokens'))}, 비용 {_usd(kpis.get('estimated_cost_usd'))} 수준입니다.\n\n"
        f"평균 latency는 {_seconds(kpis.get('avg_latency_seconds'))}, p95 latency는 {_seconds(kpis.get('p95_latency_seconds'))}입니다. "
        f"현재 가장 큰 병목 후보는 {top_stage['label']} 단계이며 p95는 {_seconds(top_stage['value'])}입니다.\n\n"
        "즉, OLLY는 단순히 답변을 생성하는 것이 아니라 최근 metric과 trace를 근거로 운영 상태를 설명합니다."
    )


def _stage_summary(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rows = snapshot.get("breakdowns", {}).get("stage_p95_seconds", [])
    return sorted(
        [row for row in rows if row.get("label") in {"retrieve", "llm_call", "postprocess"}],
        key=lambda row: float(row.get("value") or 0.0),
        reverse=True,
    )


def _stage_percent(stage_seconds: float, stages: list[dict[str, Any]]) -> float:
    total = sum(float(row.get("value") or 0.0) for row in stages)
    if total <= 0:
        return 0.0
    return stage_seconds / total * 100


def _slowest_recent_trace(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    rows = snapshot.get("recent_requests", [])
    if not rows:
        return None
    return max(rows, key=lambda row: float(row.get("latency_ms") or 0.0))


def _top_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    meaningful_rows = [row for row in rows if float(row.get("value") or 0.0) > 0]
    if not meaningful_rows:
        return None
    return max(meaningful_rows, key=lambda row: float(row.get("value") or 0.0))


def _seconds(value: Any) -> str:
    seconds = float(value or 0.0)
    if seconds >= 1:
        return f"{seconds:.2f}초"
    return f"{seconds * 1000:.0f}ms"


def _ms(value: Any) -> str:
    ms = float(value or 0.0)
    if ms >= 1000:
        return f"{ms / 1000:.2f}초"
    return f"{ms:.0f}ms"


def _number(value: Any) -> str:
    number = float(value or 0.0)
    if number >= 1_000_000:
        return f"{number / 1_000_000:.2f}M"
    if number >= 1_000:
        return f"{number / 1_000:.1f}k"
    return f"{number:.0f}"


def _usd(value: Any) -> str:
    return f"${float(value or 0.0):.6f}"


def _percent(value: Any) -> str:
    return f"{float(value or 0.0):.2f}%"
