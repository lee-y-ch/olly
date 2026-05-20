# OLLY 로컬 gemma3:1b 실행 가이드

이 문서는 팀원이 각자 로컬 PC에서 OLLY를 실행하고 같은 화면을 확인할 수 있도록 정리한 가이드이다.

## 1. 필요한 프로그램

필수:

- Docker Desktop
- Docker Compose v2
- Git

권장 사양:

- RAM 8GB 이상, 16GB 권장
- 디스크 여유 공간 8GB 이상
- 첫 실행 시 모델과 Docker 이미지를 다운로드할 인터넷 연결

확인 명령:

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

프로젝트 루트에는 아래 파일과 폴더가 있어야 한다.

```text
README.md
apps/
deploy/
docs/
observability/
```

## 3. 전체 서비스 실행

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

첫 실행에서는 아래 작업이 자동으로 진행된다.

- FastAPI 샘플 API 이미지 빌드
- Ollama 컨테이너 실행
- `gemma3:1b` 모델 다운로드
- OpenTelemetry Collector 실행
- Prometheus 실행
- Jaeger 실행
- Grafana 실행

모델 다운로드가 끝난 뒤 `sample-llm-api`가 시작된다. 첫 실행은 몇 분 걸릴 수 있다.

## 4. 실행 상태 확인

```bash
docker compose -f deploy/docker-compose.yml ps
```

정상이라면 아래 컨테이너가 `Up` 상태여야 한다.

```text
olly-sample-llm-api
olly-ollama
olly-otel-collector
olly-prometheus
olly-jaeger
olly-grafana
```

API 상태 확인:

```bash
curl http://localhost:8001/health
```

정상 응답 예:

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

Grafana 로그인:

```text
id: admin
password: admin
```

## 6. 화면으로 테스트하기

가장 쉬운 테스트 방법:

1. `http://localhost:8001/chat-ui` 접속
2. 왼쪽에서 `Normal Request` 선택
3. 예시 질문 클릭
4. 전송
5. 답변 아래 metadata 확인
6. `Operator Dashboard` 클릭
7. `Recent Requests`에서 방금 요청 확인

## 7. curl로 테스트하기

정상 요청:

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"OLLY가 뭐야?","feature":"chat","scenario":"normal"}'
```

RAG 검색 느림:

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"OpenAI가 느린 것인가, 우리 RAG가 느린 것인가?","feature":"rag_qa","scenario":"slow_retrieve"}'
```

LLM 응답 느림:

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"응답이 느린 원인을 찾아줘.","feature":"chat","scenario":"slow_llm"}'
```

토큰 많이 쓰는 요청:

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"어제 왜 비용이 2배가 됐는지 자세히 분석해줘.","feature":"summary","scenario":"high_token"}'
```

실패 요청:

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"이 요청은 왜 실패했어?","feature":"chat","scenario":"error"}'
```

## 8. 비용 계산 기준

현재 모델은 로컬 Ollama `gemma3:1b`이다.

외부 API 과금이 없으므로 token cost는 0이다.

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

확인:

```bash
lsof -i :8001
lsof -i :11434
lsof -i :3001
lsof -i :9090
lsof -i :16686
```

해결:

- 기존 프로세스를 종료한다.
- 또는 `deploy/docker-compose.yml`에서 포트 매핑을 바꾼다.

### `sample-llm-api`가 늦게 뜨는 경우

첫 실행에서는 모델 다운로드가 끝나야 API가 시작된다.

확인:

```bash
docker logs olly-ollama-pull-gemma
docker compose -f deploy/docker-compose.yml ps
```

### API 요청이 500으로 실패하는 경우

로그 확인:

```bash
docker logs olly-sample-llm-api
docker logs olly-ollama
```

모델 확인:

```bash
curl http://localhost:11434/api/tags
```

`gemma3:1b`가 없으면 다시 pull한다.

```bash
docker compose -f deploy/docker-compose.yml run --rm ollama-pull-gemma
```

## 10. 서비스 중지

컨테이너만 중지:

```bash
docker compose -f deploy/docker-compose.yml down
```

모델 데이터까지 삭제:

```bash
docker compose -f deploy/docker-compose.yml down -v
```

`down -v`를 실행하면 `gemma3:1b` 모델도 삭제된다. 다음 실행 때 다시 다운로드한다.

## 11. 팀원 체크리스트

- Docker Desktop이 실행 중이다.
- 프로젝트 루트에서 명령을 실행했다.
- `docker compose -f deploy/docker-compose.yml ps`에서 주요 컨테이너가 `Up` 상태다.
- `curl http://localhost:8001/health` 응답의 model이 `gemma3:1b`다.
- `/chat-ui`에서 질문을 보낼 수 있다.
- `/dashboard`에서 최근 요청이 보인다.
- Recent Requests를 클릭하면 단계별 병목이 보인다.

