from collections.abc import Callable
from typing import Any

from app.dashboard import collect_dashboard_summary, dashboard_trace
from app.analysis_intents import (
    ERROR_KEYWORDS,
    LATENCY_KEYWORDS,
    TOKEN_KEYWORDS,
    classify_intent,
    contains,
    extract_request_id,
    extract_trace_id,
    extract_window,
)
from app.analysis_metrics import MetricComparison, collect_period_comparison
from app.schemas import ChatRequest


async def build_observability_answer(request: ChatRequest, window: str = "1h") -> str | None:
    intent = classify_intent(request)
    if intent is None:
        return None

    window = extract_window(request.question, window)
    if intent == "intro":
        return _answer_intro(detailed=_wants_detailed_intro(request))

    snapshot = await collect_dashboard_summary(window)
    if intent == "trace_detail":
        return await _answer_trace_detail(request.question, snapshot, window)
    if intent == "compare":
        comparison = await collect_period_comparison(window)
        return _answer_comparison(snapshot, comparison, window, request.question)
    if intent == "cost":
        return _answer_cost(snapshot, window, request.question)
    handler = SUMMARY_HANDLERS.get(intent, _answer_overview)
    return handler(snapshot, window)


def is_observability_question(request: ChatRequest) -> bool:
    return classify_intent(request) is not None


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
        cause = "최근 트레이스 데이터가 충분하지 않아 어느 단계가 가장 느린지 아직 단정하기 어렵습니다."
        action = "몇 번 더 요청을 보낸 뒤 다시 분석하는 것이 좋습니다."

    evidence = [
        f"최근 {window} 기준 평균 응답 시간은 {_seconds(kpis.get('avg_latency_seconds'))}, p95 응답 시간은 {_seconds(kpis.get('p95_latency_seconds'))}입니다.",
        f"단계별 p95 중 가장 큰 값은 {stage_name}={_seconds(stage_seconds)}입니다.",
    ]
    if stage_percent > 0:
        evidence.append(f"단계별 합계 기준으로 {stage_name}가 약 {stage_percent:.0f}%를 차지합니다.")
    if recent:
        evidence.append(
            f"최근 가장 느린 요청은 {recent.get('request_id')}이고 응답 시간은 {_ms(recent.get('latency_ms'))}입니다."
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
        f"총 토큰은 {_number(kpis.get('total_tokens'))}입니다.",
        f"총 비용은 {_usd(kpis.get('estimated_cost_usd'))}입니다.",
        f"토큰 비용은 {_usd(token_cost)}, 인프라 비용은 {_usd(infra_cost)}입니다.",
    ]
    if top_cost:
        evidence.append(f"비용을 가장 많이 만든 기능은 {top_cost['label']}={_usd(top_cost['value'])}입니다.")
    if top_token:
        evidence.append(f"참고로 토큰을 가장 많이 쓴 기능은 {top_token['label']}={_number(top_token['value'])}입니다.")

    if contains(question.lower(), ("어제", "yesterday", "2배", "전일")):
        evidence.append("현재 MVP 답변은 전일 대비 계산이 아니라 대시보드의 최근 수집 구간 기준 원인 분석입니다.")

    return "\n\n".join([cause, "\n".join(f"- {item}" for item in evidence), cost_reason])


def _answer_comparison(
    snapshot: dict[str, Any], comparison: dict[str, MetricComparison], window: str, question: str
) -> str:
    text = question.lower()
    metric_name = "estimated_cost_usd"
    label = "비용"
    formatter = _usd
    if contains(text, TOKEN_KEYWORDS):
        metric_name = "total_tokens"
        label = "토큰"
        formatter = _number
    elif contains(text, LATENCY_KEYWORDS):
        metric_name = "avg_latency_seconds"
        label = "평균 응답 시간"
        formatter = _seconds
    elif contains(text, ERROR_KEYWORDS):
        metric_name = "error_rate_percent"
        label = "오류율"
        formatter = _percent
    elif contains(text, ("요청", "request", "트래픽")):
        metric_name = "total_requests"
        label = "요청 수"
        formatter = _number

    row = comparison.get(metric_name, MetricComparison(0.0, 0.0, 0.0, 0.0))
    current = row.current
    previous = row.previous
    delta = row.delta
    change = row.change_percent
    direction = "증가" if delta > 0 else "감소" if delta < 0 else "변화 없음"

    cause = _comparison_cause(snapshot, metric_name)
    evidence = [
        f"현재 {window} {label}: {formatter(current)}",
        f"이전 {window} {label}: {formatter(previous)}",
        f"변화량: {formatter(abs(delta))} {direction}",
    ]
    if previous > 0:
        evidence.append(f"변화율: {change:+.1f}%")
    else:
        evidence.append("이전 구간 값이 0이라 정확한 배수/증가율 계산은 제한됩니다.")

    return "\n\n".join(
        [
            f"{label}은 현재 {window} 기준으로 이전 같은 길이의 구간과 비교해 {direction}했습니다.",
            "\n".join(f"- {item}" for item in evidence),
            cause,
        ]
    )


def _comparison_cause(snapshot: dict[str, Any], metric_name: str) -> str:
    breakdowns = snapshot.get("breakdowns", {})
    if metric_name in {"estimated_cost_usd", "total_tokens"}:
        top_tokens = _top_row(breakdowns.get("tokens_by_feature", []))
        top_cost = _top_row(breakdowns.get("cost_by_feature", []))
        parts = []
        if top_cost:
            parts.append(f"비용 기여 1위는 {top_cost['label']}={_usd(top_cost['value'])}입니다.")
        if top_tokens:
            parts.append(f"토큰 사용 1위는 {top_tokens['label']}={_number(top_tokens['value'])}입니다.")
        parts.append("로컬 gemma3:1b에서는 토큰 API 과금보다 실행 시간 기반 infra_cost가 더 중요합니다.")
        return " ".join(parts)
    if metric_name == "avg_latency_seconds":
        stages = _stage_summary(snapshot)
        top = stages[0] if stages else {"label": "unknown", "value": 0.0}
        return f"지연 원인 후보는 {top['label']} 단계입니다. 단계 p95는 {_seconds(top['value'])}입니다."
    if metric_name == "error_rate_percent":
        return "실패 원인은 최근 요청의 실패 항목과 해당 트레이스 ID를 열어 확인해야 합니다."
    return "요청 수 변화는 기능별 트래픽 증가나 데모 시나리오 실행 횟수와 함께 봐야 합니다."


def _answer_top_costs(snapshot: dict[str, Any], window: str) -> str:
    rows = snapshot.get("breakdowns", {}).get("cost_by_feature", [])
    top_cost = _top_row(rows)
    if not top_cost:
        return f"최근 {window} 기준으로는 기능별 비용 데이터를 아직 충분히 찾지 못했습니다."
    lines = _rank_lines(rows, _usd)
    return "\n\n".join(
        [
            f"최근 {window} 기준 비용을 가장 많이 만든 기능은 {top_cost['label']}입니다.",
            "\n".join(lines),
            "로컬 모델에서는 이 비용이 OpenAI API 과금이 아니라 실행 시간 기반 infra_cost 중심으로 계산됩니다.",
        ]
    )


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
        action = "따라서 두 단계의 트레이스를 함께 보고 요청별로 어느 쪽이 튀는지 확인해야 합니다."

    evidence = [
        f"retrieve p95는 {_seconds(retrieve)}입니다.",
        f"llm_call p95는 {_seconds(llm_call)}입니다.",
    ]
    if recent:
        evidence.append(f"최근 가장 느린 요청은 {recent.get('request_id')}이고 응답 시간은 {_ms(recent.get('latency_ms'))}입니다.")

    return "\n\n".join([verdict, "\n".join(f"- {item}" for item in evidence), cause, action])


async def _answer_trace_detail(question: str, snapshot: dict[str, Any], window: str) -> str:
    trace_id = extract_trace_id(question)
    request_id = extract_request_id(question)
    trace_data: dict[str, Any] | None = None

    if trace_id:
        trace_data = await dashboard_trace(trace_id)
        if not trace_data.get("found"):
            return f"트레이스 ID {trace_id}를 Jaeger에서 찾지 못했습니다. 최근 {window} 안에 수집된 트레이스인지 먼저 확인해야 합니다."
    else:
        recent = snapshot.get("recent_requests", [])
        if request_id:
            trace_data = next((row for row in recent if str(row.get("request_id")).lower() == request_id.lower()), None)
        if trace_data is None:
            trace_data = _slowest_recent_trace(snapshot)
        if trace_data is None:
            return f"최근 {window} 안에서 분석할 요청 데이터를 찾지 못했습니다."

    stages = trace_data.get("stages", [])
    slowest = max(stages, key=lambda row: float(row.get("duration_ms") or 0.0), default={"name": "unknown", "duration_ms": 0})
    status = trace_data.get("status", "unknown")
    evidence = [
        f"요청 ID: {trace_data.get('request_id')}",
        f"트레이스 ID: {trace_data.get('trace_id')}",
        f"status: {status}",
        f"응답 시간: {_ms(trace_data.get('latency_ms'))}",
        f"토큰: {_number(trace_data.get('tokens'))}",
        f"비용: {_usd(trace_data.get('cost_usd'))}",
        f"가장 긴 단계: {slowest.get('name')}={_ms(slowest.get('duration_ms'))}",
    ]
    return "\n\n".join(
        [
            f"이 요청의 핵심 원인은 {slowest.get('name')} 단계입니다.",
            "\n".join(f"- {item}" for item in evidence),
            _stage_action(str(slowest.get("name"))),
        ]
    )


def _answer_alerts(snapshot: dict[str, Any], window: str) -> str:
    alerts = snapshot.get("alerts", [])
    if not alerts:
        kpis = snapshot.get("kpis", {})
        return "\n\n".join(
            [
                f"현재 Prometheus 기준 활성 알림은 없습니다.",
                "\n".join(
                    [
                        f"- 최근 {window} 오류율: {_percent(kpis.get('error_rate_percent'))}",
                        f"- 최근 {window} p95 응답 시간: {_seconds(kpis.get('p95_latency_seconds'))}",
                    ]
                ),
                "따라서 지금은 알림이 울린 상태라기보다 일반 성능/비용 지표를 확인하는 상태입니다.",
            ]
        )
    lines = [
        f"- {alert.get('name')} / {alert.get('state')} / {alert.get('severity')}: {alert.get('summary')}"
        for alert in alerts
    ]
    return "\n\n".join(["현재 활성 알림이 있습니다.", "\n".join(lines), "먼저 같은 시간대의 최근 요청과 트레이스 ID를 확인해야 합니다."])


def _answer_models(snapshot: dict[str, Any], window: str) -> str:
    rows = snapshot.get("breakdowns", {}).get("cost_by_model", [])
    if not rows:
        return f"최근 {window} 기준 모델별 데이터를 찾지 못했습니다."
    top = _top_row(rows)
    evidence = _rank_lines(rows, _usd)
    return "\n\n".join(
        [
            f"최근 {window} 기준 가장 비용이 큰 모델은 {top['label']}입니다.",
            "\n".join(evidence),
            "현재 구성은 로컬 gemma3:1b 중심이므로 모델별 비용 차이는 API 단가보다 실행 시간 차이로 해석해야 합니다.",
        ]
    )


def _answer_ranking(snapshot: dict[str, Any], window: str) -> str:
    breakdowns = snapshot.get("breakdowns", {})
    sections = [
        ("비용 상위 기능", _rank_lines(breakdowns.get("cost_by_feature", []), _usd)),
        ("토큰 상위 기능", _rank_lines(breakdowns.get("tokens_by_feature", []), _number)),
        ("단계별 p95 응답 시간", _rank_lines(breakdowns.get("stage_p95_seconds", []), _seconds)),
    ]
    rendered = []
    for title, lines in sections:
        if lines:
            rendered.append(title + "\n" + "\n".join(lines))
    if not rendered:
        return f"최근 {window} 기준 랭킹을 만들 데이터가 아직 충분하지 않습니다."
    return f"최근 {window} 기준 운영 랭킹입니다.\n\n" + "\n\n".join(rendered)


def _answer_slowest_requests(snapshot: dict[str, Any], window: str) -> str:
    rows = sorted(
        snapshot.get("recent_requests", []),
        key=lambda row: float(row.get("latency_ms") or 0.0),
        reverse=True,
    )[:5]
    if not rows:
        return f"최근 {window} 안에서 요청 목록을 찾지 못했습니다."
    lines = [
        f"- {row.get('request_id')} / {_ms(row.get('latency_ms'))} / {row.get('feature')} / {row.get('status')} / trace={row.get('trace_id')}"
        for row in rows
    ]
    slowest = rows[0]
    stages = slowest.get("stages", [])
    slow_stage = max(stages, key=lambda stage: float(stage.get("duration_ms") or 0.0), default={"name": "unknown"})
    return "\n\n".join(
        [
            f"최근 {window} 기준 가장 느린 요청은 {slowest.get('request_id')}입니다.",
            "\n".join(lines),
            f"가장 느린 요청의 병목 후보는 {slow_stage.get('name')} 단계입니다.",
        ]
    )


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
            f"현재 오류율은 {_percent(kpis.get('error_rate_percent'))}입니다.",
            f"해당 trace_id는 {latest_error.get('trace_id')}입니다.",
            f"실패 요청 latency는 {_ms(latest_error.get('latency_ms'))}입니다.",
        ]
        action = "따라서 이 요청은 성공 응답 문제가 아니라 실제 실패 이벤트로 분류해야 하며, trace_id로 실패 단계까지 추적할 수 있습니다."
    else:
        cause = f"최근 {window} 기준으로 Jaeger 최근 요청 목록에서는 실패 요청이 뚜렷하게 보이지 않습니다."
        evidence = [f"현재 오류율은 {_percent(kpis.get('error_rate_percent'))}입니다."]
        action = "만약 방금 실패 시나리오를 실행했다면 trace export가 반영될 때까지 몇 초 뒤 다시 확인해야 합니다."
    return "\n\n".join([cause, "\n".join(f"- {item}" for item in evidence), action])


def _answer_overview(snapshot: dict[str, Any], window: str) -> str:
    kpis = snapshot.get("kpis", {})
    stages = _stage_summary(snapshot)
    top_stage = stages[0] if stages else {"label": "unknown", "value": 0.0}
    return (
        f"최근 {window} 기준 OLLY 상태는 요청 {_number(kpis.get('total_requests'))}건, "
        f"토큰 {_number(kpis.get('total_tokens'))}, 비용 {_usd(kpis.get('estimated_cost_usd'))} 수준입니다.\n\n"
        f"평균 응답 시간은 {_seconds(kpis.get('avg_latency_seconds'))}, p95 응답 시간은 {_seconds(kpis.get('p95_latency_seconds'))}입니다. "
        f"현재 가장 큰 병목 후보는 {top_stage['label']} 단계이며 p95는 {_seconds(top_stage['value'])}입니다.\n\n"
        "즉, OLLY는 단순히 답변을 생성하는 것이 아니라 최근 metric과 trace를 근거로 운영 상태를 설명합니다."
    )


def _wants_detailed_intro(request: ChatRequest) -> bool:
    question = request.question.lower()
    return request.scenario == "high_token" or contains(question, ("긴", "길게", "자세", "상세"))


def _answer_intro(*, detailed: bool = False) -> str:
    if not detailed:
        return (
            "OLLY는 LLM 서비스의 운영 상태를 확인하기 위한 관측성 대시보드와 분석 챗봇입니다.\n\n"
            "사용자가 질문을 보내면 OLLY는 답변만 보여주는 것이 아니라 request_id, trace_id, 응답 시간, 토큰, 비용, 실패 여부를 함께 기록합니다.\n\n"
            "그래서 운영자는 요청이 느릴 때 RAG 검색이 문제인지, 모델 답변 생성이 문제인지, 토큰 사용량이나 실패가 원인인지 대시보드와 trace로 확인할 수 있습니다."
        )

    return (
        "OLLY는 LLM 서비스를 운영할 때 필요한 관측성 대시보드와 분석 챗봇입니다. "
        "일반 챗봇은 사용자의 질문에 답변만 돌려주지만, OLLY는 그 요청이 내부에서 어떻게 처리됐는지까지 함께 기록합니다. "
        "각 요청에는 request_id와 trace_id가 붙고, 응답 시간, 입력 토큰, 출력 토큰, 비용, 성공 또는 실패 상태가 저장됩니다.\n\n"
        "첫 번째 기능은 요청 추적입니다. 운영자는 사용자가 보낸 특정 요청을 request_id로 찾고, 같은 요청의 trace_id를 통해 Jaeger에서 세부 실행 흐름을 확인할 수 있습니다. "
        "요청은 retrieve, llm_call, postprocess 단계로 나뉘며, 각 단계가 몇 초 걸렸는지 비교할 수 있습니다. "
        "그래서 응답이 느릴 때 단순히 'LLM이 느리다'고 추측하지 않고, RAG 검색이 느린지, 모델 생성이 느린지, 후처리 로직이 느린지 구분할 수 있습니다.\n\n"
        "두 번째 기능은 비용과 토큰 분석입니다. OLLY는 기능별 토큰 사용량과 비용 추정치를 보여줍니다. "
        "현재 로컬 gemma3:1b 모델은 외부 API 토큰 과금이 없기 때문에 token_cost_usd는 0에 가깝고, 대신 모델 실행 시간에 기반한 infra_cost_usd를 계산합니다. "
        "토큰이 많은 요청은 처리 시간이 길어지고, 그 결과 로컬 추론 비용 추정치도 커질 수 있습니다.\n\n"
        "세 번째 기능은 병목 분석입니다. 대시보드는 최근 요청 목록과 trace detail을 함께 보여주며, retrieve, llm_call, postprocess 중 가장 오래 걸린 단계를 강조합니다. "
        "retrieve가 길면 문서 검색, 벡터 DB 인덱스, top_k, 청크 크기 같은 RAG 파이프라인을 먼저 점검해야 합니다. "
        "llm_call이 길면 프롬프트 길이, 출력 토큰 수, 모델 크기, CPU 또는 GPU 자원을 확인해야 합니다.\n\n"
        "네 번째 기능은 사용자 정의 알림입니다. 운영자는 대시보드에서 직접 알림 규칙을 만들 수 있습니다. "
        "요청 수, 토큰 수, p95 응답 시간, 에러율, 추정 비용, retrieve p95 같은 지표를 선택하고, 임계값과 평가 윈도우를 설정한 뒤 Discord webhook을 연결할 수 있습니다. "
        "조건이 만족되면 OLLY가 Prometheus 지표를 평가해 Discord로 알림을 보내고, gemma3:1b가 만든 한 줄 요약도 함께 첨부합니다.\n\n"
        "정리하면 OLLY는 LLM 서비스에서 발생하는 지연, 토큰 증가, 비용 증가, 실패 요청을 request 단위로 추적하고 설명하는 MVP입니다. "
        "운영자는 OLLY를 통해 문제가 생긴 요청을 찾고, trace로 병목 단계를 확인하고, 알림으로 장애 징후를 빠르게 받을 수 있습니다."
    )


SUMMARY_HANDLERS: dict[str, Callable[[dict[str, Any], str], str]] = {
    "alerts": _answer_alerts,
    "error": _answer_error,
    "top_tokens": _answer_top_tokens,
    "top_costs": _answer_top_costs,
    "models": _answer_models,
    "ranking": _answer_ranking,
    "slowest_requests": _answer_slowest_requests,
    "rag_vs_llm": _answer_rag_vs_llm,
    "latency": _answer_latency,
    "overview": _answer_overview,
}


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


def _rank_lines(rows: list[dict[str, Any]], formatter: Any, limit: int = 5) -> list[str]:
    ranked = sorted(
        [row for row in rows if float(row.get("value") or 0.0) > 0],
        key=lambda row: float(row.get("value") or 0.0),
        reverse=True,
    )[:limit]
    return [f"- {index}. {row.get('label')}: {formatter(row.get('value'))}" for index, row in enumerate(ranked, 1)]


def _stage_action(stage_name: str) -> str:
    if stage_name == "retrieve":
        return "retrieve가 가장 길면 RAG 검색, 문서 조회, 벡터 DB 인덱스, top_k 설정을 먼저 확인해야 합니다."
    if stage_name == "llm_call":
        return "llm_call이 가장 길면 프롬프트 길이, 출력 길이, CPU/GPU 성능, 모델 크기를 먼저 확인해야 합니다."
    if stage_name == "postprocess":
        return "postprocess가 가장 길면 응답 포맷팅, 필터링, 후처리 로직을 먼저 확인해야 합니다."
    return "단계명이 명확하지 않으므로 Jaeger trace에서 span 구조를 먼저 확인해야 합니다."


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
