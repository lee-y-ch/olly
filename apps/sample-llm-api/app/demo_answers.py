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
            "OpenAI나 gemma3:1b가 느린 것이 아니라, 우리 RAG 검색 단계가 느린 상황입니다.\n\n"
            "이 요청은 답변을 만들기 전에 관련 문서를 찾는 retrieve 단계에서 시간이 많이 걸렸습니다. "
            "LLM은 retrieve가 끝난 뒤에야 답변 생성을 시작할 수 있기 때문에, 검색 단계가 늦어지면 전체 응답도 같이 늦어집니다.\n\n"
            "그래서 원인은 모델 호출이 아니라 벡터 검색, 문서 조회, 인덱스 상태, 검색 결과 개수 같은 RAG 파이프라인 쪽에 있습니다. "
            "대시보드에서는 이 요청의 Trace Detail에서 Retrieve 구간이 가장 길게 보일 것입니다."
        )

    if request.scenario == "slow_llm":
        return (
            "이번 요청이 느린 이유는 검색이 아니라 LLM 답변 생성 시간이 길어졌기 때문입니다.\n\n"
            "retrieve 단계는 비교적 빨리 끝났지만, gemma3:1b가 실제 답변을 생성하는 llm_call 단계에서 시간이 오래 걸렸습니다. "
            "로컬 모델은 CPU/GPU 성능, 프롬프트 길이, 출력 길이에 영향을 많이 받기 때문에 이 구간이 길어질 수 있습니다.\n\n"
            "따라서 이 경우에는 RAG 검색을 고치기보다 모델 실행 환경, 출력 길이, 프롬프트 크기를 먼저 줄이는 것이 맞습니다."
        )

    if request.scenario == "high_token" or "토큰" in question or "비용" in question:
        return (
            "비용이 늘어난 이유는 토큰 사용량과 로컬 추론 시간이 같이 늘었기 때문입니다.\n\n"
            "긴 질문, 긴 답변, 요약 기능, RAG 문맥 추가가 발생하면 입력 토큰과 출력 토큰이 증가합니다. "
            "토큰이 많아지면 gemma3:1b가 처리해야 할 문맥이 길어지고, 그만큼 llm_call 실행 시간이 늘어납니다.\n\n"
            "현재 로컬 모델은 OpenAI처럼 토큰당 API 과금이 붙지는 않습니다. 대신 실행 시간이 길어진 만큼 CPU 기반 infra_cost_usd가 증가합니다. "
            "그래서 대시보드에서는 Total Tokens와 Total Cost가 함께 올라간 것으로 보입니다."
        )

    if request.scenario == "error" or "실패" in question or "에러" in question:
        return (
            "이 요청이 실패한 이유는 데모에서 error 시나리오로 강제로 실패를 발생시키기 때문입니다.\n\n"
            "실제 운영 상황으로 치면 모델 서버 장애, API 제한, 네트워크 오류, 잘못된 요청 값 같은 문제가 이 범주에 들어갑니다. "
            "OLLY는 이런 실패도 그냥 버리지 않고 request_id, trace_id, error metric으로 기록합니다.\n\n"
            "그래서 운영자는 실패한 요청을 Recent Requests에서 ERROR로 보고, 같은 trace_id로 어느 단계에서 실패했는지 추적할 수 있습니다."
        )

    if "rag" in question.lower() or "openai" in question.lower() or "느린" in question:
        return (
            "응답이 느린 이유는 요청 처리 과정 중 한 단계가 전체 시간을 끌어올렸기 때문입니다.\n\n"
            "OLLY는 요청을 retrieve, llm_call, postprocess로 나누어 기록합니다. "
            "retrieve가 길면 RAG 검색이 원인이고, llm_call이 길면 모델 생성이 원인이고, postprocess가 길면 후처리 코드가 원인입니다.\n\n"
            "즉, 단순히 'LLM이 느리다'고 보는 것이 아니라 어느 단계가 전체 latency를 만든 것인지 구분할 수 있습니다."
        )

    return (
        "OLLY는 LLM 서비스에서 문제가 생겼을 때 원인을 설명하기 위해 만든 관측성 대시보드입니다.\n\n"
        "LLM 요청은 겉으로 보면 하나의 질문과 하나의 답변처럼 보이지만, 내부적으로는 검색, 모델 호출, 후처리 단계를 거칩니다. "
        "OLLY는 이 단계를 나눠서 기록하기 때문에 비용이 늘었는지, 토큰이 많았는지, 어떤 단계가 느렸는지 설명할 수 있습니다.\n\n"
        "그래서 운영자는 감으로 추측하지 않고 request_id와 trace_id를 기준으로 원인을 확인할 수 있습니다."
    )


def estimate_demo_output_tokens(answer: str) -> int:
    return estimate_tokens(answer)
