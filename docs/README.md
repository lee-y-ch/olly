# OLLY 문서 안내

이 폴더는 팀원이 OLLY를 이해하고, 실행하고, 병렬 작업하고, 발표할 수 있도록 정리한 문서 모음이다.

## 먼저 볼 문서 순서

| 순서 | 문서 | 목적 |
| --- | --- | --- |
| 1 | `OLLY_쉬운_이해_가이드.md` | OLLY가 무엇인지, 용어와 화면을 쉽게 이해 |
| 2 | `MVP_진행계획.md` | 현재 구현된 MVP 범위와 전체 구조 파악 |
| 3 | `local_gemma3_setup.md` | Docker Compose로 로컬 실행 |
| 4 | `demo_scenario.md` | 발표 시연 순서 확인 |
| 5 | `팀원_병렬작업_가이드.md` | 팀원 4명 분업 기준 확인 |
| 6 | `대시보드_사전검증_결과.md` | metric, trace, alert, 분석 챗봇 검증 근거 확인 |

## 현재 OLLY 핵심 상태

현재 OLLY는 단순 챗봇이 아니라, **대시보드 데이터를 읽고 운영 질문에 답하는 LLM 서비스 관측성 MVP**이다.

구현된 핵심 기능:

- 사용자 챗봇 UI: 질문 전송
- 운영자 대시보드: 비용, 토큰, latency, 최근 요청, trace detail 확인
- 분석 챗봇: Prometheus/Jaeger 데이터를 읽고 질문에 답변
- 로컬 LLM: Ollama `gemma3:1b`
- 비용 계산: API 토큰 과금이 아니라 CPU/GPU 실행 시간 기반 추정
- 관측 수집: OpenTelemetry, Prometheus, Jaeger
- 보조 시각화: Grafana
- 알림: Prometheus alert rule

## 핵심 접속 주소

| 화면 | 주소 | 역할 |
| --- | --- | --- |
| 사용자 챗봇 UI | http://localhost:8001/chat-ui | 사용자가 질문하는 화면 |
| 운영자 대시보드 | http://localhost:8001/dashboard | 운영자가 한 화면에서 상태를 보는 화면 |
| API 문서 | http://localhost:8001/docs | 개발자가 API를 직접 테스트하는 화면 |
| Jaeger | http://localhost:16686 | 요청 하나의 trace 원본 확인 |
| Prometheus | http://localhost:9090 | metric 원본 확인 |
| Grafana | http://localhost:3001 | 보조 시각화 대시보드 |

## 코드 구조 요약

```text
apps/sample-llm-api/app/
  main.py               # /chat 처리, 계측, 응답 반환
  analysis.py           # 관측 질문 답변 orchestrator
  analysis_intents.py   # 질문 의도/기간/request_id/trace_id 파싱
  analysis_metrics.py   # Prometheus 기간 비교 쿼리
  dashboard.py          # /dashboard, /chat-ui, dashboard API
  metrics.py            # Prometheus metric 정의/기록
  telemetry.py          # OpenTelemetry 설정
  ollama_llm.py         # Ollama gemma3:1b 호출
  pricing.py            # 로컬 실행 시간 기반 비용 계산
```

## 팀원이 기억할 한 문장

> OLLY는 LLM 요청을 `request_id`와 `trace_id`로 추적하고, Prometheus/Jaeger 데이터를 읽어 비용, 토큰, 지연, 실패, 알림 원인을 설명하는 운영 대시보드이다.
