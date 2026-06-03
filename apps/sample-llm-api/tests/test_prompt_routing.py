import asyncio
import sys
import types
import unittest

if "pydantic" not in sys.modules:
    pydantic_stub = types.ModuleType("pydantic")

    class BaseModel:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    def Field(default, **_kwargs):
        return default

    pydantic_stub.BaseModel = BaseModel
    pydantic_stub.Field = Field
    sys.modules["pydantic"] = pydantic_stub

if "httpx" not in sys.modules:
    httpx_stub = types.ModuleType("httpx")

    class AsyncClient:
        pass

    class Limits:
        def __init__(self, **_kwargs):
            pass

    class ConnectError(Exception):
        pass

    class HTTPStatusError(Exception):
        def __init__(self, response=None):
            self.response = response

    httpx_stub.AsyncClient = AsyncClient
    httpx_stub.Limits = Limits
    httpx_stub.ConnectError = ConnectError
    httpx_stub.HTTPStatusError = HTTPStatusError
    sys.modules["httpx"] = httpx_stub

from app.analysis_intents import classify_intent
import app.ollama_llm as ollama_llm
from app.schemas import ChatRequest


class PromptRoutingTest(unittest.TestCase):
    def request(self, question: str, scenario: str = "normal") -> ChatRequest:
        return ChatRequest(question=question, feature="chat", scenario=scenario)

    def test_general_llm_question_uses_general_prompt(self) -> None:
        request = self.request("LLM이 뭐야?")

        prompt = ollama_llm.build_user_prompt(request, [])

        self.assertFalse(ollama_llm.is_observability_request(request))
        self.assertIn("일반 질문", prompt)
        self.assertIn("LLM이 뭐야?", prompt)
        self.assertNotIn("OLLY 데모 요청", prompt)
        self.assertNotIn("[참고 문맥]", prompt)

    def test_general_question_stays_general_even_when_demo_scenario_is_selected(self) -> None:
        for scenario in ("high_token", "slow_retrieve", "slow_llm", "error"):
            with self.subTest(scenario=scenario):
                request = self.request("LLM이 뭐야?", scenario=scenario)

                prompt = ollama_llm.build_user_prompt(request, [])

                self.assertIsNone(classify_intent(request))
                self.assertFalse(ollama_llm.is_observability_request(request))
                self.assertIn("일반 질문", prompt)
                self.assertNotIn("OLLY 데모 요청", prompt)

    def test_rag_vs_finetuning_question_stays_general(self) -> None:
        request = self.request("RAG랑 파인튜닝 차이가 뭐야?")

        prompt = ollama_llm.build_user_prompt(request, [])

        self.assertFalse(ollama_llm.is_observability_request(request))
        self.assertIn("일반 질문", prompt)
        self.assertNotIn("OLLY 데모 요청", prompt)

    def test_general_error_message_question_stays_general(self) -> None:
        request = self.request("이 에러 메시지 해석해줘")

        self.assertIsNone(classify_intent(request))
        self.assertFalse(ollama_llm.is_observability_request(request))

    def test_general_ranking_question_stays_general(self) -> None:
        request = self.request("세계 대학 순위 알려줘")

        self.assertIsNone(classify_intent(request))
        self.assertFalse(ollama_llm.is_observability_request(request))

    def test_general_yesterday_question_stays_general(self) -> None:
        request = self.request("어제 뭐 먹었는지 기억해?")

        self.assertIsNone(classify_intent(request))
        self.assertFalse(ollama_llm.is_observability_request(request))

    def test_error_rate_question_is_observability(self) -> None:
        request = self.request("최근 에러율 알려줘")

        self.assertEqual(classify_intent(request), "error")
        self.assertTrue(ollama_llm.is_observability_request(request))

    def test_olly_cost_question_uses_demo_prompt_when_stable_answers_enabled(self) -> None:
        old_value = ollama_llm.STABLE_DEMO_ANSWERS
        ollama_llm.STABLE_DEMO_ANSWERS = True
        try:
            request = self.request("비용이 왜 늘었어?")

            prompt = ollama_llm.build_user_prompt(request, ["OLLY context"])

            self.assertTrue(ollama_llm.is_observability_request(request))
            self.assertIn("OLLY 데모 요청", prompt)
            self.assertIn("비용이 왜 늘었어?", prompt)
            self.assertNotIn("OLLY context", prompt)
        finally:
            ollama_llm.STABLE_DEMO_ANSWERS = old_value

    def test_olly_cost_question_uses_context_prompt_when_stable_answers_disabled(self) -> None:
        old_value = ollama_llm.STABLE_DEMO_ANSWERS
        ollama_llm.STABLE_DEMO_ANSWERS = False
        try:
            request = self.request("비용이 왜 늘었어?")

            prompt = ollama_llm.build_user_prompt(request, ["OLLY context"])

            self.assertTrue(ollama_llm.is_observability_request(request))
            self.assertIn("[참고 문맥]", prompt)
            self.assertIn("OLLY context", prompt)
            self.assertIn("비용이 왜 늘었어?", prompt)
            self.assertNotIn("일반 질문", prompt)
        finally:
            ollama_llm.STABLE_DEMO_ANSWERS = old_value

    def test_general_question_in_error_scenario_does_not_force_demo_failure(self) -> None:
        class FakeResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {
                    "message": {"content": "LLM은 대규모 언어 모델입니다."},
                    "prompt_eval_count": 7,
                    "eval_count": 6,
                }

        class FakeClient:
            async def post(self, _url, json):
                self.payload = json
                return FakeResponse()

        old_get_client = ollama_llm.get_client
        fake_client = FakeClient()
        ollama_llm.get_client = lambda: fake_client
        try:
            request = self.request("LLM이 뭐야?", scenario="error")

            answer, input_tokens, output_tokens, _metadata = asyncio.run(ollama_llm.llm_call(request, []))

            self.assertEqual(answer, "LLM은 대규모 언어 모델입니다.")
            self.assertEqual(input_tokens, 7)
            self.assertEqual(output_tokens, 6)
        finally:
            ollama_llm.get_client = old_get_client

    def test_general_question_uses_general_system_prompt_and_normal_output_limit(self) -> None:
        class FakeResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {
                    "message": {"content": "LLM은 대규모 언어 모델입니다."},
                    "prompt_eval_count": 7,
                    "eval_count": 6,
                }

        class FakeClient:
            def __init__(self) -> None:
                self.payload = None

            async def post(self, _url, json):
                self.payload = json
                return FakeResponse()

        old_get_client = ollama_llm.get_client
        fake_client = FakeClient()
        ollama_llm.get_client = lambda: fake_client
        try:
            request = self.request("LLM이 뭐야?", scenario="high_token")

            asyncio.run(ollama_llm.llm_call(request, []))

            self.assertIsNotNone(fake_client.payload)
            system_message = fake_client.payload["messages"][0]["content"]
            self.assertIn("한국어 AI 어시스턴트", system_message)
            self.assertNotIn("운영 대시보드", system_message)
            self.assertEqual(fake_client.payload["options"]["num_predict"], ollama_llm.MAX_NEW_TOKENS)
        finally:
            ollama_llm.get_client = old_get_client


if __name__ == "__main__":
    unittest.main()
