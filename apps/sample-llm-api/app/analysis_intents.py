import re

from app.schemas import ChatRequest


LATENCY_KEYWORDS = ("느려", "느린", "느림", "지연", "latency", "병목", "bottleneck", "응답")
COST_KEYWORDS = ("비용", "cost", "2배", "증가", "올랐", "비싸")
TOKEN_KEYWORDS = ("토큰", "token")
TOP_FEATURE_KEYWORDS = ("어떤 기능", "무슨 기능", "가장 많이", "많이 쓰", "최다", "top")
RAG_VS_LLM_KEYWORDS = ("rag", "openai", "llm", "모델", "검색", "답변 생성")
ERROR_KEYWORDS = ("실패", "에러", "오류", "error", "fail")
ALERT_KEYWORDS = ("알림", "alert", "경고", "장애", "incident")
COMPARE_KEYWORDS = ("어제", "전일", "지난", "이전", "비교", "대비", "2배", "증가율", "줄었", "늘었")
RANKING_KEYWORDS = ("순위", "랭킹", "top", "상위", "목록", "리스트")
MODEL_KEYWORDS = ("모델", "model", "gemma", "openai")
REQUEST_KEYWORDS = ("요청", "request", "trace", "트레이스", "req_")
TRACE_ID_RE = re.compile(r"\b[0-9a-f]{16,32}\b", re.IGNORECASE)
REQUEST_ID_RE = re.compile(r"\breq_[0-9a-f]{8}\b", re.IGNORECASE)
VALID_WINDOWS = {"15m", "1h", "6h", "24h"}


def classify_intent(request: ChatRequest) -> str | None:
    question = request.question.lower()
    has_token = contains(question, TOKEN_KEYWORDS)
    asks_top_feature = contains(question, TOP_FEATURE_KEYWORDS) or "기능" in question
    has_cost = contains(question, COST_KEYWORDS)
    has_latency = contains(question, LATENCY_KEYWORDS)
    mentions_rag_or_llm = contains(question, RAG_VS_LLM_KEYWORDS)

    if contains(question, ("가장 느린", "느린 요청", "slowest", "최근 요청", "요청 목록")):
        return "slowest_requests"
    if extract_trace_id(question) or extract_request_id(question) or (
        contains(question, REQUEST_KEYWORDS) and contains(question, ("이", "해당", "방금"))
    ):
        return "trace_detail"
    if contains(question, COMPARE_KEYWORDS):
        return "compare"
    if contains(question, ALERT_KEYWORDS):
        return "alerts"
    if contains(question, ERROR_KEYWORDS):
        return "error"
    if mentions_rag_or_llm and (has_latency or "느린 것" in question):
        return "rag_vs_llm"
    if contains(question, MODEL_KEYWORDS) and (has_cost or has_token or has_latency or "상태" in question):
        return "models"
    if contains(question, RANKING_KEYWORDS):
        return "ranking"
    if has_token and asks_top_feature:
        return "top_tokens"
    if has_cost and asks_top_feature:
        return "top_costs"
    if has_cost:
        return "cost"
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
        if request.scenario != "normal"
        or "olly" in question
        or "대시보드" in question
        or contains(question, ("상태", "요약", "현황", "health", "summary", "overview"))
        else None
    )


def contains(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def extract_window(question: str, default: str = "1h") -> str:
    text = question.lower()
    if contains(text, ("15분", "15m", "quarter")):
        return "15m"
    if contains(text, ("6시간", "6h")):
        return "6h"
    if contains(text, ("24시간", "24h", "하루", "오늘", "어제", "전일", "지난날")):
        return "24h"
    if contains(text, ("1시간", "한 시간", "1h", "최근")):
        return "1h"
    return default if default in VALID_WINDOWS else "1h"


def extract_trace_id(question: str) -> str | None:
    match = TRACE_ID_RE.search(question)
    return match.group(0) if match else None


def extract_request_id(question: str) -> str | None:
    match = REQUEST_ID_RE.search(question)
    return match.group(0) if match else None
