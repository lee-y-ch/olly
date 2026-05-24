# OLLY 사용자 정의 알림 가이드

이 문서는 운영자가 직접 알림 규칙을 만들고 Discord 채널로 푸시 알림을 받는 방법을 정리한 가이드이다.

## 1. 기능 요약

운영자는 `/dashboard`의 `Custom Alert Rule` 영역에서 다음을 직접 설정할 수 있다.

- 어떤 지표를 감시할지 (요청 수, 토큰, p95, 에러율, 비용, retrieve p95 중 선택)
- 비교 조건 (`>` 또는 `<`)
- 임계값
- 평가 윈도우 (`1m`, `5m`, `15m`)
- 쿨다운 (같은 규칙이 너무 자주 발화하지 않도록)
- Discord webhook URL

조건을 만족하면 Discord 채널에 알림이 전송되며, 함께 `gemma3:1b`가 생성한 한 줄 요약이 첨부된다.

## 2. 평가 흐름

```text
규칙 생성 (UI 또는 POST /api/alerts/rules)
  ↓
저장 (alert_rules.json, 영속 볼륨)
  ↓
백그라운드 평가 루프 (기본 30초 간격)
  ↓
Prometheus query 실행
  ↓
임계값 충족 + cooldown 만료 시
  ↓
gemma3:1b가 1줄 요약 생성 (옵션)
  ↓
Discord webhook POST
  ↓
last_fired_at 갱신, history 기록
```

## 3. 사용 가능한 지표

| metric key | 의미 | 단위 |
| --- | --- | --- |
| `request_rate_per_min` | 분당 요청 수 | req/min |
| `token_rate_per_min` | 분당 토큰 사용량 | tokens/min |
| `p95_latency_seconds` | 응답시간 p95 | seconds |
| `error_rate_percent` | 에러율 | percent |
| `estimated_cost_rate_per_hour` | 시간당 추정 비용 | USD/hour |
| `retrieve_p95_seconds` | retrieve 단계 p95 | seconds |

## 4. 환경 변수

| 이름 | 기본값 | 설명 |
| --- | --- | --- |
| `ALERT_RULES_PATH` | `/var/lib/olly/alert_rules.json` | 규칙 저장 경로 |
| `ALERT_EVAL_INTERVAL_SECONDS` | `30` | 평가 주기 |
| `ALERT_LLM_SUMMARY` | `true` | LLM 요약 첨부 여부 |
| `ALERT_LLM_SUMMARY_TIMEOUT` | `8` | LLM 호출 타임아웃 (초) |

## 5. Discord Webhook 만들기

1. Discord 채널 → 채널 설정 → 연동 → 웹후크
2. 새 웹후크 → URL 복사
3. 그 URL을 `/dashboard` 폼의 Discord Webhook URL에 붙여 넣기

## 6. 예시: 토큰 사용량 급증 알림

| 항목 | 값 |
| --- | --- |
| 이름 | 토큰 사용량 급증 |
| 지표 | `token_rate_per_min` |
| 조건 | `>` |
| 임계값 | `200` |
| 윈도우 | `5m` |
| 쿨다운(초) | `300` |
| Webhook URL | (Discord에서 복사한 URL) |

이 규칙은 최근 5분간 분당 토큰 사용량 평균이 200을 넘으면 Discord에 알림을 보낸다. 5분 동안 같은 규칙은 다시 발화하지 않는다.

## 7. API 사용 예시 (curl)

규칙 생성:

```bash
curl -X POST http://localhost:8001/api/alerts/rules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "p95 응답시간 경고",
    "metric": "p95_latency_seconds",
    "comparator": "gt",
    "threshold": 3,
    "window": "5m",
    "cooldown_seconds": 300,
    "webhook_url": "https://discord.com/api/webhooks/..."
  }'
```

규칙 목록:

```bash
curl http://localhost:8001/api/alerts/rules
```

규칙 삭제:

```bash
curl -X DELETE http://localhost:8001/api/alerts/rules/{rule_id}
```

규칙 on/off:

```bash
curl -X POST 'http://localhost:8001/api/alerts/rules/{rule_id}/toggle?enabled=false'
```

최근 발화 이력:

```bash
curl http://localhost:8001/api/alerts/history
```

## 8. 자주 묻는 것

### 알림이 안 옵니다

- Discord webhook URL을 다시 확인한다.
- 평가 주기는 기본 30초이다. 임계값을 충족했어도 다음 평가 주기에 발화한다.
- `cooldown_seconds` 안에는 다시 발화하지 않는다.
- Prometheus가 해당 지표를 아직 수집하지 못했을 수 있다. `/chat` 요청을 몇 번 발생시켜 데이터를 만든다.

### LLM 요약이 비어 있습니다

- `ALERT_LLM_SUMMARY=false`로 비활성화된 경우 비어 있다.
- `gemma3:1b`가 타임아웃 안에 응답하지 못하면 비어 있다 (요약 실패해도 알림 자체는 발송됨).

### 규칙을 코드로 미리 정의하고 싶습니다

`ALERT_RULES_PATH`가 가리키는 JSON 파일에 직접 규칙을 적어두고 컨테이너를 시작하면 된다.
