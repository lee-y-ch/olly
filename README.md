# OLLY

OLLY는 LLM 서비스의 비용, 속도, 병목을 실시간으로 확인하는 MVP 관측성 프로젝트입니다.

## 실행

```bash
docker compose -f deploy/docker-compose.yml up --build
```

## 접속 주소

| 도구 | 주소 |
| --- | --- |
| Sample API | http://localhost:8001/docs |
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

## 주요 문서

- [MVP 진행 계획](docs/MVP_진행계획.md)
- [데모 시나리오](docs/demo_scenario.md)
