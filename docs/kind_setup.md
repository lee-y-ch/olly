# OLLY kind(쿠버네티스) 실행 가이드

이 문서는 로컬 시연용으로 OLLY 전체 시스템을 kind 위에 배포하는 방법을 정리한 가이드이다.

CNCF 프로젝트 활용 측면에서 OLLY는 다음을 사용한다.

- Kubernetes (kind, 로컬 시연용 distribution)
- Prometheus
- OpenTelemetry Collector
- Jaeger
- Helm chart 대신 plain manifest를 사용 (이번 MVP 범위)

## 1. 필요한 도구

| 도구 | 설치 명령 |
| --- | --- |
| Docker Desktop | 공식 사이트 또는 `brew install --cask docker` |
| kubectl | Docker Desktop에 포함 또는 `brew install kubectl` |
| kind | `brew install kind` |
| make | macOS에 기본 포함 |

확인:

```bash
docker --version
kubectl version --client
kind version
```

## 2. 한 번에 실행

```bash
cd k8s
make up
```

`make up`은 아래를 순서대로 실행한다.

1. kind 클러스터 생성 (`kind-cluster.yaml`)
2. `sample-llm-api` 도커 이미지 빌드 후 클러스터로 load
3. 설정 파일들을 ConfigMap으로 등록
4. PVC, Deployment, Service 적용

첫 실행은 `gemma3:1b` 모델을 다운로드하므로 5~10분 걸릴 수 있다.

## 3. 상태 확인

```bash
make status
```

또는:

```bash
kubectl -n olly get pods,svc,pvc,job
```

모든 Pod이 `Running`이고 `ollama-pull-gemma` Job이 `Completed`가 되면 준비 완료.

## 4. 접속 주소

`kind-cluster.yaml`의 `extraPortMappings`로 호스트 포트를 NodePort 서비스에 연결한다.

| 화면 | 주소 |
| --- | --- |
| 사용자 챗봇 UI | http://localhost:8001/chat-ui |
| 운영자 대시보드 | http://localhost:8001/dashboard |
| API 문서 | http://localhost:8001/docs |
| Jaeger | http://localhost:16686 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3001 (admin/admin) |

## 5. 로그 확인

```bash
make logs
```

또는 특정 컴포넌트:

```bash
kubectl -n olly logs -l app=ollama --tail=50
kubectl -n olly logs -l app=prometheus --tail=50
```

## 6. 코드 변경 후 API 재배포

`apps/sample-llm-api/` 아래 코드를 수정했다면:

```bash
cd k8s
make reload-api
```

이 명령은 이미지 재빌드 → kind에 다시 load → Deployment rollout restart를 수행한다.

## 7. 전체 정리

```bash
cd k8s
make down
```

`kind delete cluster --name olly`와 동등하다. PVC도 같이 삭제된다.

## 8. 매니페스트 구조

```text
k8s/
  kind-cluster.yaml          kind 클러스터 + 포트 매핑
  Makefile                   원클릭 명령 모음
  00-namespace.yaml          olly Namespace
  01-storage.yaml            PVC (ollama 모델, 알림 규칙)
  10-ollama.yaml             ollama Deployment + Service + 모델 pull Job
  20-otel-collector.yaml     OTel Collector
  30-jaeger.yaml             Jaeger + NodePort
  40-prometheus.yaml         Prometheus + NodePort
  50-grafana.yaml            Grafana + NodePort
  60-sample-llm-api.yaml     FastAPI 앱 + NodePort
```

Prometheus, OTel Collector, Grafana의 설정 파일은 `observability/` 폴더의 기존 파일을 ConfigMap으로 마운트하므로, 설정 변경 시 `make configmaps` 후 해당 Pod를 재시작한다.

## 9. 자주 나는 문제

### kind 클러스터가 만들어지지 않는다

- Docker Desktop이 실행 중인지 확인한다.
- 기존 `olly` 클러스터가 남아 있다면 `kind delete cluster --name olly`로 정리한다.

### `sample-llm-api` Pod가 `ImagePullBackOff`이다

- `make image` 후 `make load`를 다시 실행했는지 확인한다.
- `imagePullPolicy: IfNotPresent`이므로 kind에 load된 이미지를 우선 사용한다.

### `/chat`이 500을 낸다

- `kubectl -n olly logs -l app=ollama --tail=50`으로 ollama가 모델을 로드했는지 확인한다.
- 모델 다운로드 중이면 잠시 기다린다.

### 포트 충돌

- 호스트의 8001, 9090, 16686, 3001 포트가 이미 사용 중이면 `kind-cluster.yaml`의 `hostPort`를 수정한다.
