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
| OLLY 통합 웹 대시보드 | http://localhost:8001/dashboard |
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

1. `http://localhost:8001/dashboard`를 연다.
2. 왼쪽의 `데모 요청 생성`에서 `normal`, `slow_retrieve`, `high_token`, `error`를 실행한다.
3. 상단 카드에서 총 요청 수, 토큰 수, 예상 비용, p95 latency, 에러율이 바뀌는지 확인한다.
4. `비용 분석`에서 기능별 비용과 로컬 추론 시간 기반 인프라 비용을 설명한다.
5. `단계별 병목 분석`에서 `retrieve`, `llm_call`, `postprocess` 중 어느 단계가 느린지 확인한다.
6. `최근 요청 내역`에서 느린 요청을 클릭한다.
7. 오른쪽 상세 패널에서 요청 하나의 waterfall을 확인한다.
8. 더 자세한 trace가 필요하면 `Open in Jaeger`를 눌러 Jaeger 원본 trace를 연다.
9. 필요하면 Grafana, Prometheus, Jaeger를 각각 열어 원본 도구와 통합 대시보드가 같은 데이터를 보고 있음을 보여준다.

## 8. 발표 설명 예시

> 사용자가 보기에는 단순히 응답이 느린 상황입니다. 하지만 OLLY를 보면 이 요청이 어떤 모델을 사용했고, 토큰을 얼마나 썼고, 비용이 얼마였고, 어느 단계에서 느려졌는지 확인할 수 있습니다. 운영자는 Grafana에서 전체 추세를 보고 Jaeger에서 개별 요청의 병목을 추적할 수 있습니다.
