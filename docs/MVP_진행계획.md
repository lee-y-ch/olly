# OLLY MVP 진행 계획

## 1. 프로젝트 한 줄 설명

**OLLY는 LLM 서비스의 비용, 토큰, 응답 속도, 병목 지점을 한 화면에서 확인하는 운영 관측성 플랫폼이다.**

쉽게 말하면, 챗봇이나 RAG 서비스를 운영할 때 필요한 **운영 계기판**을 만드는 프로젝트이다.

운영 중에는 이런 질문이 자주 나온다.

- 어제 왜 비용이 갑자기 늘었지?
- 어떤 기능이 토큰을 가장 많이 쓰지?
- 응답이 느린 원인이 LLM인가, RAG 검색인가?
- 특정 요청은 왜 실패했지?
- 로컬 LLM을 쓰면 비용을 어떻게 계산하지?

OLLY는 이 질문에 답하기 위해 요청마다 비용, 토큰, 응답 시간, 처리 단계를 기록하고 화면으로 보여준다.

## 2. 현재 MVP 상태

현재 MVP는 아래 흐름까지 구현되어 있다.

```text
사용자
  ↓
http://localhost:8001/chat-ui
  ↓
POST /chat
  ↓
retrieve
  ↓
llm_call
  ↓
postprocess
  ↓
Ollama gemma3:1b 응답

동시에 관측 데이터 기록:
요청 수, 토큰 수, 비용, latency, 에러, trace
```

현재 구현된 화면:

| 화면 | 주소 | 역할 |
| --- | --- | --- |
| 사용자 챗봇 UI | http://localhost:8001/chat-ui | 사용자가 질문을 보내는 화면 |
| 운영자 대시보드 | http://localhost:8001/dashboard | 비용, 토큰, 병목, 최근 요청을 보는 화면 |
| API 문서 | http://localhost:8001/docs | 개발자가 API를 직접 테스트하는 화면 |
| Jaeger | http://localhost:16686 | 요청 하나의 trace 원본 확인 |
| Prometheus | http://localhost:9090 | metric 원본 확인 |
| Grafana | http://localhost:3001 | 보조 시각화 대시보드 |

## 3. MVP에서 보여줘야 하는 핵심 가치

이번 발표와 MVP에서 가장 중요한 것은 아래 3가지이다.

1. **비용**: 요청이 얼마나 비용을 만들었는지 볼 수 있다.
2. **토큰**: 어떤 기능이 토큰을 많이 쓰는지 볼 수 있다.
3. **병목**: 느린 원인이 `retrieve`, `llm_call`, `postprocess` 중 어디인지 볼 수 있다.

최종 데모에서 아래 문장을 증명하면 된다.

> 사용자는 그냥 질문을 보냈지만, 운영자는 OLLY에서 해당 요청의 비용, 토큰, 응답 시간, 병목 단계를 확인할 수 있다.

## 4. 전체 아키텍처

```text
사용자 챗봇 UI (/chat-ui)
  ↓
FastAPI Sample LLM API (/chat)
  ↓
Ollama gemma3:1b

FastAPI 내부 계측:
  - retrieve span
  - llm_call span
  - postprocess span
  - Prometheus metrics
  - request_id / trace_id

관측 데이터 흐름:
FastAPI
  ↓ OpenTelemetry
OpenTelemetry Collector
  ↓
Prometheus: 숫자 지표 저장
Jaeger: 요청 단위 trace 저장
  ↓
OLLY Operator Dashboard (/dashboard)
```

## 5. 주요 기술과 역할

| 기술 | 역할 |
| --- | --- |
| FastAPI | `/chat`, `/chat-ui`, `/dashboard`를 제공하는 API 서버 |
| Ollama | 로컬 LLM 실행기 |
| gemma3:1b | 현재 실험에 사용하는 로컬 LLM |
| OpenTelemetry | 요청 처리 단계를 trace로 기록 |
| OpenTelemetry Collector | trace/metric 데이터를 중간 수집 |
| Prometheus | 요청 수, 토큰, 비용, latency 같은 숫자 저장 |
| Jaeger | 요청 하나가 내부에서 어떻게 처리됐는지 확인 |
| Grafana | 보조 대시보드와 metric 검증 |
| Docker Compose | 전체 서비스를 한 번에 실행 |

## 6. 핵심 API

### POST /chat

사용자 질문을 받아 LLM 답변을 만든다.

요청 예시:

```json
{
  "question": "OpenAI가 느린 것인가, 우리 RAG가 느린 것인가?",
  "feature": "rag_qa",
  "scenario": "slow_retrieve"
}
```

응답 예시:

```json
{
  "request_id": "req_6b416a56",
  "trace_id": "581bf5f8a556b3843d3dfa910fc7e02b",
  "answer": "모른다.",
  "model": "gemma3:1b",
  "feature": "chat",
  "llm_backend": "ollama",
  "input_tokens": 122,
  "output_tokens": 8,
  "cost_usd": 0.000044,
  "token_cost_usd": 0.0,
  "infra_cost_usd": 0.000044,
  "compute_seconds": 3.2,
  "compute_resource": "cpu",
  "latency_ms": 3435,
  "status": "success"
}
```

### scenario 값

| scenario | 의미 | 발표에서 보여줄 것 |
| --- | --- | --- |
| `normal` | 정상 요청 | 일반적인 요청 처리 |
| `slow_retrieve` | 검색 단계 느림 | RAG 병목 |
| `slow_llm` | LLM 호출 느림 | 모델 생성 병목 |
| `high_token` | 토큰 많이 사용 | 토큰/비용 증가 |
| `error` | 실패 요청 | 실패도 관측되는지 확인 |

## 7. 로컬 LLM 비용 계산 방식

현재 모델은 Ollama의 `gemma3:1b`이다. OpenAI API처럼 토큰당 과금되는 구조가 아니다.

그래서 비용을 두 종류로 나눠서 기록한다.

```text
token_cost_usd = 0
infra_cost_usd = LLM 실행 시간(초) / 3600 * 시간당 장비 비용
```

기본값:

```text
compute_resource = cpu
LOCAL_COMPUTE_HOURLY_USD = 0.05
```

즉, 현재 MVP에서 비용은 **로컬 CPU/GPU 사용 시간 기반 추정 비용**이다.

## 8. 구현된 폴더 구조

```text
OLLY/
  apps/
    sample-llm-api/
      app/
        main.py
        dashboard.py
        schemas.py
        ollama_llm.py
        mock_llm.py
        metrics.py
        telemetry.py
        pricing.py
        static/
          chat_ui.html
          dashboard.html
      Dockerfile
      requirements.txt

  observability/
    otel-collector.yaml
    prometheus.yml
    alert-rules.yml
    grafana/
      dashboards/
      provisioning/

  deploy/
    docker-compose.yml

  docs/
    OLLY_쉬운_이해_가이드.md
    MVP_진행계획.md
    demo_scenario.md
    local_gemma3_setup.md
    대시보드_사전검증_결과.md
    팀원_병렬작업_가이드.md
```

## 9. MVP 완료 기준

아래가 되면 MVP는 발표 가능한 상태이다.

- `docker compose -f deploy/docker-compose.yml up -d --build`로 전체 서비스가 실행된다.
- `http://localhost:8001/chat-ui`에서 질문을 보낼 수 있다.
- 응답 아래에 `request_id`, `trace_id`, `latency`, `tokens`, `cost`가 보인다.
- `http://localhost:8001/dashboard`에서 방금 요청이 `Recent Requests`에 보인다.
- 요청을 클릭하면 `retrieve`, `LLM Generation`, `Post-process` 단계별 시간이 보인다.
- `Slow Retrieval (RAG)` 시나리오에서는 retrieve 병목을 설명할 수 있다.
- `High Token Usage` 시나리오에서는 토큰/비용 증가를 설명할 수 있다.
- `Error Occurred` 시나리오에서는 실패 요청도 기록됨을 설명할 수 있다.

## 10. 앞으로 확장할 수 있는 것

MVP 이후에는 아래를 확장할 수 있다.

- 실제 서비스 챗봇 UI와 연결
- OpenAI, Claude, Gemini 같은 외부 API 모델 비용 계산
- 요청 단위 로그 저장소 추가
- Slack/Discord 알림 연동
- 운영용 DB에 최근 요청 저장
- 사용자/조직별 비용 분리
- Kubernetes/Helm 배포
- 대시보드 로그인과 권한 관리

