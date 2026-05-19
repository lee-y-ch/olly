from typing import Literal

from pydantic import BaseModel, Field


Scenario = Literal["normal", "slow_retrieve", "slow_llm", "high_token", "error"]


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    feature: str = "chat"
    scenario: Scenario = "normal"


class ChatResponse(BaseModel):
    request_id: str
    trace_id: str
    answer: str
    model: str
    feature: str
    llm_backend: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    token_cost_usd: float
    infra_cost_usd: float
    compute_seconds: float
    compute_resource: str
    latency_ms: int
    status: str
