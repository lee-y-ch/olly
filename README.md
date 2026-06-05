# OLLY — LLM 서비스 운영 관측성 플랫폼

> LLM/RAG 챗봇 서비스의 **비용, 토큰, 지연, 병목, 실패, 알림**을 하나의 요청 단위로 추적하는 CNCF 네이티브 관측성 MVP.

단국대학교 오픈소스SW분석(클라우드) 5조 — 이용찬, 박주희, 최호준, 조하은 / 담당교수: 남재현 교수님

---

## 1. 왜 만들었나

LLM 기반 서비스는 일반 웹 API와 다르게 HTTP 200 응답만으로는 운영 품질을 판단할 수 없다. 같은 `/chat` 요청이라도:

- 프롬프트 길이, 검색 문맥, 모델 실행 시간, 출력 토큰 수에 따라 latency와 비용이 크게 달라지고
- 장애가 발생해도 검색 단계 문제인지, 모델 호출 문제인지 즉시 구분이 어려우며
- 운영자는 비용 급증·토큰 폭증·지연 급증의 원인을 별도로 추적해야 한다

OLLY는 이 문제를 **기존 챗봇 서비스를 대체하지 않고**, `/chat` API에 관측성 계층을 부착하는 방식으로 해결한다.

---

## 2. 핵심 가치

| 축 | 무엇을 보는가 |
| --- | --- |
| 비용 | 요청마다 token cost + local infra cost 분리 기록 |
| 토큰 | feature/scenario별 input/output 토큰 추세 |
| 지연 | 요청 전체 latency + retrieve/llm_call/postprocess 단계별 duration |
| 병목 | p95 기준 어느 단계가 가장 길었는지 자동 식별 |
| 실패 | 성공/실패 요청 모두 동일한 trace 구조로 보존 |
| 알림 | 임계값 초과 시 Discord webhook + SLM 한 줄 요약 |

모든 데이터는 **하나의 `request_id` / `trace_id`로 묶여** 대시보드, Jaeger, Prometheus 어디서 봐도 동일한 요청을 가리킨다.

---

## 3. 시스템 아키텍처

```
사용자 (Chat UI)
   │
   ▼
FastAPI /chat
   ├── retrieve span
   ├── llm_call span (Ollama gemma3:1b)
   └── postprocess span
   │
   ├──── OpenTelemetry SDK ──── OTel Collector ──┬──► Prometheus  (metrics + alert rules)
   │                                              └──► Jaeger      (분산 trace + 단계별 span)
   │
   └──── 응답 (request_id, trace_id, tokens, cost, latency, status)

운영자 (Dashboard)
   ├── 운영자 대시보드   →  Prometheus / Jaeger 조회
   ├── 분석 챗봇         →  Prometheus metric을 자연어로 질의
   ├── 알림 관리         →  AlertEvaluator → Discord webhook + SLM 요약
   └── Grafana 패널      →  iframe embed (실시간 시계열)
```

3개의 독립적 파이프라인(요청 처리 / 관측성 데이터 / 운영 분석)으로 분리되어 모니터링 백엔드가 바뀌어도 메인 서비스 로직에 영향이 없다.

---

## 4. CNCF 프로젝트 활용

| CNCF 도구 | 역할 | 구체적 사용 |
| --- | --- | --- |
| **Kubernetes** | kind 기반 로컬 클러스터 실행 | Deployment + Service + PVC + Job(모델 pull) + ConfigMap + NodePort |
| **OpenTelemetry** | 애플리케이션 계측 표준 | FastAPI 자동 계측 + retrieve/llm_call/postprocess 수동 span |
| **Prometheus** | metric 저장 + PromQL + alert rule | 요청 수, 토큰, 비용, latency, error, stage duration |
| **Jaeger** | 분산 trace 시각화 | POST /chat trace에서 단계별 병목 워터폴 확인 |

Grafana는 시계열 시각화를 위해 함께 연동했고, 운영자 대시보드에 패널 4개(p95 latency / token usage / cost breakdown / bottleneck by stage)를 iframe으로 임베드한다.

특정 벤더 전용 기능에 의존하지 않으므로 **사내 보안 정책 준수**, **벤더 lock-in 없음**, **K8s 환경 친화적**이라는 실무 이점을 갖는다.

---

## 5. 빠른 시작

### 사전 준비

- Docker Desktop
- (선택) kind, kubectl — Kubernetes 환경에서 돌릴 때

### Option A. Docker Compose (가장 빠름)

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

첫 실행 시 `gemma3:1b` (약 815MB) 다운로드로 5~10분 소요. 이후 실행은 즉시.

| 화면 | 주소 |
| --- | --- |
| 사용자 챗봇 UI | http://localhost:8001/chat-ui |
| 운영자 대시보드 | http://localhost:8001/dashboard |
| API 문서 | http://localhost:8001/docs |
| Jaeger | http://localhost:16686 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3001 (admin/admin) |

정리:
```bash
docker compose -f deploy/docker-compose.yml down
```

### Option B. Kubernetes (kind)

CNCF 네이티브 배포 검증용:

```bash
cd k8s
make up      # kind 클러스터 생성 → 이미지 빌드 + load → ConfigMap → manifest apply
make status  # Pod 상태 확인
make down    # 클러스터 삭제
```

NodePort로 호스트의 동일 포트(8001 / 9090 / 16686 / 3001)에 매핑되어 접속 주소는 Docker Compose와 동일.

---

## 6. API

### `POST /chat`

```json
{
  "question": "OpenAI가 느린 것인가, 우리 RAG가 느린 것인가?",
  "feature": "rag_qa",
  "scenario": "slow_retrieve"
}
```

응답:
```json
{
  "request_id": "req_6b416a56",
  "trace_id": "581bf5f8a556b3843d3dfa910fc7e02b",
  "answer": "...",
  "model": "gemma3:1b",
  "feature": "rag_qa",
  "llm_backend": "ollama",
  "input_tokens": 122,
  "output_tokens": 8,
  "cost_usd": 0.000044,
  "token_cost_usd": 0.0,
  "infra_cost_usd": 0.000044,
  "compute_seconds": 3.2,
  "compute_resource": "cpu",
  "latency_ms": 3435,
  "status": "success"
}
```

### 시나리오

데모/검증 재현성을 위해 5개 시나리오를 제공:

| scenario | 의미 | 발표에서 보이는 것 |
| --- | --- | --- |
| `normal` | 정상 요청 | KPI baseline |
| `slow_retrieve` | retrieve 단계 지연 | RAG 검색 병목 |
| `slow_llm` | llm_call 단계 지연 | 모델 생성 병목 |
| `high_token` | 출력 토큰 폭증 | 토큰/비용 증가 |
| `error` | 강제 실패 | status=error 보존 검증 |

### 사용자 정의 알림

운영자는 `/dashboard`에서 직접 알림 규칙을 만들 수 있다:

- 지표 6종 (요청 수/분, 토큰/분, p95 latency, 에러율, 시간당 비용, retrieve p95)
- 비교 조건(`>`, `<`), 임계값, 평가 윈도우(`1m/5m/15m`), 쿨다운
- 발화 시 Discord webhook으로 push + `gemma3:1b`가 한 줄 요약 첨부

```bash
curl -X POST http://localhost:8001/api/alerts/rules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "토큰 사용량 급증",
    "metric": "token_rate_per_min",
    "comparator": "gt",
    "threshold": 200,
    "window": "5m",
    "cooldown_seconds": 300,
    "webhook_url": "https://discord.com/api/webhooks/..."
  }'
```

---

## 7. 검증 결과

5개 시나리오 × 각 10회 = **총 50회 요청**을 반복하여 end-to-end 관측 파이프라인을 검증.

| 시나리오 | 관측 결과 |
| --- | --- |
| `slow_retrieve` | retrieve span 지연이 정상 대비 크게 증가, 대시보드 단계별 워터폴에서 즉시 식별 |
| `slow_llm` | llm_call 구간이 병목으로 자동 분류 |
| `high_token` | 평균 457 토큰, p50 약 34.58초 — Cost/Token KPI 증가 즉시 반영 |
| `error` | status=error로 보존되어 Recent Requests / Prometheus / Jaeger에서 동일하게 추적 |

자세한 PromQL, metric 정의, 단계별 분석은 최종 보고서를 참조.

---

## 8. 폴더 구조

```
olly/
├── apps/sample-llm-api/        # FastAPI 샘플 LLM 서비스 (관측 대상)
│   ├── app/
│   │   ├── main.py             # /chat 엔드포인트 + AlertEvaluator 부착
│   │   ├── dashboard.py        # /dashboard, /chat-ui, /api/dashboard/*, /api/alerts/*
│   │   ├── alerts.py           # 백그라운드 알림 평가 + Discord dispatcher
│   │   ├── alert_storage.py    # 알림 규칙 JSON 영속화
│   │   ├── analysis*.py        # 분석 챗봇 응답 빌더
│   │   ├── ollama_llm.py       # gemma3:1b 호출
│   │   ├── telemetry.py        # OpenTelemetry 설정
│   │   ├── metrics.py          # Prometheus metric 정의
│   │   └── static/             # chat_ui.html, dashboard.html
│   ├── Dockerfile
│   └── requirements.txt
│
├── observability/              # CNCF 도구 설정
│   ├── otel-collector.yaml
│   ├── prometheus.yml
│   ├── alert-rules.yml
│   └── grafana/                # dashboards + provisioning
│
├── deploy/docker-compose.yml   # 로컬 Compose 배포
│
├── k8s/                        # Kubernetes (kind) 배포
│   ├── kind-cluster.yaml
│   ├── Makefile                # make up / down / status / logs
│   ├── 00-namespace.yaml
│   ├── 01-storage.yaml         # PVC (모델 + 알림 규칙)
│   ├── 10-ollama.yaml          # Ollama Deployment + Service + 모델 pull Job
│   ├── 20-otel-collector.yaml
│   ├── 30-jaeger.yaml
│   ├── 40-prometheus.yaml
│   ├── 50-grafana.yaml
│   └── 60-sample-llm-api.yaml
│
├── tools/                      # 보고서/다이어그램 생성 스크립트
│
├── presentation/               # 발표 자료
│   ├── OLLY_주제발표.pdf
│   ├── OLLY_최종발표.pdf
│   └── OLLY_데모영상.mp4
│
└── README.md
```

---

## 9. 발표 자료 / 데모

| 자료 | 경로 |
| --- | --- |
| 데모 영상 | [`presentation/OLLY_데모영상.mp4`](presentation/OLLY_데모영상.mp4) |
| 최종 발표 슬라이드 | [`presentation/OLLY_최종발표.pdf`](presentation/OLLY_최종발표.pdf) |
| 주제 발표 슬라이드 | [`presentation/OLLY_주제발표.pdf`](presentation/OLLY_주제발표.pdf) |
| 최종 보고서 | 별도 제출 |

---

## 10. 한계와 향후 확장

**현재 MVP 범위에서 의도적으로 제외한 항목:**

- 외부 LLM API 과금(OpenAI/Claude/Gemini) — 반복 검증 비용 제약으로 로컬 SLM에 한정
- 대규모 트래픽 / 장기 metric 보관 — 샘플링 + 보존 정책 별도 필요
- 인증/RBAC, Ingress/TLS, Secret 관리 — 운영 클러스터 적용 시 필요
- 멀티테넌시, 사용자/조직별 비용 분리
- Semantic Monitoring (응답 품질/할루시네이션 평가)

**확장 방향:**

1. 외부 LLM 백엔드 어댑터 추가 — 토큰 가격표 기반 정확 비용 계산
2. 장기 저장소(Thanos / Cortex / VictoriaMetrics) 연동
3. 인증 + 권한(OIDC + RBAC)
4. 멀티 모델/멀티 테넌시 비용 분리
5. Semantic Monitoring 통합

---

## 11. 팀

| 학번 | 이름 |
| --- | --- |
| 32213336 | 이용찬 |
| 32221902 | 박주희 |
| 32215116 | 최호준 |
| 32234364 | 조하은 |

단국대학교 SW융합학부 — 오픈소스SW분석(클라우드) / 담당교수: 남재현 교수님

---

## 12. 라이선스

본 저장소는 학교 과제로 작성된 결과물이며, 별도 라이선스 표기가 없는 한 **MIT 라이선스**를 따른다. 사용된 CNCF 프로젝트(Kubernetes, OpenTelemetry, Prometheus, Jaeger, Grafana)와 Ollama, gemma3는 각자의 라이선스를 따른다.
