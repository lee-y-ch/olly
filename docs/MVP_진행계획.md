# OLLY MVP 진행 계획

## 1. 프로젝트 한 줄 설명

**OLLY는 LLM 서비스의 비용, 속도, 병목 지점을 실시간으로 확인하는 관측성 플랫폼이다.**

쉽게 말하면, LLM 서비스를 운영할 때 필요한 **계기판**을 만드는 프로젝트이다.

예를 들어 챗봇을 만들었을 때 다음과 같은 문제가 생길 수 있다.

- 갑자기 API 비용이 많이 나옴
- 어떤 요청은 답변이 너무 느림
- HTTP 요청은 성공했지만 답변 내용이 이상함
- RAG 검색이 느린 건지, LLM 호출이 느린 건지 알 수 없음

OLLY는 이런 문제를 확인할 수 있도록 요청마다 비용, 토큰, 응답 시간, 처리 단계를 기록하고 화면으로 보여준다.

## 2. MVP 목표

MVP의 목표는 완성형 서비스를 만드는 것이 아니라, **핵심 가치가 실제로 동작하는 최소 버전**을 만드는 것이다.

이번 MVP에서는 아래 3가지만 확실히 보여주면 된다.

1. LLM 요청의 비용을 볼 수 있다.
2. LLM 요청의 응답 시간을 볼 수 있다.
3. 요청이 어느 단계에서 느려졌는지 추적할 수 있다.

즉, 최종 데모에서 다음 문장을 증명하면 된다.

> 이 요청은 어떤 모델을 사용했고, 토큰을 얼마나 썼고, 비용이 얼마였고, 어느 단계에서 느려졌는지 확인할 수 있다.

## 3. 전체 구조

```text
사용자 질문
  ↓
샘플 LLM API
  ↓
OpenTelemetry로 요청 정보 기록
  ↓
OpenTelemetry Collector가 데이터 수집
  ↓
Prometheus: 숫자 데이터 저장
Jaeger: 요청 흐름 추적
Grafana: 대시보드 시각화
  ↓
비용, 속도, 병목 확인
```

## 4. 사용하는 기술과 역할

| 기술 | 역할 |
| --- | --- |
| FastAPI | 샘플 LLM API 서버 |
| OpenTelemetry | 요청 처리 과정 기록 |
| OpenTelemetry Collector | 기록된 데이터 수집 및 전달 |
| Prometheus | 비용, 토큰, 응답 시간 같은 숫자 저장 |
| Jaeger | 요청 하나가 어떤 단계를 거쳤는지 추적 |
| Grafana | 대시보드 화면 구성 |
| Docker Compose | 여러 서비스를 한 번에 실행 |
| Kubernetes / Helm | 최종적으로 클라우드 네이티브 배포 구조 설명 |

## 5. MVP 구현 범위

### 포함할 것

- `/chat` API
- Mock LLM 응답
- 요청별 토큰 수 계산
- 요청별 예상 비용 계산
- 요청별 응답 시간 측정
- 처리 단계별 trace 기록
- Prometheus metric 연동
- Jaeger trace 연동
- Grafana dashboard 구성
- Docker Compose 실행 환경
- 발표용 데모 시나리오

### 이번 MVP에서 제외할 것

- 실제 SaaS 수준의 사용자 로그인
- 실제 결제 기능
- 복잡한 권한 관리
- 완벽한 hallucination 판별
- 운영용 대규모 Kubernetes 배포
- 모든 LLM 벤더 연동

이 기능들은 나중에 확장할 수 있지만, MVP에서는 핵심 흐름을 먼저 완성하는 것이 중요하다.

## 6. 구현 단계

### 1단계: 샘플 LLM API 만들기

먼저 `/chat` API를 만든다.

요청 예시:

```json
{
  "question": "OLLY가 뭐야?"
}
```

응답 예시:

```json
{
  "answer": "OLLY는 LLM 운영 관측성 플랫폼입니다.",
  "model": "gpt-4o-mini",
  "input_tokens": 120,
  "output_tokens": 80,
  "cost_usd": 0.00004,
  "latency_ms": 850
}
```

처음에는 실제 OpenAI API를 쓰지 않고 Mock LLM으로 만든다. 발표 데모에서는 외부 API 장애나 비용 문제를 피할 수 있어서 더 안정적이다.

### 2단계: 요청 처리 단계를 나누기

LLM 요청을 한 번에 처리하지 않고, 일부러 단계별로 나눈다.

```text
/chat 요청
  ↓
retrieve
  ↓
llm_call
  ↓
postprocess
  ↓
응답 반환
```

이렇게 나누면 Jaeger에서 어느 단계가 느린지 확인할 수 있다.

예시:

```text
전체 응답 시간: 2.4초
retrieve: 1.5초
llm_call: 0.7초
postprocess: 0.2초
```

이 경우 발표에서 다음처럼 설명할 수 있다.

> 응답이 느린 원인은 LLM 모델이 아니라 retrieve 단계였다.

### 3단계: OpenTelemetry 계측 붙이기

각 요청과 단계에 OpenTelemetry 기록을 붙인다.

기록할 주요 정보:

- 모델명
- 기능명
- 입력 토큰 수
- 출력 토큰 수
- 예상 비용
- 응답 시간
- 성공 여부
- 에러 정보

이 단계가 OLLY의 핵심이다. 단순히 API를 만드는 것이 아니라, API가 어떻게 동작했는지 관찰할 수 있게 만드는 것이다.

### 4단계: Prometheus metric 저장

Prometheus에는 숫자 데이터를 저장한다.

예시 metric:

- 총 요청 수
- 평균 응답 시간
- p95 응답 시간
- 모델별 토큰 사용량
- 모델별 예상 비용
- 기능별 요청 수
- 에러율

Prometheus는 나중에 Grafana가 그래프를 그릴 때 사용하는 데이터 저장소 역할을 한다.

### 5단계: Jaeger trace 확인

Jaeger에서는 요청 하나의 상세 흐름을 확인한다.

예시:

```text
POST /chat
  ├─ retrieve: 1.5s
  ├─ llm_call: 0.7s
  └─ postprocess: 0.2s
```

Prometheus가 전체 통계를 보는 도구라면, Jaeger는 요청 하나를 깊게 분석하는 도구이다.

### 6단계: Grafana 대시보드 만들기

Grafana에는 MVP용 대시보드를 만든다.

대시보드에 들어갈 항목:

- 오늘 총 요청 수
- 오늘 총 토큰 수
- 오늘 예상 비용
- 모델별 비용
- 기능별 요청 수
- p95 응답 시간
- 에러율
- 최근 느린 요청

발표에서는 Grafana 화면을 통해 “LLM 서비스의 상태를 한눈에 볼 수 있다”는 점을 보여준다.

### 7단계: Alert rule 추가

운영 상황을 가정해서 알림 조건을 만든다.

예시:

- 최근 5분 p95 응답 시간이 3초 초과
- 에러율이 5% 초과
- 특정 기능의 토큰 사용량 급증
- 예상 비용이 기준치 초과

MVP에서는 실제 Slack 알림까지는 필수는 아니다. Grafana나 Prometheus에서 alert 상태를 보여주는 것만으로도 충분하다.

### 8단계: Docker Compose로 실행

마지막으로 모든 서비스를 한 번에 실행할 수 있게 만든다.

```bash
docker compose up
```

실행되는 서비스:

- sample-llm-api
- otel-collector
- prometheus
- jaeger
- grafana

## 7. 예상 폴더 구조

```text
OLLY/
  apps/
    sample-llm-api/
      app/
      Dockerfile
      requirements.txt

  observability/
    otel-collector.yaml
    prometheus.yml
    alert-rules.yml
    grafana/
      dashboards/
      provisioning/

  deploy/
    docker-compose.yml
    helm/

  docs/
    MVP_진행계획.md
    demo_scenario.md
```

## 8. 팀원별 병렬 작업 계획

4명이 동시에 작업하려면 각자 맡는 파일과 책임 범위를 분리해야 한다. 아래처럼 나누면 서로 기다리는 시간을 줄일 수 있다.

### 공통으로 먼저 맞춰야 하는 약속

개발을 시작하기 전에 아래 값은 팀 전체가 동일하게 사용한다.

| 항목 | 값 |
| --- | --- |
| API 서버 포트 | 컨테이너 내부 `8000`, 로컬 접속 `8001` |
| API 엔드포인트 | `POST /chat` |
| Prometheus 포트 | `9090` |
| Jaeger UI 포트 | `16686` |
| Grafana 포트 | 컨테이너 내부 `3000`, 로컬 접속 `3001` |
| 서비스 이름 | `olly-sample-api` |
| 기본 feature 이름 | `chat` |
| 기본 model 이름 | `gpt-4o-mini-mock` |

공통 응답 형식은 아래처럼 맞춘다.

```json
{
  "request_id": "req_001",
  "answer": "OLLY는 LLM 운영 관측성 플랫폼입니다.",
  "model": "gpt-4o-mini-mock",
  "feature": "chat",
  "input_tokens": 120,
  "output_tokens": 80,
  "cost_usd": 0.00004,
  "latency_ms": 850,
  "status": "success"
}
```

공통 trace 단계 이름은 아래 3개로 고정한다.

```text
retrieve
llm_call
postprocess
```

공통 metric 이름은 아래처럼 시작한다.

```text
olly_requests_total
olly_request_duration_seconds
olly_tokens_total
olly_cost_usd_total
olly_errors_total
```

### 1번 팀원: 샘플 LLM API / Mock LLM 로직

#### 책임

LLM 서비스 역할을 하는 FastAPI 서버를 만든다. 실제 OpenAI API를 호출하지 않고, 발표에서 안정적으로 보여줄 수 있는 Mock LLM을 구현한다.

#### 담당 경로

```text
apps/sample-llm-api/
  app/
    main.py
    schemas.py
    mock_llm.py
    pricing.py
  requirements.txt
  Dockerfile
```

#### 해야 할 일

- `POST /chat` API 구현
- 질문을 받으면 Mock 답변 반환
- 요청마다 `request_id` 생성
- 입력 토큰 수 계산
- 출력 토큰 수 계산
- 모델별 예상 비용 계산
- 일부 요청을 일부러 느리게 만드는 옵션 추가
- 일부 요청을 일부러 토큰 많이 쓰게 만드는 옵션 추가
- 일부 요청을 일부러 에러로 만드는 옵션 추가

#### 요청 예시

```json
{
  "question": "OLLY가 뭐야?",
  "feature": "chat",
  "scenario": "normal"
}
```

`scenario` 값은 아래처럼 사용한다.

| scenario | 의미 |
| --- | --- |
| `normal` | 정상 요청 |
| `slow_retrieve` | retrieve 단계가 느린 요청 |
| `slow_llm` | llm_call 단계가 느린 요청 |
| `high_token` | 토큰을 많이 쓰는 요청 |
| `error` | 실패 요청 |

#### 완료 기준

- `curl`로 `/chat` 요청을 보냈을 때 JSON 응답이 온다.
- `normal`, `slow_retrieve`, `slow_llm`, `high_token`, `error` 시나리오가 동작한다.
- 응답에 `input_tokens`, `output_tokens`, `cost_usd`, `latency_ms`가 포함된다.
- Dockerfile로 API 서버 이미지를 만들 수 있다.

#### 다른 팀원과 연결되는 지점

- 2번 팀원이 OpenTelemetry를 붙일 수 있도록 `retrieve`, `llm_call`, `postprocess` 함수를 분리해둔다.
- 3번 팀원이 metric을 쓸 수 있도록 응답 필드 이름을 바꾸지 않는다.
- 4번 팀원이 Docker Compose에 연결할 수 있도록 서버 포트는 `8000`으로 유지한다.

### 2번 팀원: OpenTelemetry 계측 / Collector / Jaeger 연결

#### 책임

샘플 API에서 발생하는 요청 정보를 OpenTelemetry로 기록하고, Collector를 통해 Jaeger와 Prometheus로 전달한다.

#### 담당 경로

```text
apps/sample-llm-api/app/
  telemetry.py

observability/
  otel-collector.yaml
```

#### 해야 할 일

- FastAPI에 OpenTelemetry instrumentation 적용
- `/chat` 요청마다 trace 생성
- `retrieve`, `llm_call`, `postprocess`를 각각 span으로 기록
- span attribute에 모델명, feature, 토큰 수, 비용, 상태 기록
- OTel Collector 설정 작성
- trace 데이터를 Jaeger로 전달
- metric 데이터를 Prometheus가 가져갈 수 있게 노출

#### span attribute 예시

```text
gen_ai.system = "mock"
gen_ai.request.model = "gpt-4o-mini-mock"
olly.feature = "chat"
olly.input_tokens = 120
olly.output_tokens = 80
olly.cost_usd = 0.00004
olly.scenario = "slow_retrieve"
```

#### 완료 기준

- `/chat` 요청 1개를 보내면 Jaeger에서 trace 1개가 보인다.
- Jaeger trace 안에 `retrieve`, `llm_call`, `postprocess` span이 보인다.
- 느린 시나리오에서 실제로 해당 span 시간이 길게 보인다.
- Collector가 에러 없이 실행된다.

#### 다른 팀원과 연결되는 지점

- 1번 팀원이 만든 함수 구조에 계측을 추가한다.
- 3번 팀원이 쓸 metric이 Prometheus로 들어갈 수 있게 export 방식을 맞춘다.
- 4번 팀원이 Compose에 넣을 수 있도록 Collector 설정 파일 경로를 고정한다.

### 3번 팀원: Prometheus / Grafana Dashboard / Alert

#### 책임

수집된 metric을 Prometheus에 저장하고, Grafana에서 발표용 대시보드를 만든다.

#### 담당 경로

```text
observability/
  prometheus.yml
  alert-rules.yml
  grafana/
    dashboards/
      olly-mvp-dashboard.json
    provisioning/
      dashboards/
        dashboard.yml
      datasources/
        datasource.yml
```

#### 해야 할 일

- Prometheus scrape 설정 작성
- API 또는 Collector의 metric endpoint 연결
- Grafana datasource 자동 설정
- Grafana dashboard JSON 작성
- 발표용 panel 구성
- Prometheus alert rule 작성

#### Grafana에 들어갈 panel

| Panel | 보여줄 내용 |
| --- | --- |
| Total Requests | 전체 요청 수 |
| Total Tokens | 전체 토큰 수 |
| Total Cost | 전체 예상 비용 |
| Cost by Model | 모델별 비용 |
| Requests by Feature | 기능별 요청 수 |
| p95 Latency | p95 응답 시간 |
| Error Rate | 에러율 |
| Token Usage Trend | 시간대별 토큰 사용량 |

#### Alert rule 예시

```text
최근 5분 p95 응답 시간이 3초 초과
최근 5분 에러율이 5% 초과
최근 10분 예상 비용이 기준치 초과
최근 10분 토큰 사용량이 기준치 초과
```

#### 완료 기준

- Prometheus UI에서 OLLY metric을 조회할 수 있다.
- Grafana에 Prometheus datasource가 자동 등록된다.
- Grafana dashboard가 자동 import된다.
- `/chat` 요청을 여러 번 보내면 dashboard 숫자와 그래프가 변한다.
- alert rule이 Prometheus에서 로드된다.

#### 다른 팀원과 연결되는 지점

- 2번 팀원이 노출한 metric 이름을 기준으로 dashboard를 만든다.
- 4번 팀원이 Compose에서 Grafana volume을 연결할 수 있도록 provisioning 경로를 맞춘다.
- 발표자는 dashboard panel 이름을 그대로 발표 시나리오에 사용한다.

### 4번 팀원: Docker Compose / 실행 문서 / 발표 데모

#### 책임

전체 서비스를 한 번에 실행할 수 있게 만들고, 팀원이 같은 방식으로 데모를 재현할 수 있도록 문서화한다.

#### 담당 경로

```text
deploy/
  docker-compose.yml
  helm/

docs/
  demo_scenario.md
  runbook.md

README.md
```

#### 해야 할 일

- Docker Compose 작성
- API, OTel Collector, Prometheus, Jaeger, Grafana 서비스 연결
- 각 서비스 포트 정리
- 로컬 실행 방법 작성
- 데모 요청 스크립트 또는 curl 명령 정리
- 발표용 시나리오 문서 작성
- 가능하면 Helm chart 기본 구조 작성

#### Docker Compose에 포함할 서비스

```text
sample-llm-api
otel-collector
prometheus
jaeger
grafana
```

#### 실행 명령 예시

```bash
docker compose -f deploy/docker-compose.yml up --build
```

#### 데모 요청 예시

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"OLLY가 뭐야?","feature":"chat","scenario":"normal"}'
```

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"왜 느려?","feature":"chat","scenario":"slow_retrieve"}'
```

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"긴 답변을 해줘","feature":"chat","scenario":"high_token"}'
```

#### 완료 기준

- `docker compose up --build` 한 번으로 전체 서비스가 실행된다.
- `http://localhost:8001/docs`에서 API 문서를 볼 수 있다.
- `http://localhost:16686`에서 Jaeger UI를 볼 수 있다.
- `http://localhost:9090`에서 Prometheus UI를 볼 수 있다.
- `http://localhost:3001`에서 Grafana dashboard를 볼 수 있다.
- README만 보고 다른 팀원이 로컬에서 실행할 수 있다.

#### 다른 팀원과 연결되는 지점

- 1번 팀원의 API Dockerfile을 Compose에 연결한다.
- 2번 팀원의 Collector 설정 파일을 Compose에 연결한다.
- 3번 팀원의 Prometheus/Grafana 설정 파일을 Compose에 연결한다.
- 발표자가 그대로 따라 할 수 있는 데모 순서를 문서화한다.

### 병렬 작업 순서

완전히 순차적으로 할 필요는 없다. 아래 순서로 병렬 진행한다.

```text
1번: API 기본 구조 작성
2번: telemetry.py와 otel-collector.yaml 초안 작성
3번: prometheus.yml, dashboard, alert rule 초안 작성
4번: docker-compose.yml, README, demo_scenario.md 초안 작성

        ↓

1번이 /chat 응답 형식 확정
2번이 trace와 metric 연결
3번이 실제 metric 이름으로 dashboard 수정
4번이 전체 실행 확인

        ↓

전체 팀원이 함께 데모 리허설
```

### 팀원 간 인터페이스 체크리스트

작업 중 아래 항목이 바뀌면 반드시 팀 전체에 공유한다.

- API 포트가 바뀌는 경우
- `/chat` 요청/응답 형식이 바뀌는 경우
- metric 이름이 바뀌는 경우
- trace span 이름이 바뀌는 경우
- Docker Compose 서비스 이름이 바뀌는 경우
- Grafana dashboard panel 이름이 바뀌는 경우

### 통합 테스트 체크리스트

최종 통합 때는 아래 순서대로 확인한다.

1. `docker compose -f deploy/docker-compose.yml up --build` 실행
2. `/chat` normal 요청 5회 실행
3. `/chat` slow_retrieve 요청 3회 실행
4. `/chat` high_token 요청 3회 실행
5. Grafana에서 요청 수, 토큰 수, 비용 증가 확인
6. Jaeger에서 느린 trace 확인
7. Prometheus에서 alert rule 로드 확인
8. README 실행 방법대로 다른 팀원이 재현

## 9. 발표 데모 시나리오

발표에서는 아래 흐름으로 보여주면 된다.

1. `/chat` API에 질문을 여러 번 보낸다.
2. 일부 요청은 정상 응답으로 처리한다.
3. 일부 요청은 일부러 느리게 만든다.
4. 일부 요청은 토큰을 많이 쓰게 만든다.
5. Grafana에서 비용, 토큰, 응답 시간 그래프를 확인한다.
6. Jaeger에서 느린 요청 하나를 클릭한다.
7. 병목이 retrieve인지 llm_call인지 확인한다.
8. alert가 발생한 상태를 보여준다.

발표 설명 예시:

> 사용자가 보기에는 그냥 응답이 느린 상황입니다. 하지만 OLLY를 보면 전체 요청 중 retrieve 단계에서 시간이 많이 걸렸고, 특정 기능에서 토큰 사용량이 급증했다는 것을 확인할 수 있습니다. 그래서 운영자는 비용 문제와 성능 문제의 원인을 빠르게 찾을 수 있습니다.

## 10. 최종 산출물

MVP 완료 시점에 있어야 하는 결과물:

- 실행 가능한 샘플 LLM API
- OpenTelemetry 계측 코드
- Prometheus 설정
- Jaeger 연동
- Grafana 대시보드
- Alert rule
- Docker Compose 실행 환경
- README
- 데모 시나리오 문서
- 발표용 구현 설명

## 11. 핵심 정리

OLLY는 LLM 자체를 더 똑똑하게 만드는 프로젝트가 아니다.

OLLY는 LLM 서비스를 운영할 때 필요한 정보를 보여주는 프로젝트이다.

핵심은 다음 3가지다.

1. 비용이 얼마나 나왔는가?
2. 응답이 얼마나 느렸는가?
3. 어디에서 문제가 생겼는가?

이번 MVP는 이 3가지를 실제 화면으로 보여주는 것을 목표로 한다.
