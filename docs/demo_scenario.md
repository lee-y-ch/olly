# OLLY 발표 데모 시나리오

이 문서는 발표자가 실제 화면을 어떤 순서로 보여주면 되는지 정리한 자료이다.

핵심 흐름:

```text
/chat-ui에서 질문
  ↓
OLLY가 답변과 함께 request_id, trace_id, latency, tokens, cost 기록
  ↓
/dashboard에서 같은 요청 확인
  ↓
분석 챗봇이 Prometheus/Jaeger 데이터를 읽고 원인 설명
```

## 1. 실행

프로젝트 루트에서 실행한다.

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

상태 확인:

```bash
docker compose -f deploy/docker-compose.yml ps
curl http://localhost:8001/health
```

## 2. 접속 주소

| 화면 | 주소 | 발표 역할 |
| --- | --- | --- |
| Chat UI | http://localhost:8001/chat-ui | 사용자가 질문하는 화면 |
| Operator Dashboard | http://localhost:8001/dashboard | 운영자가 상태와 병목을 보는 화면 |
| API Docs | http://localhost:8001/docs | API 구조 설명 |
| Jaeger | http://localhost:16686 | trace 원본 확인 |
| Prometheus | http://localhost:9090 | metric 원본 확인 |
| Grafana | http://localhost:3001 | 보조 대시보드 |

Grafana:

```text
id: admin
password: admin
```

## 3. 추천 발표 흐름

### 장면 1: OLLY가 무엇인지 보여주기

1. `/chat-ui`를 연다.
2. 질문을 보낸다.

예시:

```text
현재 상태 요약해줘
```

설명:

> OLLY는 단순히 답변만 만드는 챗봇이 아니라, 뒤에서 metric과 trace를 읽어 운영 상태를 설명합니다.

### 장면 2: 비용 증가 원인 분석

질문:

```text
어제랑 비교해서 비용이 왜 늘었어?
```

확인할 답변:

- 현재 24h 비용
- 이전 24h 비용
- 변화율
- 비용 기여 1위 기능
- 로컬 모델은 token cost가 아니라 infra cost 중심이라는 설명

설명:

> 로컬 gemma3:1b는 OpenAI처럼 토큰당 API 과금이 없습니다. 대신 토큰이 많아지면 모델 실행 시간이 길어지고, 이 시간이 infra_cost로 계산됩니다.

### 장면 3: 토큰 최다 기능 확인

질문:

```text
토큰 제일 많이 쓰는 기능 뭐야?
```

확인할 답변:

- 1위 기능
- 전체 토큰 중 비중
- 2위 기능

설명:

> 운영자는 어떤 기능이 비용과 지연을 키우는지 기능 단위로 볼 수 있습니다.

### 장면 4: RAG와 LLM 중 어디가 느린지 비교

질문:

```text
RAG가 느린 거야, 모델이 느린 거야?
```

확인할 답변:

- `retrieve p95`
- `llm_call p95`
- 어느 단계가 더 큰지

설명:

> 막연히 LLM이 느리다고 말하지 않고, retrieve와 llm_call을 분리해서 원인을 판단합니다.

### 장면 5: 최근 요청 상세 추적

질문:

```text
가장 느린 요청 목록 보여줘
```

그 다음:

```text
방금 요청 왜 느렸어?
```

확인할 답변:

- request_id
- trace_id
- latency
- tokens
- cost
- 가장 긴 단계

설명:

> 운영자는 request_id와 trace_id를 기준으로 특정 요청을 끝까지 추적할 수 있습니다.

### 장면 6: 운영자 대시보드 확인

1. `/dashboard`로 이동한다.
2. Recent Requests에서 방금 요청을 선택한다.
3. Trace Detail waterfall을 본다.

확인할 것:

```text
Retrieve
LLM Generation
Post-process
```

설명:

> Chat UI는 사용자의 화면이고, Dashboard는 운영자의 화면입니다. 두 화면은 request_id와 trace_id로 연결됩니다.

### 장면 7: 알림 확인

질문:

```text
최근 알림 떠 있어?
```

확인할 답변:

- Prometheus alert 상태
- firing alert 이름
- 다음에 확인할 요청/trace

## 4. 보조 도구 설명

### Jaeger

```text
http://localhost:16686
```

확인할 것:

```text
Service: olly-sample-api
Operation: POST /chat
Span: retrieve, llm_call, postprocess
```

### Prometheus

```promql
sum(increase(olly_requests_total[1h]))
sum(increase(olly_tokens_total[1h])) by (feature)
sum(increase(olly_cost_usd_total[1h])) by (feature)
histogram_quantile(0.95, sum by (stage, le) (increase(olly_stage_duration_seconds_bucket[1h])))
```

### Grafana

Grafana는 발표 필수 화면이 아니라 보조 검증 화면이다.

## 5. 발표자가 외울 핵심 문장

> OLLY는 LLM 요청을 request_id와 trace_id로 추적하고, Prometheus/Jaeger 데이터를 읽어 비용, 토큰, 지연, 실패, 알림 원인을 설명합니다.
