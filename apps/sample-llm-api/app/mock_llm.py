import asyncio

from app.analysis_intents import classify_intent
from app.demo_answers import build_demo_answer, build_demo_context, estimate_demo_output_tokens
from app.pricing import estimate_tokens
from app.schemas import ChatRequest


async def retrieve(request: ChatRequest) -> list[str]:
    if request.scenario == "slow_retrieve":
        await asyncio.sleep(1.8)
    else:
        await asyncio.sleep(0.15)

    return build_demo_context(request)


def model_name() -> str:
    return "gpt-4o-mini-mock"


async def llm_call(request: ChatRequest, context: list[str]) -> tuple[str, int, int, dict[str, float]]:
    if request.scenario == "error" and classify_intent(request) == "intro":
        await asyncio.sleep(0.2)
        raise RuntimeError("mock LLM failure")

    if request.scenario == "slow_llm":
        await asyncio.sleep(2.0)
    else:
        await asyncio.sleep(0.35)

    answer = build_demo_answer(request)

    prompt = request.question + "\n" + "\n".join(context)
    input_tokens = estimate_tokens(prompt)
    output_tokens = estimate_demo_output_tokens(answer)
    return answer, input_tokens, output_tokens, {
        "llm_elapsed_seconds": 2.0 if request.scenario == "slow_llm" else 0.35,
        "tokens_per_second": 0.0,
    }


async def postprocess(answer: str) -> str:
    await asyncio.sleep(0.08)
    return answer.strip()
