# OLLY 쉬운 이해 가이드

이 문서는 OLLY를 처음 보는 팀원이 “무엇을 왜 만들었는지” 빠르게 이해하기 위한 자료이다.

## 1. OLLY는 무엇인가?

**OLLY는 LLM 서비스용 운영 대시보드와 분석 챗봇이다.**

챗봇이나 RAG 서비스를 운영하면 이런 질문이 생긴다.

- 왜 비용이 늘었지?
- 어떤 기능이 토큰을 많이 쓰지?
- 응답이 느린 이유가 모델 때문인가, RAG 검색 때문인가?
- 방금 요청은 왜 느렸지?
- 지금 알림이 떠 있나?
- 특정 trace_id는 어느 단계에서 문제가 생겼나?

OLLY는 이 질문에 답하기 위해 요청마다 비용, 토큰, latency, trace를 기록하고, 그 데이터를 읽어서 설명한다.

## 2. 지금 만든 것은 무엇인가?

현재 MVP에는 세 가지가 있다.

1. **사용자 챗봇 UI**
   - 주소: `http://localhost:8001/chat-ui`
   - 사용자가 질문을 보내는 화면

2. **운영자 대시보드**
   - 주소: `http://localhost:8001/dashboard`
   - 운영자가 비용, 토큰, 병목, 최근 요청을 보는 화면

3. **분석 챗봇**
   - `/chat` 질문을 보고 Prometheus/Jaeger 데이터를 읽어 답변
   - 예시 질문뿐 아니라 비슷한 운영 질문도 처리

## 3. 전체 흐름

```text
사용자 질문
  ↓
/chat API
  ↓
retrieve: 관련 문서 검색 또는 조회
  ↓
llm_call: gemma3:1b 답변 생성
  ↓
postprocess: 응답 후처리
  ↓
사용자에게 답변 반환

동시에 기록:
request_id, trace_id, tokens, cost, latency, stage duration, error
```

기록된 데이터는 아래 도구로 저장된다.

```text
FastAPI
  ↓ OpenTelemetry
OpenTelemetry Collector
  ├─ Prometheus: 숫자 metric 저장
  └─ Jaeger: 요청 trace 저장
```

## 4. 각 도구를 쉽게 설명하면

| 이름 | 쉽게 말하면 | 우리 프로젝트에서 하는 일 |
| --- | --- | --- |
| FastAPI | API 서버 | `/chat`, `/chat-ui`, `/dashboard` 제공 |
| Ollama | 로컬 LLM 실행기 | `gemma3:1b` 실행 |
| gemma3:1b | 작은 로컬 LLM | 답변 생성 |
| OpenTelemetry | 서비스 기록 표준 | 요청 단계 기록 |
| Prometheus | 숫자 저장소 | 요청 수, 토큰, 비용, latency 저장 |
| Jaeger | 요청 추적 도구 | 요청 하나가 어디서 느렸는지 확인 |
| Grafana | 시각화 도구 | Prometheus metric 보조 확인 |
| Docker Compose | 실행 도구 | 전체 서비스를 한 번에 실행 |

## 5. 핵심 용어

### Token

LLM이 문장을 처리하는 단위이다. 질문과 답변이 길어질수록 토큰 수가 늘어난다.

토큰이 많아지면:

- 외부 API 모델에서는 비용 증가
- 로컬 모델에서는 처리 시간 증가

### 로컬 LLM 비용

현재는 OpenAI API를 쓰지 않고 로컬 `gemma3:1b`를 쓴다.

그래서 토큰당 API 비용은 0이다.

```text
token_cost_usd = 0
infra_cost_usd = LLM 실행 시간(초) / 3600 * 시간당 장비 비용
```

즉, 현재 비용은 **로컬 CPU/GPU를 얼마나 오래 썼는지**로 추정한다.

### RAG

LLM이 바로 답하지 않고, 먼저 관련 문서를 찾은 뒤 그 문서를 참고해서 답하는 방식이다.

우리 코드에서 RAG 검색 단계는 `retrieve`이다.

### Trace

요청 하나가 내부에서 어떤 단계를 거쳤는지 보여주는 기록이다.

```text
POST /chat
  ├─ retrieve
  ├─ llm_call
  └─ postprocess
```

### Metric

숫자로 쌓이는 운영 데이터이다.

예:

```text
요청 수
토큰 수
비용
p95 latency
error rate
```

### p95 latency

전체 요청 중 느린 쪽 5%를 대표하는 응답 시간이다. 평균보다 운영 병목을 찾기에 좋다.

## 6. 분석 챗봇은 어떻게 답하는가?

분석 챗봇은 무작정 LLM에게 맡기지 않는다.

```text
질문 입력
  ↓
analysis_intents.py
질문 의도, 기간, request_id, trace_id 파악
  ↓
analysis.py
필요한 데이터 선택
  ↓
Prometheus/Jaeger 조회
  ↓
근거 수치와 함께 답변
```

예:

| 질문 | OLLY가 보는 데이터 |
| --- | --- |
| 비용이 왜 늘었어? | 비용 metric, 기능별 비용, infra cost |
| 토큰 많이 쓰는 기능은? | 기능별 token metric |
| RAG가 느린 거야? | `retrieve` p95와 `llm_call` p95 |
| 방금 요청 왜 느렸어? | Jaeger recent trace, stage duration |
| 알림 떠 있어? | Prometheus alerts |

## 7. 화면을 어떻게 보면 되는가?

### `/chat-ui`

사용자 화면이다.

확인할 것:

```text
REQ
TRACE
LATENCY
TOKENS
COST
MODEL
```

### `/dashboard`

운영자 화면이다.

확인할 것:

```text
Avg Latency
Total Tokens
Total Cost
Success Rate
Recent Requests
Trace Detail
Cost Analysis
Active Alerts
```

### Jaeger

요청 하나의 원본 trace를 보는 곳이다.

확인할 것:

```text
retrieve가 긴가?
llm_call이 긴가?
postprocess가 긴가?
```

## 8. 지금 답할 수 있는 질문

```text
현재 상태 요약해줘
어제랑 비교해서 비용이 왜 늘었어?
토큰 제일 많이 쓰는 기능 뭐야?
비용 많이 만든 기능 순위 보여줘
RAG가 느린 거야, 모델이 느린 거야?
가장 느린 요청 목록 보여줘
방금 요청 왜 느렸어?
최근 알림 떠 있어?
모델별 비용 알려줘
6시간 기준 운영 랭킹 보여줘
```

## 9. 팀원이 기억할 핵심 문장

> OLLY는 LLM 요청을 감으로 판단하지 않고, request_id와 trace_id를 기준으로 비용, 토큰, 지연, 실패, 알림 원인을 데이터로 설명하는 도구이다.
