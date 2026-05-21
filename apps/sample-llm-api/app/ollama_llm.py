import os
import time

import httpx

from app.demo_answers import build_demo_answer, build_demo_context, estimate_demo_output_tokens, is_unhelpful_answer
from app.schemas import ChatRequest


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:1b")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
MAX_NEW_TOKENS = int(os.getenv("OLLAMA_MAX_NEW_TOKENS", "256"))
TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.2"))
TOP_P = float(os.getenv("OLLAMA_TOP_P", "0.9"))
STABLE_DEMO_ANSWERS = os.getenv("STABLE_DEMO_ANSWERS", "true").lower() == "true"
_client: httpx.AsyncClient | None = None


def model_name() -> str:
    return OLLAMA_MODEL


def system_prompt() -> str:
    return (
        "당신은 OLLY LLM 운영 대시보드의 데모 어시스턴트입니다. "
        "사용자의 질문은 OLLY의 비용, 토큰, latency, RAG 병목, LLM 병목, 실패 원인에 관한 것입니다. "
        "반드시 한국어로 답하고, '모른다'로 끝내지 마세요. "
        "주어진 참고 문맥과 시나리오를 바탕으로 운영자가 다음에 확인할 화면과 지표를 설명하세요."
    )


def build_user_prompt(request: ChatRequest, context: list[str]) -> str:
    if STABLE_DEMO_ANSWERS:
        return (
            "OLLY 데모 요청입니다. 아래 질문에 한 문장으로 간단히 답하세요.\n\n"
            f"질문: {request.question}\n"
            f"시나리오: {request.scenario}\n"
            f"기능: {request.feature}\n"
        )

    detail_instruction = ""
    if request.scenario == "high_token":
        detail_instruction = "\n응답은 항목을 나누어 자세히 설명하세요."

    return (
        "다음 참고 문맥은 정답으로 사용할 수 있는 OLLY 운영 정보입니다. "
        "문맥 안의 정보를 근거로 사용자 질문에 답하세요.\n\n"
        f"[현재 시나리오]\n{request.scenario}\n\n"
        f"[현재 기능]\n{request.feature}\n\n"
        "[참고 문맥]\n"
        + "\n".join(f"- {item}" for item in context)
        + "\n\n[사용자 질문]\n"
        + request.question
        + detail_instruction
    )


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=OLLAMA_TIMEOUT_SECONDS,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _client


async def close() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def llm_call(request: ChatRequest, context: list[str]) -> tuple[str, int, int, dict[str, float]]:
    if request.scenario == "error":
        raise RuntimeError("forced Ollama failure scenario")

    enriched_context = context + build_demo_context(request)
    prompt = build_user_prompt(request, enriched_context)
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
        response = await get_client().post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
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
    if STABLE_DEMO_ANSWERS or is_unhelpful_answer(answer):
        answer = build_demo_answer(request)
        output_tokens = estimate_demo_output_tokens(answer)
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
