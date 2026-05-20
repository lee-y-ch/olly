# OLLY 쉬운 이해 가이드

이 문서는 팀원들이 구현 내용을 빠르게 이해하고 발표를 준비할 수 있도록 정리한 자료이다. 기술 용어를 정확하게 외우기보다, **무엇을 왜 만들었는지**를 먼저 이해하는 것이 목표이다.

## 1. OLLY가 무엇인가?

**OLLY는 LLM 서비스용 운영 대시보드이다.**

챗봇, 문서 요약, 코드 어시스턴트 같은 LLM 기능을 운영하다 보면 다음 질문이 자주 나온다.

- 어제 왜 비용이 2배가 됐지?
- 어떤 기능이 토큰을 가장 많이 쓰지?
- 응답이 느린 원인이 LLM인가, RAG 검색인가?
- 특정 요청은 왜 실패했지?
- 로컬 모델을 쓰면 실제 운영 비용은 어떻게 계산하지?

OLLY는 이 질문에 답하기 위해 만든다.

즉, OLLY는 LLM을 더 똑똑하게 만드는 서비스가 아니다. **LLM 서비스가 어떻게 돌아가고 있는지 보여주는 관측성 플랫폼**이다.

## 2. 지금 만든 MVP는 무엇인가?

이번 MVP는 완성형 서비스가 아니라, 핵심 아이디어가 실제로 동작하는 최소 버전이다.

현재 구현된 것:

- `gemma3:1b` 로컬 LLM을 사용하는 간단한 챗봇 API
- 요청별 토큰 수 측정
- 로컬 CPU/GPU 사용 시간 기반 비용 추정
- 요청별 응답 시간 측정
- `retrieve`, `llm_call`, `postprocess` 단계별 병목 추적
- 사용자용 챗봇 화면
- 운영자용 통합 웹 대시보드
- Grafana 대시보드 시각화
- Jaeger trace 상세 분석
- Prometheus metric 저장
- Prometheus alert rule

## 3. 전체 흐름

```text
사용자 질문
  ↓
/chat API
  ↓
retrieve 단계
  ↓
llm_call 단계
  ↓
postprocess 단계
  ↓
응답 반환

동시에 아래 데이터가 기록됨:

토큰 수
예상 비용
응답 시간
단계별 처리 시간
에러 여부
```

기록된 데이터는 다음 도구로 이동한다.

```text
FastAPI 챗봇
  ↓
OpenTelemetry
  ↓
OpenTelemetry Collector
  ↓
Prometheus / Jaeger
  ↓
Grafana
```

## 4. 각 도구를 쉽게 설명하면

| 이름 | 쉽게 말하면 | 우리 프로젝트에서 하는 일 |
| --- | --- | --- |
| FastAPI | API 서버를 쉽게 만드는 Python 도구 | `/chat` 챗봇 API 제공 |
| gemma3:1b | 로컬에서 실행하는 작은 LLM | 실제 답변 생성 |
| Ollama | 로컬 LLM 실행기 | `gemma3:1b` 모델 실행 |
| OpenTelemetry | 서비스 동작 기록 표준 | 요청 처리 단계를 기록 |
| OpenTelemetry Collector | 기록 데이터 중간 수집기 | trace/metric 데이터를 전달 |
| Prometheus | 숫자 저장소 | 요청 수, 토큰 수, 비용, latency 저장 |
| Jaeger | 요청 추적 도구 | 요청 하나가 어디서 느렸는지 확인 |
| OLLY Chat UI | 사용자 화면 | 일반 사용자가 질문을 보내는 화면 |
| OLLY Operator Dashboard | 운영자 화면 | 비용, 토큰, 속도, 병목, 최근 요청을 한 화면에서 확인 |
| Grafana | 외부 시각화 도구 | Prometheus metric을 검증하거나 보조로 확인 |
| Docker Compose | 여러 서비스를 한 번에 실행하는 도구 | 전체 MVP를 한 명령으로 실행 |

## 5. 핵심 용어 정리

### LLM

Large Language Model의 줄임말이다. ChatGPT, Claude, Gemini, Gemma 같은 언어 모델을 의미한다.

우리 프로젝트에서는 `gemma3:1b`를 사용한다.

### 로컬 LLM

OpenAI API처럼 외부 서버에 요청하는 것이 아니라, 내 컴퓨터나 우리 서버에서 직접 실행하는 LLM이다.

장점:

- 외부 API 과금이 없다.
- 데이터가 외부로 나가지 않는다.

단점:

- CPU/GPU 자원을 직접 써야 한다.
- 모델 성능이나 속도가 서버 사양에 영향을 받는다.

### Token

LLM이 문장을 처리하는 단위이다. 단어와 비슷하지만 완전히 같지는 않다.

예를 들어 긴 질문이나 긴 답변일수록 token 수가 늘어난다.

토큰이 많아지면:

- 외부 API 모델에서는 비용이 증가한다.
- 로컬 모델에서는 처리 시간이 길어질 수 있다.

### 비용

외부 API 모델과 로컬 모델의 비용 계산 방식은 다르다.

외부 API 모델:

```text
비용 = 입력 토큰 비용 + 출력 토큰 비용
```

로컬 모델:

```text
비용 = LLM 실행 시간(초) / 3600 * 시간당 장비 비용
```

현재 MVP 기본값:

```text
리소스: cpu
시간당 비용: $0.05
```

그래서 `gemma3:1b`는 API 토큰 비용은 0이고, CPU 사용 시간 기반 인프라 비용만 계산한다.

### RAG

Retrieval-Augmented Generation의 줄임말이다.

쉽게 말하면, LLM이 바로 답하지 않고 먼저 관련 문서를 검색한 다음, 그 문서를 참고해서 답하는 방식이다.

```text
질문
  ↓
관련 문서 검색
  ↓
LLM에게 문서와 질문 전달
  ↓
답변 생성
```

우리 코드에서는 이 검색 단계를 `retrieve`라고 부른다.

### Observability

한국어로는 관측성이라고 한다.

서비스 내부에서 무슨 일이 일어나는지 밖에서 알 수 있게 만드는 것이다.

OLLY에서 관측하는 것:

- 요청 수
- 토큰 수
- 예상 비용
- 응답 시간
- 단계별 병목
- 에러율

### Metric

숫자로 쌓이는 데이터이다.

예:

```text
총 요청 수: 10
총 토큰 수: 5000
총 비용: 0.03달러
p95 응답 시간: 3.2초
```

Prometheus가 metric을 저장하고, Grafana가 metric을 그래프로 보여준다.

### Trace

요청 하나가 내부에서 어떤 단계를 거쳤는지 보여주는 기록이다.

예:

```text
POST /chat
  ├─ retrieve: 1.8초
  ├─ llm_call: 0.7초
  └─ postprocess: 0.1초
```

Jaeger가 trace를 보여준다.

### Span

Trace 안에 들어 있는 작은 단계 하나이다.

우리 프로젝트의 주요 span:

```text
retrieve
llm_call
postprocess
```

### Latency

응답 시간이다.

사용자가 질문을 보낸 뒤 답변을 받을 때까지 걸린 시간을 의미한다.

### p95 latency

전체 요청 중 느린 쪽 5%를 대표하는 응답 시간이다.

평균보다 운영 상황을 더 잘 보여준다. 평균은 일부 느린 요청을 숨길 수 있기 때문이다.

### Alert

문제가 생겼을 때 알려주는 규칙이다.

현재 MVP에는 다음 알림 규칙이 있다.

- p95 응답 시간이 너무 높음
- 에러율이 높음
- 토큰 사용량 급증
- retrieve 단계가 느림
- 로컬 추론 비용 증가

현재는 Prometheus alert rule까지 구현되어 있다. Slack, Discord 같은 외부 알림 발송은 다음 확장 단계이다.

## 6. 우리가 만든 API

API 문서:

```text
http://localhost:8001/docs
```

주요 API:

```text
POST /chat
```

요청 예시:

```json
{
  "question": "왜 응답이 느려?",
  "feature": "chat",
  "scenario": "slow_retrieve"
}
```

실제 사용자는 보통 질문만 입력한다. `feature`와 `scenario`는 MVP 데모를 안정적으로 하기 위해 넣은 값이다.

| 값 | 의미 |
| --- | --- |
| `question` | 사용자 질문 |
| `feature` | 기능 이름. 예: `chat`, `summary`, `rag_qa` |
| `scenario` | 데모용 상황 지정 |

`scenario` 종류:

| scenario | 의미 |
| --- | --- |
| `normal` | 정상 요청 |
| `slow_retrieve` | RAG 검색 단계가 느린 상황 |
| `slow_llm` | LLM 호출 단계가 느린 상황 |
| `high_token` | 토큰을 많이 쓰는 상황 |
| `error` | 에러 상황 |

응답에는 요청 추적을 위한 값도 포함된다.

```json
{
  "request_id": "req_b93e8334",
  "trace_id": "a2aa25c7f1488e0e24186443ef7a9e23",
  "model": "gemma3:1b",
  "feature": "chat"
}
```

| 값 | 의미 |
| --- | --- |
| `request_id` | OLLY가 만든 요청 식별자 |
| `trace_id` | Jaeger에서 해당 요청 trace를 찾을 수 있는 식별자 |

자체 웹 대시보드를 만들 때는 최근 요청 목록에서 `trace_id`를 이용해 Jaeger 상세 화면으로 연결할 수 있다.

## 7. 화면을 어떻게 보면 되는가?

발표와 시연에서는 아래 두 화면을 중심으로 보면 된다.

```text
사용자 화면: http://localhost:8001/chat-ui
운영자 화면: http://localhost:8001/dashboard
```

`/docs`, Grafana, Jaeger, Prometheus는 보조 화면이다. 처음부터 모두 보여주면 복잡해 보이므로, 발표에서는 먼저 `/chat-ui`와 `/dashboard`만 사용하고 필요할 때 원본 도구를 보여주는 방식이 좋다.

### 7.1 사용자 챗봇 화면

주소:

```text
http://localhost:8001/chat-ui
```

이 화면은 실제 사용자가 보는 화면이다.

사용자는 JSON을 몰라도 된다. 그냥 질문을 입력하고 전송하면 된다.

화면에서 보는 것:

| 영역 | 의미 |
| --- | --- |
| Scenario Selection | 발표용 상황 선택 |
| Example Questions | 발표 때 바로 넣을 수 있는 예시 질문 |
| Chat UI | 사용자가 질문하고 답변을 받는 영역 |
| 응답 메타데이터 | 방금 요청의 request id, trace id, latency, tokens, cost |
| Operator Dashboard 링크 | 운영자 대시보드로 이동 |

왼쪽 시나리오의 의미:

| 버튼 | 내부 설정 | 보여줄 수 있는 상황 |
| --- | --- | --- |
| Normal Request | `scenario=normal`, `feature=chat` | 정상 요청 |
| Slow Retrieval (RAG) | `scenario=slow_retrieve`, `feature=rag_qa` | RAG 검색 단계가 느린 상황 |
| Slow LLM Response | `scenario=slow_llm`, `feature=chat` | LLM 호출 단계가 느린 상황 |
| High Token Usage | `scenario=high_token`, `feature=summary` | 토큰을 많이 쓰는 상황 |
| Error Occurred | `scenario=error`, `feature=chat` | 실패 요청 |

사용자가 질문을 전송하면 내부적으로는 `/chat` API가 호출된다.

```text
사용자 질문
  ↓
/chat-ui
  ↓
POST /chat
  ↓
gemma3:1b 로컬 LLM 호출
  ↓
답변 반환
```

동시에 OLLY는 아래 데이터를 자동으로 기록한다.

```text
request_id
trace_id
latency
input_tokens
output_tokens
cost
retrieve / llm_call / postprocess 단계별 시간
```

따라서 발표에서는 이렇게 말하면 된다.

> 사용자는 일반 챗봇처럼 질문만 입력합니다. 하지만 OLLY는 뒤에서 이 요청의 비용, 토큰, 응답 시간, 병목 단계를 자동으로 기록합니다.

### 7.2 운영자 대시보드 화면

주소:

```text
http://localhost:8001/dashboard
```

이 화면은 운영자나 개발자가 보는 화면이다.

`/chat-ui`에서 질문을 보낸 뒤 이 화면으로 이동하면, 방금 요청이 `Recent Requests`에 나타난다.

화면에서 보는 것:

| 영역 | 의미 |
| --- | --- |
| Avg Latency | 선택한 시간 동안 평균 응답 시간 |
| Total Tokens | 전체 토큰 사용량 |
| Total Cost | 로컬 추론 시간 기반 예상 비용 |
| Success Rate | 성공 요청 비율 |
| Recent Requests | 최근 `/chat` 요청 목록 |
| Trace Detail | 선택한 요청의 단계별 처리 시간 |
| Cost Analysis | 기능별 비용 추이 |
| Active Alerts | 현재 활성화된 알림 |

`Recent Requests`에서 요청 하나를 클릭하면 오른쪽 `Trace Detail`이 바뀐다.

Trace Detail에서 보는 핵심 단계:

| 단계 | 의미 |
| --- | --- |
| Retrieve | RAG 검색 또는 관련 문서 조회 단계 |
| LLM Generation | 로컬 LLM이 답변을 생성하는 단계 |
| Post-process | 응답 후처리 단계 |

예를 들어 `Slow Retrieval (RAG)` 시나리오를 실행했는데 `Retrieve` 막대가 가장 길면 이렇게 설명하면 된다.

> 이 요청은 LLM이 느린 것이 아니라, 답변 생성 전에 관련 문서를 찾는 retrieve 단계가 병목입니다.

반대로 `Slow LLM Response`에서 `LLM Generation`이 가장 길면 이렇게 설명한다.

> 이 요청은 검색보다 LLM 답변 생성 시간이 길어서 전체 응답이 느려졌습니다.

### 7.3 실제 발표 순서

추천 발표 순서는 아래와 같다.

```text
1. http://localhost:8001/chat-ui 를 연다.
2. 왼쪽에서 Slow Retrieval (RAG)를 선택한다.
3. Example Questions에서 "Is OpenAI slow or our RAG?"를 누른다.
4. 질문을 전송한다.
5. 답변 아래의 latency, tokens, cost, trace_id를 보여준다.
6. Operator Dashboard를 클릭한다.
7. http://localhost:8001/dashboard 에서 Recent Requests를 확인한다.
8. 방금 요청을 클릭한다.
9. 오른쪽 Trace Detail에서 Retrieve가 긴지 확인한다.
10. "이 요청은 LLM보다 RAG 검색 단계가 병목이다"라고 결론을 말한다.
```

다른 시나리오도 같은 방식으로 보여주면 된다.

| 보여주고 싶은 내용 | 선택할 시나리오 | 대시보드에서 볼 것 |
| --- | --- | --- |
| 정상 요청 | Normal Request | latency와 cost가 낮음 |
| RAG 병목 | Slow Retrieval (RAG) | Retrieve 막대가 김 |
| LLM 병목 | Slow LLM Response | LLM Generation 막대가 김 |
| 토큰 과다 | High Token Usage | Total Tokens와 Total Cost 증가 |
| 실패 요청 | Error Occurred | Recent Requests에 ERROR 표시 |

### 7.4 각 화면의 역할을 한 문장으로 설명하기

발표 중 헷갈리지 않게 아래처럼 구분하면 된다.

```text
/chat-ui
= 사용자가 질문하는 화면

/dashboard
= 운영자가 비용, 토큰, 속도, 병목을 확인하는 화면

/docs
= 개발자가 API를 직접 테스트하는 문서 화면

Grafana / Jaeger / Prometheus
= OLLY가 내부적으로 사용하는 원본 관측 도구
```

## 8. Grafana에서 봐야 하는 것

주소:

```text
http://localhost:3001/d/olly-mvp/olly-mvp-dashboard
```

Grafana는 현재 발표의 메인 화면이 아니라 보조 검증 화면이다. OLLY 자체 웹 대시보드가 Prometheus 데이터를 잘 가져오는지 확인하거나, 기존 관측성 도구와 비교할 때 사용한다.

주요 패널:

| 패널 | 의미 |
| --- | --- |
| Total Requests | 전체 요청 수 |
| Total Tokens | 전체 토큰 사용량 |
| Total Estimated Cost | 총 예상 비용 |
| p95 Latency | 느린 요청이 있는지 확인 |
| Token Usage Trend | 시간대별 토큰 사용 추이 |
| Cost Breakdown | API 토큰 비용과 로컬 인프라 비용 분리 |
| Local Compute Seconds | 로컬 모델 실행 시간 |
| Bottleneck by Stage p95 | 어느 단계가 느린지 확인 |
| Active Alerts | 현재 발생 중인 알림 |
| Jaeger Trace Link | Jaeger 상세 분석 화면 이동 |

## 9. Jaeger에서 봐야 하는 것

주소:

```text
http://localhost:16686
```

확인 순서:

1. Service에서 `olly-sample-api` 선택
2. `Find Traces` 클릭
3. trace 하나 선택
4. 아래 span 확인

```text
retrieve
llm_call
postprocess
```

예를 들어 `slow_retrieve` 요청을 보냈는데 `retrieve` 막대가 길면, LLM이 느린 것이 아니라 RAG 검색 단계가 느린 것이다.

## 10. Prometheus에서 봐야 하는 것

주소:

```text
http://localhost:9090
```

Prometheus는 발표에서 직접 보여줄 필요는 적다. Grafana가 Prometheus 데이터를 가져와서 보여주기 때문이다.

다만 원본 metric을 확인할 때 사용한다.

추천 쿼리:

```promql
sum(olly_requests_total)
```

```promql
sum(olly_tokens_total) by (token_type)
```

```promql
sum(olly_infra_cost_usd_total) by (resource, model)
```

```promql
histogram_quantile(0.95, sum(rate(olly_stage_duration_seconds_bucket[5m])) by (le, stage))
```

## 11. 발표에서 설명할 핵심 흐름

발표 흐름은 이렇게 잡으면 된다.

```text
1. /chat-ui에서 사용자가 질문을 보낸다.
2. 답변 아래에 latency, tokens, cost, trace_id가 생기는 것을 보여준다.
3. /dashboard로 이동한다.
4. Recent Requests에서 방금 요청을 선택한다.
5. Trace Detail에서 retrieve, llm_call, postprocess 중 병목 단계를 확인한다.
6. High Token Usage 시나리오로 토큰과 비용 증가를 보여준다.
7. Error Occurred 시나리오로 실패 요청도 기록되는 것을 보여준다.
8. 로컬 모델은 API 과금이 없고, CPU/GPU 실행 시간 기반 비용으로 계산한다고 설명한다.
```

## 12. 발표용 한 문장

> OLLY는 LLM 서비스의 비용, 속도, 병목을 한 화면에서 확인할 수 있게 해주는 운영 대시보드입니다. 사용자는 챗봇 화면에서 질문만 입력하고, 운영자는 대시보드에서 모델별 비용, 기능별 토큰 사용량, 요청 단위 병목, 알림 상태를 확인합니다.

## 13. 팀원 분업 전에 알아야 할 역할

자세한 병렬 작업 계획은 아래 문서에 따로 정리되어 있다.

```text
docs/팀원_병렬작업_가이드.md
```

간단히 나누면 아래 4개 역할이다.

| 역할 | 맡을 부분 |
| --- | --- |
| API / LLM 담당 | `/chat` API, Gemma/Ollama 호출, 응답 구조 |
| 관측성 담당 | OpenTelemetry span, Prometheus metric, Jaeger trace |
| 프론트엔드 / 대시보드 담당 | `/chat-ui`, `/dashboard`, 요청 상세 화면 |
| 문서 / 발표 담당 | 데모 시나리오, 실행 가이드, 발표 흐름 |

각 역할은 분리되어 있지만, 아래 이름은 반드시 같이 맞춰야 한다.

- API 응답 필드 이름
- metric 이름
- span 이름
- Docker Compose 서비스 이름
- Grafana panel 이름

## 14. 지금 코드에서 중요한 파일

| 파일 | 역할 |
| --- | --- |
| `apps/sample-llm-api/app/main.py` | FastAPI API 흐름 |
| `apps/sample-llm-api/app/dashboard.py` | `/chat-ui`, `/dashboard`, 대시보드 데이터 API |
| `apps/sample-llm-api/app/static/chat_ui.html` | 사용자 챗봇 화면 |
| `apps/sample-llm-api/app/static/dashboard.html` | 운영자 통합 대시보드 화면 |
| `apps/sample-llm-api/app/ollama_llm.py` | Ollama Gemma 모델 호출 |
| `apps/sample-llm-api/app/mock_llm.py` | 데모용 mock LLM |
| `apps/sample-llm-api/app/metrics.py` | Prometheus metric 정의와 기록 |
| `apps/sample-llm-api/app/config.py` | 환경변수 설정 관리 |
| `apps/sample-llm-api/app/pricing.py` | 토큰 비용, 로컬 인프라 비용 계산 |
| `observability/prometheus.yml` | Prometheus 수집 설정 |
| `observability/alert-rules.yml` | 알림 규칙 |
| `observability/otel-collector.yaml` | OpenTelemetry Collector 설정 |
| `observability/grafana/dashboards/olly-mvp-dashboard.json` | 보조 Grafana 대시보드 |
| `deploy/docker-compose.yml` | 전체 서비스 실행 설정 |

## 15. 최종 정리

OLLY의 핵심은 세 가지이다.

1. **비용**: 어떤 모델/기능이 비용을 많이 쓰는가?
2. **속도**: 응답이 얼마나 느린가?
3. **병목**: 느린 원인이 RAG 검색인가, LLM 호출인가?

이번 MVP는 이 세 가지를 실제 로컬 LLM 환경에서 확인할 수 있도록 만든 버전이다.
