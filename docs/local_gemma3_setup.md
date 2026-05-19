# OLLY 로컬 gemma3:1b 실험 환경 설정 가이드

이 문서는 팀원이 각자 로컬 PC에서 OLLY와 Ollama `gemma3:1b` 모델을 실행하고, Grafana/Jaeger/Prometheus로 성능을 확인하는 방법을 정리한 것이다.

## 1. 실행 환경

필수 설치:

- Docker Desktop
- Docker Compose v2
- Git

권장 사양:

- RAM 8GB 이상, 16GB 권장
- 디스크 여유 공간 최소 8GB 이상
- 첫 실행 시 모델과 Docker 이미지를 다운로드하므로 인터넷 연결 필요

확인 명령:

```bash
docker --version
docker compose version
git --version
```

## 2. 프로젝트 받기

GitHub 저장소를 사용하는 경우:

```bash
git clone <OLLY_REPOSITORY_URL>
cd OLLY
```

압축 파일로 공유받은 경우에는 압축을 푼 뒤 프로젝트 루트로 이동한다.

```bash
cd /path/to/OLLY
```

프로젝트 루트에는 다음 파일이 있어야 한다.

```text
README.md
deploy/docker-compose.yml
apps/sample-llm-api/
observability/
docs/
```

## 3. 전체 서비스 실행

프로젝트 루트에서 실행한다.

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

첫 실행에서는 다음 작업이 자동으로 진행된다.

- OLLY Sample API 이미지 빌드
- Ollama 컨테이너 실행
- `gemma3:1b` 모델 다운로드
- Prometheus, Jaeger, Grafana 실행

`gemma3:1b` 모델 다운로드가 끝난 뒤 `sample-llm-api`가 시작된다. 첫 실행은 몇 분 걸릴 수 있다.

## 4. 실행 상태 확인

```bash
docker compose -f deploy/docker-compose.yml ps
```

정상이라면 아래 컨테이너들이 `Up` 상태여야 한다.

```text
olly-sample-llm-api
olly-ollama
olly-prometheus
olly-jaeger
olly-grafana
olly-otel-collector
```

API 상태 확인:

```bash
curl http://localhost:8001/health
```

정상 응답:

```json
{
  "status": "ok",
  "llm_backend": "ollama",
  "model": "gemma3:1b"
}
```

Ollama 모델 확인:

```bash
curl http://localhost:11434/api/tags
```

응답 안에 `gemma3:1b`가 있으면 정상이다.

## 5. 테스트 요청 보내기

정상 요청:

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"OLLY가 뭐야?","feature":"chat","scenario":"normal"}'
```

토큰을 더 쓰는 요청:

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"OLLY에서 로컬 LLM 성능을 어떻게 측정해?","feature":"chat","scenario":"high_token"}'
```

느린 retrieve 시나리오:

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"왜 응답이 느려?","feature":"chat","scenario":"slow_retrieve"}'
```

실패 시나리오:

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"에러 상황을 보여줘","feature":"chat","scenario":"error"}'
```

## 6. 접속 주소

| 도구 | 주소 | 용도 |
| --- | --- | --- |
| Sample API | http://localhost:8001/docs | API 테스트 |
| Ollama | http://localhost:11434 | 로컬 LLM 서버 |
| Prometheus | http://localhost:9090 | metric 확인 |
| Jaeger | http://localhost:16686 | trace 확인 |
| Grafana | http://localhost:3001 | 대시보드 확인 |

Grafana 로그인:

```text
id: admin
password: admin
```

## 7. Grafana에서 확인할 것

Grafana 접속 후 `OLLY MVP Dashboard`를 연다.

주요 패널:

- `Total Requests`: 전체 요청 수
- `Total Tokens`: 입력/출력 토큰 합계
- `p95 Latency`: 전체 API p95 응답 시간
- `Requests by Scenario`: 시나리오별 요청 추이
- `Token Usage Trend`: 입력/출력 토큰 추이
- `LLM p95 Duration`: Ollama 모델 호출 구간 p95 시간
- `Generation Tokens/sec`: `gemma3:1b` 생성 속도
- `Cost Breakdown`: API 토큰 비용과 로컬 인프라 비용 분리
- `Local Compute Seconds`: 로컬 CPU/GPU 추론 시간
- `Bottleneck by Stage p95`: `retrieve`, `llm_call`, `postprocess` 단계별 병목
- `Active Alerts`: 현재 firing 중인 알림
- `Jaeger Trace Link`: Jaeger trace 상세 화면으로 이동

로컬 Ollama 모델은 외부 API 비용이 없으므로 토큰 API 비용은 0으로 기록된다. 대신 OLLY는 로컬 추론 시간을 기준으로 인프라 비용을 추정한다.

```text
local infra cost = LLM 실행 시간(초) / 3600 * 시간당 장비 비용
```

기본값은 CPU 시간당 0.05달러로 설정되어 있다.

```yaml
LOCAL_COMPUTE_RESOURCE: cpu
LOCAL_COMPUTE_HOURLY_USD: "0.05"
```

GPU 비용으로 실험하려면 `deploy/docker-compose.yml`에서 아래처럼 바꾸면 된다.

```yaml
LOCAL_COMPUTE_RESOURCE: gpu
LOCAL_COMPUTE_HOURLY_USD: "0.50"
```

## 8. Jaeger에서 확인할 것

1. http://localhost:16686 접속
2. Service에서 `olly-sample-api` 선택
3. `Find Traces` 클릭
4. trace 하나를 열어서 아래 span을 확인

```text
POST /chat
retrieve
llm_call
postprocess
```

`llm_call` span에는 다음 속성이 기록된다.

```text
gen_ai.system = ollama
gen_ai.request.model = gemma3:1b
olly.input_tokens
olly.output_tokens
olly.llm_elapsed_ms
olly.tokens_per_second
olly.ollama_load_duration_seconds
olly.ollama_eval_duration_seconds
olly.token_cost_usd
olly.infra_cost_usd
olly.compute_seconds
olly.compute_resource
```

첫 요청은 모델 로딩 시간이 포함되어 느릴 수 있다. 두 번째 요청부터는 warm 상태의 성능으로 보는 것이 좋다.

## 9. Prometheus에서 직접 확인할 metric

Prometheus 접속:

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

```promql
sum(olly_infra_cost_usd_total) by (resource, model)
```

```promql
histogram_quantile(0.95, sum(rate(olly_request_duration_seconds_bucket[5m])) by (le))
```

```promql
histogram_quantile(0.95, sum(rate(olly_stage_duration_seconds_bucket[5m])) by (le, stage))
```

```promql
histogram_quantile(0.95, sum(rate(olly_llm_duration_seconds_bucket[5m])) by (le, model, backend))
```

```promql
histogram_quantile(0.50, sum(rate(olly_generation_tokens_per_second_bucket[5m])) by (le, model, backend))
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

`down -v`를 실행하면 `gemma3:1b` 모델도 삭제되므로 다음 실행 때 다시 다운로드한다.

## 11. 자주 나는 문제

### 포트가 이미 사용 중인 경우

증상:

```text
port is already allocated
```

확인:

```bash
lsof -i :8001
lsof -i :11434
lsof -i :3001
lsof -i :9090
lsof -i :16686
```

해결:

- 기존에 실행 중인 같은 포트의 프로그램을 종료한다.
- 또는 `deploy/docker-compose.yml`의 포트 매핑을 팀원 PC 상황에 맞게 바꾼다.

### `sample-llm-api`가 늦게 뜨는 경우

첫 실행에서는 `ollama-pull-gemma` 컨테이너가 `gemma3:1b`를 먼저 다운로드한다. 다운로드가 끝나야 API가 시작된다.

상태 확인:

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

Ollama 모델 확인:

```bash
curl http://localhost:11434/api/tags
```

`gemma3:1b`가 없으면 다시 pull한다.

```bash
docker compose -f deploy/docker-compose.yml run --rm ollama-pull-gemma
```

### Docker 메모리가 부족한 경우

Docker Desktop 설정에서 메모리를 6GB 이상으로 올린다. 가능하면 8GB 이상을 권장한다.

### Windows에서 실행하는 경우

Windows에서는 Docker Desktop과 WSL2 기반 실행을 권장한다. 명령은 동일하게 PowerShell 또는 WSL 터미널에서 실행하면 된다.

## 12. 모델 바꾸기

기본 모델은 `gemma3:1b`이다. 다른 모델을 실험하려면 `deploy/docker-compose.yml`에서 아래 값을 바꾼다.

```yaml
OLLAMA_MODEL: gemma3:1b
```

예시:

```yaml
OLLAMA_MODEL: gemma3:4b
```

그리고 pull 컨테이너의 명령도 같은 모델명으로 바꾼다.

```yaml
command: ["until ollama list >/dev/null 2>&1; do sleep 1; done; ollama pull gemma3:4b"]
```

변경 후 다시 실행한다.

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

## 13. 팀원 체크리스트

- Docker Desktop이 실행 중이다.
- 프로젝트 루트에서 명령을 실행했다.
- `docker compose -f deploy/docker-compose.yml ps`에서 주요 컨테이너가 `Up` 상태다.
- `curl http://localhost:8001/health` 응답의 model이 `gemma3:1b`다.
- `/chat` 요청이 성공한다.
- Grafana의 `OLLY MVP Dashboard`에서 요청 수와 토큰 수가 증가한다.
- Jaeger에서 `llm_call` span이 보인다.
