# OLLY

OLLY는 LLM 서비스의 비용, 속도, 병목을 실시간으로 확인하는 MVP 관측성 프로젝트입니다.

현재 기본 실험 모델은 Docker Compose 안에서 실행되는 Ollama `gemma3:1b`입니다.

## 실행

```bash
docker compose -f deploy/docker-compose.yml up --build
```

첫 실행 때는 `gemma3:1b` 모델을 내려받기 때문에 시간이 조금 걸릴 수 있습니다.

## 접속 주소

| 도구 | 주소 |
| --- | --- |
| Sample API | http://localhost:8001/docs |
| Ollama | http://localhost:11434 |
| Prometheus | http://localhost:9090 |
| Jaeger | http://localhost:16686 |
| Grafana | http://localhost:3001 |

Grafana 기본 계정은 `admin` / `admin`입니다.

## 테스트 요청

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"OLLY가 뭐야?","feature":"chat","scenario":"normal"}'
```

지원하는 `scenario` 값:

| scenario | 의미 |
| --- | --- |
| `normal` | 정상 요청 |
| `slow_retrieve` | retrieve 단계가 느린 요청 |
| `slow_llm` | llm_call 단계가 느린 요청 |
| `high_token` | 토큰을 많이 쓰는 요청 |
| `error` | 실패 요청 |

## LLM 백엔드

기본값은 실제 로컬 SLM 실험을 위한 Ollama입니다.

| 환경변수 | 기본값 | 의미 |
| --- | --- | --- |
| `LLM_BACKEND` | `ollama` | `ollama` 또는 `mock` |
| `OLLAMA_MODEL` | `gemma3:1b` | Ollama 모델명 |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Docker Compose 내부 Ollama 주소 |
| `LOCAL_COMPUTE_RESOURCE` | `cpu` | 로컬 추론 리소스 이름. 예: `cpu`, `gpu` |
| `LOCAL_COMPUTE_HOURLY_USD` | `0.05` | 로컬 추론 리소스의 시간당 추정 비용 |

로컬에서 API만 직접 실행하면서 mock을 쓰고 싶으면 `LLM_BACKEND=mock`으로 실행하면 됩니다.

로컬 모델은 API 토큰 과금이 없으므로 OLLY는 아래 방식으로 비용을 추정합니다.

```text
local infra cost = LLM 실행 시간(초) / 3600 * 시간당 장비 비용
```

## 주요 문서

- [MVP 진행 계획](docs/MVP_진행계획.md)
- [데모 시나리오](docs/demo_scenario.md)
- [로컬 gemma3:1b 실험 환경 설정 가이드](docs/local_gemma3_setup.md)
