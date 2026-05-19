# OLLY MVP 데모 시나리오

## 1. 전체 서비스 실행

```bash
docker compose -f deploy/docker-compose.yml up --build
```

기본 LLM은 Ollama `gemma3:1b`입니다. 첫 실행에서는 모델 다운로드가 먼저 진행됩니다.

## 2. 접속 주소

| 도구 | 주소 |
| --- | --- |
| API 문서 | http://localhost:8001/docs |
| Ollama | http://localhost:11434 |
| Prometheus | http://localhost:9090 |
| Jaeger | http://localhost:16686 |
| Grafana | http://localhost:3001 |

Grafana 기본 계정:

```text
id: admin
password: admin
```

## 3. 정상 요청 보내기

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"OLLY가 뭐야?","feature":"chat","scenario":"normal"}'
```

## 4. 느린 retrieve 요청 보내기

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"왜 응답이 느려?","feature":"chat","scenario":"slow_retrieve"}'
```

## 5. 토큰 많이 쓰는 요청 보내기

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"OLLY를 길게 설명해줘","feature":"chat","scenario":"high_token"}'
```

## 6. 실패 요청 보내기

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"에러 상황을 보여줘","feature":"chat","scenario":"error"}'
```

## 7. 발표 흐름

1. `/chat` API에 여러 시나리오 요청을 보낸다.
2. Grafana에서 총 요청 수, 토큰 수, 예상 비용, p95 latency가 증가하는지 확인한다.
3. `Cost Breakdown`에서 로컬 모델의 API 토큰 비용은 0이고, 추론 시간 기반 인프라 비용이 증가하는지 확인한다.
4. `Bottleneck by Stage p95`에서 `retrieve`, `llm_call`, `postprocess` 중 어느 단계가 느린지 확인한다.
5. Jaeger에서 `olly-sample-api` 서비스를 선택한다.
6. 느린 trace를 하나 열고 `retrieve`, `llm_call`, `postprocess` span을 확인한다.
7. `slow_retrieve` 요청에서는 retrieve 단계가 병목임을 설명한다.
8. `high_token` 요청에서는 token과 cost metric이 증가하는 것을 설명한다.
9. Grafana에서 `LLM p95 Duration`, `Generation Tokens/sec` 패널로 `gemma3:1b`의 로컬 생성 성능을 확인한다.

## 8. 발표 설명 예시

> 사용자가 보기에는 단순히 응답이 느린 상황입니다. 하지만 OLLY를 보면 이 요청이 어떤 모델을 사용했고, 토큰을 얼마나 썼고, 비용이 얼마였고, 어느 단계에서 느려졌는지 확인할 수 있습니다. 운영자는 Grafana에서 전체 추세를 보고 Jaeger에서 개별 요청의 병목을 추적할 수 있습니다.
