import asyncio

from app.pricing import estimate_tokens
from app.schemas import ChatRequest


async def retrieve(request: ChatRequest) -> list[str]:
    if request.scenario == "slow_retrieve":
        await asyncio.sleep(1.8)
    else:
        await asyncio.sleep(0.15)

    return [
        "OLLY는 LLM 서비스의 비용, 속도, 병목을 관측하는 플랫폼입니다.",
        "OpenTelemetry, Prometheus, Jaeger, Grafana를 사용합니다.",
    ]


async def llm_call(request: ChatRequest, context: list[str]) -> tuple[str, int, int]:
    if request.scenario == "error":
        await asyncio.sleep(0.2)
        raise RuntimeError("mock LLM failure")

    if request.scenario == "slow_llm":
        await asyncio.sleep(2.0)
    else:
        await asyncio.sleep(0.35)

    if request.scenario == "high_token":
        answer = (
            "OLLY는 LLM 운영 관측성 플랫폼입니다. "
            "요청별 토큰 사용량, 예상 비용, 응답 시간, 처리 단계별 병목을 기록합니다. "
            "운영자는 Grafana에서 전체 추세를 보고, Jaeger에서 느린 요청의 상세 흐름을 확인합니다. "
        ) * 8
    else:
        answer = "OLLY는 LLM 서비스의 비용, 속도, 병목을 실시간으로 확인하는 관측성 플랫폼입니다."

    prompt = request.question + "\n" + "\n".join(context)
    input_tokens = estimate_tokens(prompt)
    output_tokens = estimate_tokens(answer)
    return answer, input_tokens, output_tokens


async def postprocess(answer: str) -> str:
    await asyncio.sleep(0.08)
    return answer.strip()
