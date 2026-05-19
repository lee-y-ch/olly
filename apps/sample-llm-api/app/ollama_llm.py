import os
import time

import httpx

from app.schemas import ChatRequest


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:1b")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
MAX_NEW_TOKENS = int(os.getenv("OLLAMA_MAX_NEW_TOKENS", "256"))
TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.2"))
TOP_P = float(os.getenv("OLLAMA_TOP_P", "0.9"))


def model_name() -> str:
    return OLLAMA_MODEL


def system_prompt() -> str:
    return (
        "당신은 OLLY 성능 실험용 로컬 LLM입니다. "
        "한국어로 간결하고 정확하게 답하세요. "
        "모르면 추측하지 말고 모른다고 답하세요."
    )


def build_user_prompt(request: ChatRequest, context: list[str]) -> str:
    detail_instruction = ""
    if request.scenario == "high_token":
        detail_instruction = "\n응답은 항목을 나누어 자세히 설명하세요."

    return (
        "다음 참고 문맥을 활용해서 사용자 질문에 답하세요.\n\n"
        "[참고 문맥]\n"
        + "\n".join(f"- {item}" for item in context)
        + "\n\n[사용자 질문]\n"
        + request.question
        + detail_instruction
    )


async def llm_call(request: ChatRequest, context: list[str]) -> tuple[str, int, int, dict[str, float]]:
    if request.scenario == "error":
        raise RuntimeError("forced Ollama failure scenario")

    prompt = build_user_prompt(request, context)
    num_predict = MAX_NEW_TOKENS * 2 if request.scenario == "high_token" else MAX_NEW_TOKENS
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": prompt},
        ],
        "options": {
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "num_predict": num_predict,
        },
    }

    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT_SECONDS) as client:
            response = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
            response.raise_for_status()
    except httpx.ConnectError as exc:
        raise RuntimeError(
            f"Ollama server is not reachable at {OLLAMA_BASE_URL}. "
            f"Start Ollama and run: ollama pull {OLLAMA_MODEL}"
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"Ollama request failed: {exc.response.text}") from exc

    elapsed_seconds = time.perf_counter() - start
    data = response.json()
    answer = data.get("message", {}).get("content", "").strip()
    input_tokens = int(data.get("prompt_eval_count") or 0)
    output_tokens = int(data.get("eval_count") or 0)
    eval_duration_seconds = (data.get("eval_duration") or 0) / 1_000_000_000
    total_duration_seconds = (data.get("total_duration") or 0) / 1_000_000_000

    metadata = {
        "llm_elapsed_seconds": elapsed_seconds,
        "ollama_total_duration_seconds": total_duration_seconds,
        "ollama_load_duration_seconds": (data.get("load_duration") or 0) / 1_000_000_000,
        "ollama_prompt_eval_duration_seconds": (data.get("prompt_eval_duration") or 0) / 1_000_000_000,
        "ollama_eval_duration_seconds": eval_duration_seconds,
        "tokens_per_second": output_tokens / eval_duration_seconds if eval_duration_seconds > 0 else 0.0,
    }
    return answer, input_tokens, output_tokens, metadata
