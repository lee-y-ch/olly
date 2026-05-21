# OLLY 로컬 gemma3:1b 실행 가이드

이 문서는 팀원이 로컬 PC에서 같은 환경으로 OLLY를 실행하기 위한 가이드이다.

## 1. 필요한 프로그램

필수:

- Docker Desktop
- Docker Compose v2
- Git

권장:

- RAM 8GB 이상, 16GB 권장
- 디스크 여유 공간 8GB 이상
- 첫 실행 시 인터넷 연결

확인:

```bash
docker --version
docker compose version
git --version
```

## 2. 프로젝트 받기

```bash
git clone https://github.com/lee-y-ch/olly.git
cd olly
```

## 3. 전체 실행

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

첫 실행에서는 다음 작업이 자동으로 진행된다.

- FastAPI 이미지 빌드
- Ollama 컨테이너 실행
- `gemma3:1b` 모델 다운로드
- OpenTelemetry Collector 실행
- Prometheus 실행
- Jaeger 실행
- Grafana 실행

첫 실행은 모델 다운로드 때문에 몇 분 걸릴 수 있다.

## 4. 상태 확인

```bash
docker compose -f deploy/docker-compose.yml ps
```

정상 컨테이너:

```text
olly-sample-llm-api
olly-ollama
olly-otel-collector
olly-prometheus
olly-jaeger
olly-grafana
```

API 확인:

```bash
curl http://localhost:8001/health
```

정상 예:

```json
{
  "status": "ok",
  "llm_backend": "ollama",
  "model": "gemma3:1b",
  "compute_resource": "cpu",
  "compute_hourly_usd": "0.05"
}
```

## 5. 접속 주소

| 화면 | 주소 | 용도 |
| --- | --- | --- |
| 사용자 챗봇 UI | http://localhost:8001/chat-ui | 질문 전송 |
| 운영자 대시보드 | http://localhost:8001/dashboard | 비용/토큰/병목 확인 |
| API 문서 | http://localhost:8001/docs | API 직접 테스트 |
| Ollama | http://localhost:11434 | 로컬 LLM 서버 |
| Prometheus | http://localhost:9090 | metric 원본 |
| Jaeger | http://localhost:16686 | trace 원본 |
| Grafana | http://localhost:3001 | 보조 대시보드 |

Grafana:

```text
id: admin
password: admin
```

## 6. 화면 테스트

1. `http://localhost:8001/chat-ui` 접속
2. 질문 입력
3. 답변 아래 metadata 확인
4. `Operator Dashboard` 클릭
5. Recent Requests에서 방금 요청 확인
6. Trace Detail에서 병목 단계 확인

추천 질문:

```text
현재 상태 요약해줘
어제랑 비교해서 비용이 왜 늘었어?
토큰 제일 많이 쓰는 기능 뭐야?
RAG가 느린 거야, 모델이 느린 거야?
가장 느린 요청 목록 보여줘
최근 알림 떠 있어?
```

## 7. curl 테스트

상태 요약:

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"현재 상태 요약해줘","feature":"chat","scenario":"normal"}'
```

비용 비교:

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"어제랑 비교해서 비용이 왜 늘었어?","feature":"chat","scenario":"normal"}'
```

RAG vs LLM:

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"RAG가 느린 거야, 모델이 느린 거야?","feature":"rag_qa","scenario":"normal"}'
```

알림 확인:

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"최근 알림 떠 있어?","feature":"chat","scenario":"normal"}'
```

데모용 실패 요청:

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"이 요청은 왜 실패했어?","feature":"chat","scenario":"error"}'
```

## 8. 비용 계산 기준

현재 모델은 로컬 Ollama `gemma3:1b`이다.

```text
token_cost_usd = 0
infra_cost_usd = LLM 실행 시간(초) / 3600 * 시간당 장비 비용
```

기본 설정:

```yaml
LOCAL_COMPUTE_RESOURCE: cpu
LOCAL_COMPUTE_HOURLY_USD: "0.05"
```

GPU 기준으로 실험하려면 `deploy/docker-compose.yml`에서 아래 값을 바꾼다.

```yaml
LOCAL_COMPUTE_RESOURCE: gpu
LOCAL_COMPUTE_HOURLY_USD: "0.50"
```

## 9. 자주 나는 문제

### 포트가 이미 사용 중인 경우

```bash
lsof -i :8001
lsof -i :11434
lsof -i :3001
lsof -i :9090
lsof -i :16686
```

### 모델 다운로드가 오래 걸리는 경우

```bash
docker logs olly-ollama-pull-gemma
docker compose -f deploy/docker-compose.yml ps
```

### API 요청이 500으로 실패하는 경우

```bash
docker logs olly-sample-llm-api
docker logs olly-ollama
curl http://localhost:11434/api/tags
```

### 대시보드 데이터가 바로 안 보이는 경우

Prometheus와 Jaeger 반영에 몇 초 걸릴 수 있다. 질문을 한두 번 더 보내고 새로고침한다.
