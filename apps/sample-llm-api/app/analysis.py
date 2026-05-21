from typing import Any

from app.dashboard import collect_dashboard_summary
from app.schemas import ChatRequest


LATENCY_KEYWORDS = ("느려", "느린", "느림", "지연", "latency", "병목", "bottleneck", "응답")
COST_KEYWORDS = ("비용", "cost", "2배", "증가", "올랐", "비싸")
TOKEN_KEYWORDS = ("토큰", "token")
TOP_FEATURE_KEYWORDS = ("어떤 기능", "무슨 기능", "가장 많이", "많이 쓰", "최다", "top")
RAG_VS_LLM_KEYWORDS = ("rag", "openai", "llm", "모델", "검색", "답변 생성")
ERROR_KEYWORDS = ("실패", "에러", "오류", "error", "fail")


async def build_observability_answer(request: ChatRequest, window: str = "1h") -> str | None:
    intent = _classify_intent(request)
    if intent is None:
        return None

    snapshot = await collect_dashboard_summary(window)
    if intent == "error":
        return _answer_error(snapshot, window)
    if intent == "top_tokens":
        return _answer_top_tokens(snapshot, window)
    if intent == "cost":
        return _answer_cost(snapshot, window, request.question)
    if intent == "rag_vs_llm":
        return _answer_rag_vs_llm(snapshot, window)
    if intent == "latency":
        return _answer_latency(snapshot, window)
    return _answer_overview(snapshot, window)


def is_observability_question(request: ChatRequest) -> bool:
    return _classify_intent(request) is not None


def _classify_intent(request: ChatRequest) -> str | None:
    question = request.question.lower()
    has_token = _contains(question, TOKEN_KEYWORDS)
    asks_top_feature = _contains(question, TOP_FEATURE_KEYWORDS) or "기능" in question
    has_cost = _contains(question, COST_KEYWORDS)
    has_latency = _contains(question, LATENCY_KEYWORDS)
    mentions_rag_or_llm = _contains(question, RAG_VS_LLM_KEYWORDS)

    if _contains(question, ERROR_KEYWORDS):
        return "error"
    if has_token and asks_top_feature:
        return "top_tokens"
    if has_cost:
        return "cost"
    if mentions_rag_or_llm and (has_latency or "느린 것" in question):
        return "rag_vs_llm"
    if has_latency:
        return "latency"

    if request.scenario == "high_token":
        return "top_tokens"
    if request.scenario == "error":
        return "error"
    if request.scenario in {"slow_retrieve", "slow_llm"}:
        return "latency"
    return (
        "overview"
        if request.scenario != "normal" or "olly" in question or "대시보드" in question
        else None
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


def _answer_cost(snapshot: dict[str, Any], window: str, question: str = "") -> str:
    kpis = snapshot.get("kpis", {})
    breakdowns = snapshot.get("breakdowns", {})
    top_token = _top_row(breakdowns.get("tokens_by_feature", []))
    top_cost = _top_row(breakdowns.get("cost_by_feature", []))
    token_cost = float(kpis.get("token_cost_usd") or 0.0)
    infra_cost = float(kpis.get("infra_cost_usd") or 0.0)

    if top_cost:
        cause = (
            f"최근 {window} 기준으로 비용을 가장 많이 만든 기능은 {top_cost['label']}입니다. "
            "현재 비용 증가는 이 기능에서 로컬 모델 실행 시간이 많이 쌓인 것이 주된 원인입니다."
        )
    else:
        cause = "최근 비용 데이터를 아직 충분히 찾지 못했습니다."

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
    if top_token:
        evidence.append(f"참고로 토큰을 가장 많이 쓴 기능은 {top_token['label']}={_number(top_token['value'])}입니다.")

    if _contains(question.lower(), ("어제", "yesterday", "2배", "전일")):
        evidence.append("현재 MVP 답변은 전일 대비 계산이 아니라 대시보드의 최근 수집 구간 기준 원인 분석입니다.")

    return "\n\n".join([cause, "\n".join(f"- {item}" for item in evidence), cost_reason])


def _answer_top_tokens(snapshot: dict[str, Any], window: str) -> str:
    kpis = snapshot.get("kpis", {})
    rows = snapshot.get("breakdowns", {}).get("tokens_by_feature", [])
    top_token = _top_row(rows)
    if not top_token:
        return f"최근 {window} 기준으로는 기능별 토큰 사용량 데이터를 아직 충분히 찾지 못했습니다."

    ordered = sorted(rows, key=lambda row: float(row.get("value") or 0.0), reverse=True)
    top_value = float(top_token.get("value") or 0.0)
    total_tokens = float(kpis.get("total_tokens") or 0.0)
    share = top_value / total_tokens * 100 if total_tokens > 0 else 0.0
    evidence = [
        f"1위 기능은 {top_token['label']}이고 사용 토큰은 {_number(top_value)}입니다.",
        f"전체 토큰 {_number(total_tokens)} 중 약 {share:.0f}%를 차지합니다.",
    ]
    if len(ordered) > 1:
        runner_up = ordered[1]
        evidence.append(f"2위는 {runner_up['label']}={_number(runner_up['value'])}입니다.")

    return "\n\n".join(
        [
            f"최근 {window} 기준으로 토큰을 가장 많이 쓴 기능은 {top_token['label']}입니다.",
            "\n".join(f"- {item}" for item in evidence),
            "따라서 이 질문의 답은 비용 전체가 아니라 기능별 토큰 사용량 기준으로 보면 됩니다. 해당 기능의 입력 문맥 길이와 출력 답변 길이를 먼저 줄이는 것이 직접적인 개선 포인트입니다.",
        ]
    )


def _answer_rag_vs_llm(snapshot: dict[str, Any], window: str) -> str:
    stages = _stage_summary(snapshot)
    stage_map = {str(row.get("label")): float(row.get("value") or 0.0) for row in stages}
    retrieve = stage_map.get("retrieve", 0.0)
    llm_call = stage_map.get("llm_call", 0.0)
    recent = _slowest_recent_trace(snapshot)

    if retrieve <= 0 and llm_call <= 0:
        return f"최근 {window} 기준으로는 retrieve와 llm_call 단계 데이터를 아직 충분히 찾지 못했습니다."

    if retrieve > llm_call:
        verdict = "최근 데이터 기준으로는 OpenAI/모델 호출보다 우리 RAG 검색 단계가 더 느립니다."
        cause = "retrieve가 더 크다는 것은 답변을 만들기 전 문서 검색, 벡터 DB 조회, 검색 결과 구성에서 시간이 더 많이 쓰였다는 뜻입니다."
        action = "따라서 먼저 확인할 곳은 벡터 DB 인덱스, 검색 top_k, 문서 청크 크기, 검색 필터 조건입니다."
    elif llm_call > retrieve:
        verdict = "최근 데이터 기준으로는 우리 RAG 검색보다 LLM 답변 생성 단계가 더 느립니다."
        cause = "llm_call이 더 크다는 것은 gemma3:1b가 프롬프트를 처리하고 답변을 생성하는 시간이 더 많이 쓰였다는 뜻입니다."
        action = "따라서 먼저 확인할 곳은 프롬프트 길이, 출력 길이, CPU/GPU 성능, 모델 크기입니다."
    else:
        verdict = "최근 데이터 기준으로는 RAG 검색과 LLM 답변 생성 시간이 거의 비슷합니다."
        cause = "retrieve와 llm_call p95가 비슷해서 한쪽만 병목이라고 보기 어렵습니다."
        action = "따라서 두 단계의 trace를 함께 보고 요청별로 어느 쪽이 튀는지 확인해야 합니다."

    evidence = [
        f"retrieve p95는 {_seconds(retrieve)}입니다.",
        f"llm_call p95는 {_seconds(llm_call)}입니다.",
    ]
    if recent:
        evidence.append(f"최근 가장 느린 요청은 {recent.get('request_id')}이고 latency는 {_ms(recent.get('latency_ms'))}입니다.")

    return "\n\n".join([verdict, "\n".join(f"- {item}" for item in evidence), cause, action])


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
