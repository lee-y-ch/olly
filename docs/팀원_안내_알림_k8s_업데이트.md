# 팀원 안내 — 알림 / k8s 기능 추가

브랜치 `feature/alerts-and-k8s`에 두 가지 큰 기능이 추가됐다. 둘 다 기존 MVP는 그대로 두고 그 위에 얹은 것이므로 기존 데모 흐름에는 영향이 없다.

## 1. 무엇이 추가됐는가

### 1.1 사용자 정의 알림 + Discord 푸시

운영자가 `/dashboard` 화면에서 직접 알림 규칙을 만들 수 있다.

- 지표 6종: 요청 수/분, 토큰/분, p95 응답시간, 에러율, 시간당 비용, retrieve p95
- 조건: `>`, `<`
- 평가 윈도우: `1m`, `5m`, `15m`
- 쿨다운 설정
- 발화 시 Discord webhook으로 푸시
- 메시지에는 `gemma3:1b`가 생성한 한 줄 요약이 함께 첨부됨

자세한 설명: `docs/alerts_setup.md`

### 1.2 쿠버네티스(kind) 배포

전체 시스템을 로컬 kind 클러스터에 배포할 수 있다.

- `k8s/` 폴더에 매니페스트 + Makefile
- `make up` 한 줄로 클러스터 생성 + 이미지 빌드 + 적용까지 끝남
- CNCF 프로젝트(Kubernetes, Prometheus, OpenTelemetry, Jaeger)를 그대로 사용

자세한 설명: `docs/kind_setup.md`

## 2. 빠르게 해보기 (5분, Docker Compose 기준)

가장 익숙한 docker compose로 빠르게 새 기능을 확인하는 방법이다. k8s 환경은 `docs/kind_setup.md` 참고.

### 2.1 최신 코드 받고 실행

```bash
git fetch origin
git checkout feature/alerts-and-k8s
docker compose -f deploy/docker-compose.yml up -d --build
```

첫 빌드는 몇 분 걸린다.

### 2.2 Discord webhook 준비

선택지 1 (실제 Discord 채널 사용):

1. Discord 본인 서버 → 알림 받을 채널 → 채널 설정 → 연동 → 웹후크 → 새 웹후크
2. URL 복사

선택지 2 (Discord 없이 webhook 동작만 확인):

1. https://webhook.site 접속
2. 화면 위 "Your unique URL" 복사

### 2.3 규칙 만들기

브라우저로 http://localhost:8001/dashboard 접속 → 화면 아래 `Custom Alert Rule` 카드에 입력:

| 필드 | 값 |
| --- | --- |
| 이름 | 테스트 알림 |
| 지표 | 요청 수 / 분 (req/min) |
| 조건 | 초과 (>) |
| 임계값 | 0.5 |
| 윈도우 | 1m |
| 쿨다운(초) | 60 |
| Webhook URL | (2.2에서 복사한 URL) |

`규칙 추가` 클릭 → 우측 `Custom Rules`에 표시되면 OK.

### 2.4 트래픽 만들기

http://localhost:8001/chat-ui 에서 아무 질문이나 3~5번 전송.

### 2.5 알림 확인

30초~1분 기다리면:

- Discord 채널 또는 webhook.site 화면에 알림 도착
- `/dashboard` 우측 하단 `Recent Firings`에 같은 이벤트 기록
- 메시지에 `gemma3:1b`가 만든 한 줄 요약 포함

### 2.6 정리

```bash
docker compose -f deploy/docker-compose.yml down
```

## 3. k8s 환경에서도 해보고 싶다면

추가로 필요한 도구:

```bash
brew install kind
```

실행:

```bash
cd k8s
make up
```

접속 주소는 docker compose와 동일하다 (`make up` 출력에 안내됨). 첫 실행은 `gemma3:1b` 다운로드까지 포함되어 5~10분 걸린다.

정리:

```bash
cd k8s
make down
```

자세한 내용은 `docs/kind_setup.md`.

## 4. 변경된 파일

알림 기능:

```text
apps/sample-llm-api/app/alert_storage.py   (신규)
apps/sample-llm-api/app/alerts.py          (신규)
apps/sample-llm-api/app/dashboard.py       (알림 API 추가)
apps/sample-llm-api/app/main.py            (평가 루프 startup/shutdown)
apps/sample-llm-api/app/static/dashboard.html (알림 UI 섹션 추가)
deploy/docker-compose.yml                  (env, 볼륨 추가)
docs/alerts_setup.md                       (신규)
```

k8s 배포:

```text
k8s/kind-cluster.yaml
k8s/Makefile
k8s/00-namespace.yaml
k8s/01-storage.yaml
k8s/10-ollama.yaml
k8s/20-otel-collector.yaml
k8s/30-jaeger.yaml
k8s/40-prometheus.yaml
k8s/50-grafana.yaml
k8s/60-sample-llm-api.yaml
docs/kind_setup.md                         (신규)
```

## 5. 문제가 생기면

- 알림이 안 옴: 임계값을 낮춰서 다시 확인, `curl http://localhost:8001/api/alerts/history`로 발화 이력 확인
- LLM 요약이 비어 있음: `gemma3:1b`가 타임아웃 안에 응답하지 못한 경우. 알림 자체는 정상 발송됨
- 자세한 디버깅 팁은 `docs/alerts_setup.md` 8장, `docs/kind_setup.md` 9장 참고
