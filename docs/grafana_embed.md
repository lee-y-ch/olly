# OLLY 대시보드 Grafana embed 가이드

운영자 대시보드(`/dashboard`)는 Grafana가 Prometheus를 읽어 그린 그래프를 그대로 임베드해서 보여준다.

## 1. 임베드되는 패널

| 패널 | Grafana panelId | 의미 |
| --- | --- | --- |
| p95 Latency | 4 | 응답시간 분포의 상위 5% |
| Token Usage Trend | 6 | 토큰 사용 추이 |
| Cost Breakdown | 11 | 토큰 vs 인프라 비용 |
| Bottleneck by Stage p95 | 13 | retrieve / llm_call / postprocess 중 어느 단계가 느린지 |

Grafana 대시보드 UID는 `olly-mvp`이며, `observability/grafana/dashboards/olly-mvp-dashboard.json`이 원본이다.

## 2. URL 형식

```text
http://localhost:3001/d-solo/olly-mvp/olly-mvp-dashboard
  ?orgId=1
  &panelId={id}
  &theme=dark
  &kiosk=tv
  &from=now-1h
  &to=now
  &refresh=30s
```

`d-solo`는 Grafana가 단일 패널만 렌더링하도록 하는 경로이다. `kiosk=tv`로 패널 외 UI를 숨긴다.

`/dashboard` 상단의 윈도우 선택(`15m / 1h / 6h / 24h`)이 바뀌면 iframe `src`의 `from`도 자동으로 갱신된다.

## 3. 동작을 위한 Grafana 설정

`deploy/docker-compose.yml`과 `k8s/50-grafana.yaml` 모두 다음 환경 변수가 설정되어 있다.

| 환경 변수 | 값 | 이유 |
| --- | --- | --- |
| `GF_AUTH_ANONYMOUS_ENABLED` | `true` | 로그인 없이 iframe 로드 |
| `GF_AUTH_ANONYMOUS_ORG_ROLE` | `Viewer` | 익명 사용자에게 조회 권한만 부여 |
| `GF_SECURITY_ALLOW_EMBEDDING` | `true` | X-Frame-Options 제거 |
| `GF_SECURITY_COOKIE_SAMESITE` | `none` | 다른 출처 iframe에서 쿠키 공유 |
| `GF_SECURITY_COOKIE_SECURE` | `false` | 로컬 http 환경에서 쿠키 사용 |

이 설정은 **로컬 데모 전용**이다. 실제 운영 환경에서는 익명 접근을 끄고 SSO/리버스 프록시로 인증을 처리해야 한다.

## 4. 패널 추가/교체

1. Grafana(`localhost:3001`)에서 대시보드를 직접 편집해 새 패널을 만들고 panelId를 확인한다.
2. `observability/grafana/dashboards/olly-mvp-dashboard.json`을 새 정의로 갱신한다(혹은 export → 덮어쓰기).
3. `apps/sample-llm-api/app/static/dashboard.html`의 `GRAFANA_PANELS` 객체에 새 elementId와 panelId를 추가하고, 그 자리에 `<iframe>` 한 개를 더 둔다.

## 5. 자주 나는 문제

### iframe이 비어 있고 "Refused to display"가 콘솔에 뜬다

- Grafana 컨테이너가 새 env로 재기동됐는지 확인 (`docker compose up -d --build` 또는 `kubectl rollout restart deploy/grafana -n olly`).

### iframe이 로그인 화면을 보여준다

- `GF_AUTH_ANONYMOUS_ENABLED=true`가 적용됐는지 확인.
- 익명 사용자의 default org가 Main Org인지 확인 (Grafana 기본값이라 보통 문제 없음).

### 그래프가 비어 있다

- `/chat-ui`에서 요청을 몇 번 보내 데이터를 만든다.
- 윈도우를 더 넓혀(예: `6h`) 다시 본다.
