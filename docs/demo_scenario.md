# OLLY MVP 데모 시나리오

이 문서는 발표자가 실제 화면을 어떤 순서로 보여주면 되는지 정리한 자료이다.

핵심 발표 흐름은 간단하다.

```text
사용자가 /chat-ui에서 질문한다.
  ↓
OLLY가 뒤에서 비용, 토큰, latency, trace를 기록한다.
  ↓
운영자는 /dashboard에서 방금 요청의 병목을 확인한다.
```

## 1. 전체 서비스 실행

프로젝트 루트에서 실행한다.

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

첫 실행에서는 Ollama `gemma3:1b` 모델을 다운로드하므로 시간이 걸릴 수 있다.

상태 확인:

```bash
docker compose -f deploy/docker-compose.yml ps
```

## 2. 접속 주소

| 화면 | 주소 | 발표에서의 역할 |
| --- | --- | --- |
| 사용자 챗봇 UI | http://localhost:8001/chat-ui | 사용자가 질문하는 화면 |
| 운영자 대시보드 | http://localhost:8001/dashboard | 비용, 토큰, 병목 확인 |
| API 문서 | http://localhost:8001/docs | 개발자용 API 테스트 |
| Jaeger | http://localhost:16686 | trace 원본 확인 |
| Prometheus | http://localhost:9090 | metric 원본 확인 |
| Grafana | http://localhost:3001 | 보조 대시보드 |

Grafana 기본 계정:

```text
id: admin
password: admin
```

## 3. 발표 메인 시나리오: RAG 병목 찾기

가장 추천하는 발표 흐름이다.

1. `http://localhost:8001/chat-ui`를 연다.
2. 왼쪽 `Scenario Selection`에서 `Slow Retrieval (RAG)`를 선택한다.
3. `Example Questions`에서 `Is OpenAI slow or our RAG?`를 클릭한다.
4. 전송 버튼을 누른다.
5. 답변 아래의 metadata를 설명한다.

확인할 metadata:

```text
REQ: request_id
TRACE: trace_id
LATENCY: 응답 시간
TOKENS: 입력 + 출력 토큰
COST: 로컬 추론 시간 기반 비용
MODEL: gemma3:1b
```

6. 상단 `Operator Dashboard`를 클릭한다.
7. `Recent Requests`에서 방금 요청을 클릭한다.
8. 오른쪽 `Trace Detail`을 본다.
9. `Retrieve` 막대가 길면 아래처럼 설명한다.

> 사용자는 단순히 질문을 했지만, OLLY는 요청 내부 단계를 기록했습니다. 이 요청은 LLM 생성보다 RAG 검색 단계인 Retrieve가 병목입니다.

## 4. 추가 시나리오

### 4.1 정상 요청

목적: OLLY가 기본 요청을 정상적으로 기록하는지 보여준다.

1. `/chat-ui`에서 `Normal Request` 선택
2. 아무 예시 질문 선택
3. 전송
4. `/dashboard`에서 latency와 cost가 낮은 요청 확인

설명 문장:

> 정상 요청도 request_id와 trace_id가 붙어서 운영 대시보드에 남습니다.

### 4.2 LLM 응답 느림

목적: RAG가 아니라 모델 생성 단계가 느린 상황을 보여준다.

1. `/chat-ui`에서 `Slow LLM Response` 선택
2. `Find the bottleneck.` 질문 선택
3. 전송
4. `/dashboard`에서 `LLM Generation` 막대 확인

설명 문장:

> 이 경우에는 검색보다 LLM Generation 단계가 길기 때문에 모델 호출 또는 생성 속도가 병목입니다.

### 4.3 토큰 과다 사용

목적: 토큰 사용량과 비용 증가를 보여준다.

1. `/chat-ui`에서 `High Token Usage` 선택
2. `Why did cost double yesterday?` 질문 선택
3. 전송
4. `/dashboard`에서 `Total Tokens`, `Total Cost`, `Cost Analysis` 확인

설명 문장:

> 로컬 LLM은 API 토큰 과금은 없지만, 토큰이 많아질수록 추론 시간이 늘고 인프라 비용 추정치가 증가할 수 있습니다.

### 4.4 실패 요청

목적: 실패한 요청도 관측 데이터에 남는지 보여준다.

1. `/chat-ui`에서 `Error Occurred` 선택
2. `Why did this fail?` 질문 선택
3. 전송
4. `/dashboard`에서 status가 `ERROR`인 요청 확인

설명 문장:

> 실패 요청도 운영 관점에서는 중요합니다. OLLY는 성공 요청뿐 아니라 실패 요청도 Recent Requests와 error metric에 기록합니다.

## 5. 보조 도구 확인

발표 시간이 남거나 기술 검증을 보여주고 싶을 때만 사용한다.

### Jaeger

주소:

```text
http://localhost:16686
```

확인할 것:

```text
Service: olly-sample-api
Operation: POST /chat
Spans:
  - retrieve
  - llm_call
  - postprocess
```

### Prometheus

주소:

```text
http://localhost:9090
```

추천 쿼리:

```promql
sum(olly_requests_total)
```

```promql
sum(olly_tokens_total) by (token_type)
```

```promql
sum(olly_cost_usd_total)
```

### Grafana

주소:

```text
http://localhost:3001
```

Grafana는 자체 `/dashboard`와 같은 metric을 보는 보조 화면이다.

## 6. 발표자가 기억할 핵심 문장

> OLLY는 사용자가 보낸 LLM 요청을 request_id와 trace_id로 추적하고, 토큰 사용량, 로컬 추론 비용, 응답 시간, 단계별 병목을 운영자 대시보드에서 보여줍니다.

