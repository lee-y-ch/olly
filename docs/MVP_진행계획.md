# OLLY MVP 진행 계획

## 1. 프로젝트 정의

**OLLY는 LLM 서비스 운영자가 비용, 토큰, 응답 지연, 실패, 알림 원인을 한 화면에서 확인하고 질문으로 분석할 수 있는 관측성 플랫폼이다.**

운영 중 자주 나오는 질문은 다음과 같다.

- 왜 비용이 늘었지?
- 어떤 기능이 토큰을 가장 많이 쓰지?
- OpenAI/모델이 느린 것인가, 우리 RAG가 느린 것인가?
- 방금 요청은 왜 느렸지?
- 지금 알림이 떠 있는가?
- 특정 trace_id/request_id는 어디서 병목이 생겼는가?

현재 MVP는 이 질문에 대해 Prometheus와 Jaeger 데이터를 읽고 답하는 수준까지 구현되어 있다.

## 2. 현재 구현 상태

```text
사용자
  ↓
/chat-ui
  ↓
POST /chat
  ↓
retrieve
  ↓
llm_call
  ↓
postprocess
  ↓
응답 반환

동시에 기록:
요청 수, 토큰, 비용, latency, 단계별 시간, 에러, trace_id
```

현재 구현된 화면과 API:

| 항목 | 주소 | 역할 |
| --- | --- | --- |
| 사용자 챗봇 UI | http://localhost:8001/chat-ui | 질문 입력, 응답 및 metadata 확인 |
| 운영자 대시보드 | http://localhost:8001/dashboard | 비용/토큰/병목/최근 요청 통합 확인 |
| API 문서 | http://localhost:8001/docs | `/chat`, `/metrics`, `/health` 테스트 |
| 대시보드 API | http://localhost:8001/api/dashboard/summary | Prometheus/Jaeger 기반 요약 데이터 |
| trace 상세 API | http://localhost:8001/api/dashboard/traces/{trace_id} | 특정 trace 상세 |
| Jaeger | http://localhost:16686 | trace 원본 |
| Prometheus | http://localhost:9090 | metric 원본 |
| Grafana | http://localhost:3001 | 보조 대시보드 |

## 3. 핵심 가치

MVP에서 보여줘야 하는 가치는 세 가지이다.

1. **관측**: LLM 요청을 단계별로 기록한다.
2. **분석**: metric과 trace를 읽어 원인을 설명한다.
3. **시연**: 사용자는 질문하고 운영자는 대시보드에서 원인을 확인한다.

발표에서 증명할 문장:

> 사용자는 그냥 질문을 보냈지만, OLLY는 그 요청의 비용, 토큰, latency, 병목 단계, trace_id를 남기고 운영 질문에 답할 수 있다.

## 4. 아키텍처

```text
Chat UI
  ↓
FastAPI /chat
  ├─ retrieve
  ├─ llm_call
  └─ postprocess
  ↓
Ollama gemma3:1b

계측 흐름:
FastAPI
  ↓ OpenTelemetry
OpenTelemetry Collector
  ├─ Prometheus: metric 저장
  └─ Jaeger: trace 저장

분석 흐름:
/chat 질문
  ↓
analysis_intents.py: 질문 의도/기간/ID 파싱
  ↓
analysis.py: 필요한 데이터 조회
  ↓
analysis_metrics.py + dashboard.py
  ↓
Prometheus/Jaeger 데이터 기반 답변
```

## 5. 코드 최적화 기준

이번 코드 정리는 10년차 개발자 관점에서 아래 기준으로 진행했다.

| 기준 | 적용 내용 |
| --- | --- |
| 단일 책임 | 질문 의도 분류, Prometheus 비교 쿼리, 답변 생성을 분리 |
| 변경 용이성 | 새 질문 유형은 `analysis_intents.py`와 handler만 추가하면 됨 |
| 중복 제거 | `build_observability_answer`의 긴 if-chain을 handler dispatch 구조로 축소 |
| 검증 가능성 | 의도 분류와 metric 비교 로직을 독립적으로 테스트 가능 |
| 운영 안전성 | request_id/trace_id는 Prometheus label로 남기지 않고 Jaeger 중심으로 추적 |

분리된 파일:

```text
analysis.py           # 분석 답변 orchestration
analysis_intents.py   # 질문 의도, 기간, request_id, trace_id 파싱
analysis_metrics.py   # Prometheus 기간 비교 쿼리
```

## 6. 분석 챗봇이 답할 수 있는 질문

현재 예시 문장에만 묶여 있지 않고, 아래 유형의 운영 질문을 처리한다.

| 질문 유형 | 예시 |
| --- | --- |
| 상태 요약 | 현재 상태 요약해줘 |
| 비용 분석 | 비용이 왜 늘었어? |
| 기간 비교 | 어제랑 비교해서 비용이 늘었어? |
| 토큰 랭킹 | 토큰 제일 많이 쓰는 기능 뭐야? |
| 비용 랭킹 | 비용 많이 만든 기능 순위 보여줘 |
| 지연 원인 | 응답이 왜 느려? |
| RAG vs LLM | RAG가 느린 거야, 모델이 느린 거야? |
| 요청 분석 | 방금 요청 왜 느렸어? |
| trace 분석 | 이 trace_id 분석해줘 |
| 알림 확인 | 지금 알림 떠 있어? |
| 모델 분석 | 모델별 비용 알려줘 |
| 운영 랭킹 | 6시간 기준 운영 랭킹 보여줘 |

## 7. 비용 계산 방식

현재 모델은 Ollama `gemma3:1b`이다. OpenAI API처럼 토큰당 과금되지 않는다.

```text
token_cost_usd = 0
infra_cost_usd = LLM 실행 시간(초) / 3600 * 시간당 장비 비용
total_cost_usd = token_cost_usd + infra_cost_usd
```

기본 설정:

```text
LOCAL_COMPUTE_RESOURCE=cpu
LOCAL_COMPUTE_HOURLY_USD=0.05
```

따라서 현재 비용 증가는 대부분 **토큰 증가 → llm_call 실행 시간 증가 → infra_cost 증가**로 설명한다.

## 8. 폴더 구조

```text
OLLY/
  apps/sample-llm-api/
    app/
      main.py
      analysis.py
      analysis_intents.py
      analysis_metrics.py
      dashboard.py
      metrics.py
      telemetry.py
      ollama_llm.py
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

  deploy/
    docker-compose.yml

  docs/
```

## 9. MVP 완료 기준

- `docker compose -f deploy/docker-compose.yml up -d --build`로 전체 실행
- `/chat-ui`에서 질문 전송 가능
- 응답 metadata에 `request_id`, `trace_id`, `latency`, `tokens`, `cost` 표시
- `/dashboard`에서 최근 요청과 단계별 병목 확인
- 분석 챗봇이 Prometheus/Jaeger 데이터를 근거로 답변
- Jaeger에서 `POST /chat` trace 확인
- Prometheus에서 주요 metric 확인
- Prometheus alert firing 상태 확인 가능

## 10. 다음 확장

- 실제 서비스 DB에 request summary 저장
- 사용자/조직별 비용 분리
- Slack/Discord 알림 발송
- OpenAI/Claude/Gemini 외부 모델별 단가 계산
- 대시보드 로그인/권한
- Kubernetes/Helm 배포
- 장기 보관용 metric/log 저장소
