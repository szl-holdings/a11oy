# szl-build-env — local 5-organ + Istio ambient + OTel stack on kind
# Doctrine v11 LOCKED 749/14/163 @ kernel c7c0ba17. NOT Iron Bank. SLSA L1 honest + L2 attested.
SHELL := /bin/bash
.DEFAULT_GOAL := help

# ---- pins (single source of truth) ------------------------------------------
ISTIO_VERSION   ?= 1.25.0
OTEL_VERSION    ?= 0.135.0
KIND_CLUSTER    ?= szl-build-env
BUNDLE          ?= oci://ghcr.io/szl-holdings/szl-uds-bundle:uds-v0.2.0
ORGAN_TAG       ?= uds-v0.2.0
NAMESPACE       ?= szl
BIN             := $(CURDIR)/bin
ISTIOCTL        := $(BIN)/istioctl
export PATH     := $(BIN):$(PATH)

ORGANS := a11oy sentra amaru killinchu rosie

.PHONY: help up verify trace down demo istioctl cluster mesh otel organs clean status cosign-key

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

istioctl: ## Download pinned istioctl into ./bin
	@mkdir -p $(BIN)
	@if [ ! -x "$(ISTIOCTL)" ]; then \
	  echo ">> downloading istioctl $(ISTIO_VERSION)"; \
	  curl -sSL https://istio.io/downloadIstio | ISTIO_VERSION=$(ISTIO_VERSION) sh - ; \
	  cp istio-$(ISTIO_VERSION)/bin/istioctl $(ISTIOCTL); \
	  chmod +x $(ISTIOCTL); \
	fi
	@$(ISTIOCTL) version --remote=false

cluster: ## Create the single-node kind cluster
	@if ! kind get clusters 2>/dev/null | grep -qx "$(KIND_CLUSTER)"; then \
	  echo ">> creating kind cluster $(KIND_CLUSTER)"; \
	  kind create cluster --config kind/cluster.yaml --wait 120s; \
	else echo ">> kind cluster $(KIND_CLUSTER) already exists"; fi
	@kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	@kubectl label namespace $(NAMESPACE) istio.io/dataplane-mode=ambient --overwrite

mesh: istioctl cluster ## Install Istio ambient mesh (ztunnel + CNI), no sidecars
	@ISTIO_VERSION=$(ISTIO_VERSION) ISTIOCTL=$(ISTIOCTL) NAMESPACE=$(NAMESPACE) \
	  bash bootstrap/install-istio-ambient.sh
	@kubectl apply -n $(NAMESPACE) -f manifests/mesh/waypoint.yaml

otel: cluster ## Install OpenTelemetry Collector + Jaeger
	@OTEL_VERSION=$(OTEL_VERSION) NAMESPACE=$(NAMESPACE) \
	  bash bootstrap/install-otel-collector.sh

cosign-key: cluster ## Load the szl-holdings cosign PUBLIC key as a configmap (no secret)
	@kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	@kubectl -n $(NAMESPACE) create configmap szl-cosign-pub \
	  --from-file=cosign.pub=keys/cosign.pub \
	  --dry-run=client -o yaml | kubectl apply -f -

organs: cluster cosign-key ## Deploy the 5 organ Deployments (cosign-gated)
	@for o in $(ORGANS); do \
	  echo ">> applying organ $$o"; \
	  kubectl apply -n $(NAMESPACE) -f manifests/organs/$$o.yaml; \
	done
	@echo ">> waiting for organs to settle (killinchu may block; see HONEST_GAPS.md)"
	@kubectl -n $(NAMESPACE) rollout status deploy/a11oy --timeout=180s || true
	@kubectl -n $(NAMESPACE) get pods -o wide

up: cluster mesh otel organs ## Bring up the entire stack
	@echo ""
	@echo "==> stack up. Jaeger UI: http://localhost:16686  |  demo gateway: http://localhost:8080"
	@$(MAKE) --no-print-directory status

status: ## Show pod + mesh status
	@echo "---- pods ----"; kubectl -n $(NAMESPACE) get pods -o wide || true
	@echo "---- ztunnel ----"; kubectl -n istio-system get pods -l app=ztunnel || true
	@echo "---- waypoint ----"; kubectl -n $(NAMESPACE) get gateways.gateway.networking.k8s.io || true

verify: ## Run the honest cosign + slsa-verifier supply-chain gate for every organ
	@ORGAN_TAG=$(ORGAN_TAG) NAMESPACE=$(NAMESPACE) bash verify/cosign-init.sh --all

trace: ## Send a request and dump the cross-organ traceparent trace tree
	@NAMESPACE=$(NAMESPACE) bash verify/run-acceptance.sh

demo: ## Scripted June 9 demo: up + verify + seeded request + trace + DSSE chain
	@bash demo/greene-demo.sh

down: ## Delete the kind cluster and all resources
	@kind delete cluster --name $(KIND_CLUSTER) || true
	@echo ">> cluster deleted."

clean: down ## down + remove downloaded binaries
	@rm -rf $(BIN) istio-$(ISTIO_VERSION)
