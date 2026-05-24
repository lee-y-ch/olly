# OLLY k8s (kind) 배포용 Makefile
#
# 한 번에 시작: make up
# 한 번에 정리: make down

CLUSTER_NAME ?= olly
NAMESPACE ?= olly
IMAGE ?= olly-sample-llm-api:dev
ROOT := $(shell cd .. && pwd)

.PHONY: cluster image load configmaps apply up down status logs reload-api

cluster:
	@if ! kind get clusters | grep -q '^$(CLUSTER_NAME)$$'; then \
		kind create cluster --config kind-cluster.yaml; \
	else \
		echo "kind cluster '$(CLUSTER_NAME)' already exists"; \
	fi

image:
	docker build -t $(IMAGE) $(ROOT)/apps/sample-llm-api

load: image
	kind load docker-image $(IMAGE) --name $(CLUSTER_NAME)

configmaps:
	kubectl apply -f 00-namespace.yaml
	kubectl create configmap prometheus-config -n $(NAMESPACE) \
		--from-file=prometheus.yml=$(ROOT)/observability/prometheus.yml \
		--from-file=alert-rules.yml=$(ROOT)/observability/alert-rules.yml \
		--dry-run=client -o yaml | kubectl apply -f -
	kubectl create configmap otel-collector-config -n $(NAMESPACE) \
		--from-file=otel-collector.yaml=$(ROOT)/observability/otel-collector.yaml \
		--dry-run=client -o yaml | kubectl apply -f -
	kubectl create configmap grafana-datasources -n $(NAMESPACE) \
		--from-file=datasource.yml=$(ROOT)/observability/grafana/provisioning/datasources/datasource.yml \
		--dry-run=client -o yaml | kubectl apply -f -
	kubectl create configmap grafana-dashboards-provisioning -n $(NAMESPACE) \
		--from-file=dashboard.yml=$(ROOT)/observability/grafana/provisioning/dashboards/dashboard.yml \
		--dry-run=client -o yaml | kubectl apply -f -
	kubectl create configmap grafana-dashboards-json -n $(NAMESPACE) \
		--from-file=$(ROOT)/observability/grafana/dashboards \
		--dry-run=client -o yaml | kubectl apply -f -

apply:
	kubectl apply -f 01-storage.yaml
	kubectl apply -f 10-ollama.yaml
	kubectl apply -f 20-otel-collector.yaml
	kubectl apply -f 30-jaeger.yaml
	kubectl apply -f 40-prometheus.yaml
	kubectl apply -f 50-grafana.yaml
	kubectl apply -f 60-sample-llm-api.yaml

up: cluster load configmaps apply
	@echo ""
	@echo "OLLY 클러스터가 올라가고 있습니다."
	@echo "접속 주소:"
	@echo "  Chat UI:     http://localhost:8001/chat-ui"
	@echo "  Dashboard:   http://localhost:8001/dashboard"
	@echo "  API Docs:    http://localhost:8001/docs"
	@echo "  Jaeger:      http://localhost:16686"
	@echo "  Prometheus:  http://localhost:9090"
	@echo "  Grafana:     http://localhost:3001 (admin/admin)"
	@echo ""
	@echo "Pod 상태 확인:  make status"

down:
	kind delete cluster --name $(CLUSTER_NAME)

status:
	kubectl -n $(NAMESPACE) get pods,svc,pvc,job

logs:
	kubectl -n $(NAMESPACE) logs -l app=sample-llm-api --tail=80

reload-api: load
	kubectl -n $(NAMESPACE) rollout restart deployment/sample-llm-api
