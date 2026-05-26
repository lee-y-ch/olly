# OLLY 문서 안내

팀원들은 아래 순서로 문서를 보면 된다.

## 1. 처음 이해할 때

```text
OLLY_쉬운_이해_가이드.md
```

OLLY가 무엇인지, 각 용어가 무슨 뜻인지, 화면을 어떻게 봐야 하는지 쉽게 정리한 문서이다.

## 2. 지금 MVP가 무엇인지 볼 때

```text
MVP_진행계획.md
```

현재 MVP의 목표, 구조, 구현 범위, 완료 기준을 정리한 문서이다.

## 3. 직접 실행할 때

```text
local_gemma3_setup.md
```

Docker Compose로 로컬에서 `gemma3:1b` 기반 OLLY를 실행하는 방법을 정리한 문서이다.

## 4. 발표 리허설을 할 때

```text
demo_scenario.md
```

`/chat-ui`에서 질문을 보내고 `/dashboard`에서 병목을 확인하는 발표 순서를 정리한 문서이다.

## 5. 팀원 4명이 나눠서 작업할 때

```text
팀원_병렬작업_가이드.md
```

API, 관측성, 프론트엔드/대시보드, 문서/발표 담당으로 나누어 병렬 작업하는 방법을 정리한 문서이다.

## 6. 대시보드 검증 근거를 볼 때

```text
대시보드_사전검증_결과.md
```

metric, trace, 비용 계산, alert가 대시보드 요구사항을 만족하는지 검증한 결과를 정리한 문서이다.

## 7. 사용자 정의 알림(Discord 푸시)을 설정할 때

```text
alerts_setup.md
```

운영자가 직접 알림 규칙을 만들고 Discord webhook으로 푸시 알림을 받는 방법을 정리한 문서이다. `gemma3:1b`가 알림 메시지에 한 줄 요약을 함께 첨부한다.

## 8. 쿠버네티스(kind)로 실행할 때

```text
kind_setup.md
```

로컬 시연용으로 OLLY 전체 시스템을 kind 위에 배포하는 방법을 정리한 문서이다. CNCF 프로젝트(Kubernetes, Prometheus, OpenTelemetry, Jaeger)를 사용한다.

## 핵심 접속 주소

| 화면 | 주소 |
| --- | --- |
| 사용자 챗봇 UI | http://localhost:8001/chat-ui |
| 운영자 대시보드 | http://localhost:8001/dashboard |
| API 문서 | http://localhost:8001/docs |
| Jaeger | http://localhost:16686 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3001 |
