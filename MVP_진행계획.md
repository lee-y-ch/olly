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

## 8. 팀원 역할 분담 예시

### 1번: 샘플 API / LLM 로직

담당 내용:

- FastAPI 서버 구현
- `/chat` API 구현
- Mock LLM 응답 구현
- 토큰 수 및 비용 계산 로직 구현

### 2번: OpenTelemetry / Collector

담당 내용:

- API에 OpenTelemetry 계측 추가
- 단계별 trace 생성
- OTel Collector 설정
- Prometheus, Jaeger로 데이터 전달

### 3번: Grafana / Prometheus / Alert

담당 내용:

- Prometheus 설정
- metric 쿼리 작성
- Grafana dashboard 구성
- alert rule 작성

### 4번: Docker / 문서 / 발표 데모

담당 내용:

- Docker Compose 구성
- 실행 방법 정리
- 데모 시나리오 작성
- 발표 자료에 구현 흐름 반영

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
