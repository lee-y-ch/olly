from app.pricing import estimate_tokens
from app.schemas import ChatRequest


UNHELPFUL_ANSWERS = {
    "",
    "모른다",
    "모릅니다",
    "모른다고 합니다.",
    "모른다고 합니다",
    "모른다.",
    "모릅니다.",
    "저는 실패하지 않았습니다.",
}


def is_unhelpful_answer(answer: str) -> bool:
    normalized = " ".join(answer.strip().split())
    if normalized in UNHELPFUL_ANSWERS:
        return True
    return len(normalized) < 12 and "모" in normalized and "른" in normalized


def build_demo_context(request: ChatRequest) -> list[str]:
    base_context = [
        "OLLY는 LLM 서비스의 비용, 토큰 사용량, 응답 시간, 병목 단계를 관측하는 플랫폼입니다.",
        "현재 사용자 화면은 /chat-ui이고, 운영자 대시보드는 /dashboard입니다.",
        "현재 로컬 모델은 Ollama gemma3:1b입니다.",
        "로컬 모델은 외부 API 토큰 비용이 없으므로 token_cost_usd는 0입니다.",
        "로컬 모델 비용은 LLM 실행 시간(초) / 3600 * 시간당 장비 비용으로 추정합니다.",
        "OLLY는 요청마다 request_id와 trace_id를 만들고, 운영자 대시보드 Recent Requests에서 추적합니다.",
        "요청 처리 단계는 retrieve, llm_call, postprocess입니다.",
        "retrieve가 길면 RAG 검색 또는 문서 조회가 병목입니다.",
        "llm_call이 길면 LLM 답변 생성이 병목입니다.",
        "postprocess가 길면 응답 후처리 로직이 병목입니다.",
        "토큰 사용량이 많으면 Total Tokens와 Total Cost가 증가합니다.",
        "실패 요청은 status=error로 기록되고 에러율 지표에 반영됩니다.",
    ]
    scenario_context = {
        "normal": [
            "normal 시나리오는 정상 요청입니다. 대시보드에는 낮은 latency와 success 상태로 표시됩니다.",
        ],
        "slow_retrieve": [
            "slow_retrieve 시나리오는 retrieve 단계를 일부러 느리게 만든 데모입니다.",
            "이 경우 OpenAI나 로컬 LLM보다 RAG 검색 단계가 느린 것으로 설명해야 합니다.",
        ],
        "slow_llm": [
            "slow_llm 시나리오는 llm_call 단계를 일부러 느리게 만든 데모입니다.",
            "이 경우 검색보다 LLM Generation 단계가 병목이라고 설명해야 합니다.",
        ],
        "high_token": [
            "high_token 시나리오는 토큰을 많이 쓰는 요청을 재현합니다.",
            "긴 프롬프트나 긴 답변을 만드는 기능은 토큰 사용량과 추론 시간이 늘어 비용 추정치가 커집니다.",
        ],
        "error": [
            "error 시나리오는 실패 요청을 재현합니다.",
            "실패 요청도 Recent Requests와 error metric에 기록됩니다.",
        ],
    }
    return base_context + scenario_context.get(request.scenario, [])


def build_demo_answer(request: ChatRequest) -> str:
    question = request.question.strip()
    if request.scenario == "slow_retrieve":
        return (
            "현재 요청은 LLM 자체보다 RAG 검색 단계가 느린 상황으로 보면 됩니다.\n\n"
            "- 대시보드의 Recent Requests에서 이 요청을 클릭하세요.\n"
            "- Trace Detail에서 Retrieve 막대가 가장 길게 표시됩니다.\n"
            "- 이것은 답변 생성 전에 관련 문서를 찾는 단계가 병목이라는 뜻입니다.\n"
            "- 따라서 우선 확인할 곳은 OpenAI나 gemma3:1b가 아니라 벡터 검색, 문서 조회, 인덱스 설정입니다.\n\n"
            "발표에서는 '사용자는 그냥 질문했지만, OLLY는 retrieve / llm_call / postprocess 중 어디가 느린지 보여준다'고 설명하면 됩니다."
        )

    if request.scenario == "slow_llm":
        return (
            "현재 요청은 LLM Generation 단계가 병목인 상황입니다.\n\n"
            "- Retrieve 단계가 짧고 LLM Generation 막대가 길면 검색은 정상입니다.\n"
            "- 병목은 gemma3:1b가 답변을 생성하는 llm_call 구간에 있습니다.\n"
            "- 원인은 모델 크기, CPU/GPU 성능, 긴 프롬프트, 긴 출력 길이일 수 있습니다.\n\n"
            "운영자는 이 정보를 보고 검색 시스템을 고칠지, 모델 추론 환경을 개선할지 구분할 수 있습니다."
        )

    if request.scenario == "high_token" or "토큰" in question or "비용" in question:
        return (
            "비용이나 토큰이 늘어난 원인은 대시보드에서 기능별로 확인해야 합니다.\n\n"
            "- Total Tokens는 전체 입력/출력 토큰 사용량입니다.\n"
            "- Total Cost는 로컬 gemma3:1b 실행 시간 기반 추정 비용입니다.\n"
            "- Cost Analysis에서 어떤 feature가 비용을 많이 만들었는지 확인합니다.\n"
            "- High Token Usage 요청은 보통 긴 질문, 긴 답변, 요약 기능, RAG 문맥 증가 때문에 발생합니다.\n\n"
            "현재 로컬 모델은 API 토큰 과금이 없어서 token_cost_usd는 0이고, infra_cost_usd만 증가합니다."
        )

    if request.scenario == "error" or "실패" in question or "에러" in question:
        return (
            "실패 요청은 운영자 대시보드에서 ERROR 상태로 확인해야 합니다.\n\n"
            "- Recent Requests에서 status가 ERROR인 요청을 찾습니다.\n"
            "- request_id와 trace_id로 Jaeger 원본 trace까지 따라갈 수 있습니다.\n"
            "- 에러율은 Prometheus metric과 Active Alerts에 반영됩니다.\n\n"
            "즉, OLLY는 성공한 요청뿐 아니라 실패한 요청도 운영 분석 대상으로 기록합니다."
        )

    if "rag" in question.lower() or "openai" in question.lower() or "느린" in question:
        return (
            "응답이 느릴 때는 먼저 병목 단계를 나눠서 봐야 합니다.\n\n"
            "- Retrieve가 길면 RAG 검색이나 문서 조회가 느린 것입니다.\n"
            "- LLM Generation이 길면 모델 호출 또는 답변 생성이 느린 것입니다.\n"
            "- Post-process가 길면 응답 후처리 코드가 느린 것입니다.\n\n"
            "이 요청의 trace_id를 대시보드 Recent Requests에서 선택하면 어느 단계가 가장 긴지 확인할 수 있습니다."
        )

    return (
        "OLLY는 LLM 서비스의 운영 상태를 확인하는 관측성 대시보드입니다.\n\n"
        "- 사용자는 /chat-ui에서 질문합니다.\n"
        "- OLLY는 요청마다 토큰, 비용, latency, request_id, trace_id를 기록합니다.\n"
        "- 운영자는 /dashboard에서 최근 요청과 단계별 병목을 확인합니다.\n"
        "- retrieve, llm_call, postprocess 중 어느 단계가 느린지 구분할 수 있습니다."
    )


def estimate_demo_output_tokens(answer: str) -> int:
    return estimate_tokens(answer)
