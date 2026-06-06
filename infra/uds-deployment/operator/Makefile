# SZL Holdings — Warhacker Demo Cluster Makefile
# Doctrine v11 LOCKED 749/14/163 @ c7c0ba17 · Λ = Conjecture 1 · SLSA L1
# Section 889 = 5 vendors (Huawei, ZTE, Hytera, Hikvision, Dahua)
# NO Iron Bank / FedRAMP / CMMC / SWFT / Mission Owner
#
# Usage:
#   make demo-up         spin up k3d cluster + uds-core + 5 flagships + szl-mesh
#   make demo-status     report all 5 flagships' status + receipt chain
#   make demo-receipts   show the latest 10 receipts across the chain
#   make demo-tear-down  nuke the cluster cleanly
#
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>

SHELL        := /usr/bin/env bash
.SHELLFLAGS  := -euo pipefail -c

CLUSTER_NAME := szl-demo
UDS_VERSION  := 0.18.0
K3D_VERSION  := 5.8.3
UDS_CORE_TAG := 0.33.0-upstream
ARCH         := amd64

# HF Space base URL (live fallback endpoints)
HF_BASE      := https://szlholdings

# Colours
GREEN  := \033[0;32m
YELLOW := \033[1;33m
RED    := \033[0;31m
NC     := \033[0m

.DEFAULT_GOAL := help

.PHONY: help demo-up demo-status demo-receipts demo-tear-down \
        preflight cluster-create uds-init uds-core-deploy \
        flagships-deploy szl-mesh-deploy seed-receipts \
        cluster-delete clean

##@ Help
help: ## Print this help
	@awk 'BEGIN {FS = ":.*##"; printf "\n$(YELLOW)SZL Warhacker Demo Cluster$(NC)\n\nUsage:\n  make $(GREEN)<target>$(NC)\n\n"} \
	  /^[a-zA-Z_-]+:.*?##/ { printf "  $(GREEN)%-22s$(NC) %s\n", $$1, $$2 } \
	  /^##@/ { printf "\n$(YELLOW)%s$(NC)\n", substr($$0, 5) }' $(MAKEFILE_LIST)
	@echo ""
	@echo "  Doctrine: v11 LOCKED 749/14/163 · Λ = Conjecture 1 · SLSA L1"

##@ Demo Lifecycle

demo-up: ## [DEMO] Spin up k3d + UDS Core + 5 flagships + szl-mesh (≈ 10-20 min)
	@echo -e "$(YELLOW)=== SZL Demo Cluster — demo-up ===$(NC)"
	@$(MAKE) preflight
	@$(MAKE) cluster-create
	@$(MAKE) uds-init
	@$(MAKE) uds-core-deploy
	@$(MAKE) flagships-deploy
	@$(MAKE) szl-mesh-deploy
	@$(MAKE) seed-receipts
	@echo ""
	@echo -e "$(GREEN)✅  demo-up COMPLETE$(NC)"
	@echo -e "   Flagships: https://a11oy.uds.dev  https://sentra.uds.dev"
	@echo -e "             https://amaru.uds.dev   https://rosie.uds.dev"
	@echo -e "             https://killinchu.uds.dev"
	@echo ""
	@$(MAKE) demo-status

demo-status: ## [DEMO] Report all 5 flagships' status + receipt chain depth
	@echo -e "$(YELLOW)=== SZL Demo — Flagship Status ===$(NC)"
	@echo ""
	@echo "Cluster nodes:"
	@kubectl get nodes --no-headers 2>/dev/null || echo "  cluster not running"
	@echo ""
	@echo "Package CR status:"
	@for app in a11oy sentra amaru rosie killinchu; do \
	  phase=$$(kubectl get package szl-$${app} -n szl-$${app} \
	    -o jsonpath='{.status.phase}' 2>/dev/null || echo "NotFound"); \
	  if [ "$${phase}" = "Ready" ]; then \
	    echo -e "  $(GREEN)✅  szl-$${app}  phase=$${phase}$(NC)"; \
	  else \
	    echo -e "  $(RED)⛔  szl-$${app}  phase=$${phase}$(NC)"; \
	  fi; \
	done
	@echo ""
	@echo "Live HF Space health (internet fallback):"
	@for app in a11oy sentra amaru rosie killinchu; do \
	  status=$$(curl -sf --max-time 5 \
	    https://szlholdings-$${app}.hf.space/api/health \
	    -o /dev/null -w "%{http_code}" 2>/dev/null || echo "ERR"); \
	  if [ "$${status}" = "200" ]; then \
	    echo -e "  $(GREEN)✅  $${app}.hf.space  HTTP $${status}$(NC)"; \
	  else \
	    echo -e "  $(YELLOW)⚠️   $${app}.hf.space  HTTP $${status}$(NC)"; \
	  fi; \
	done
	@echo ""
	@echo "Receipt chain:"
	@if [ -f receipts/checksums.txt ]; then \
	  echo "  Checksums: $$(wc -l < receipts/checksums.txt) files"; \
	  if [ -f receipts/checksums.txt.sig ]; then \
	    echo "  Signature: receipts/checksums.txt.sig present"; \
	  else \
	    echo -e "  $(YELLOW)⚠️   No signature file (run: make sign-receipts)$(NC)"; \
	  fi; \
	else \
	  echo -e "  $(YELLOW)⚠️   No receipt checksums found$(NC)"; \
	fi
	@echo ""
	@echo "Doctrine pin:"
	@echo "  v11 LOCKED 749/14/163 @ c7c0ba17 · Λ = Conjecture 1 · SLSA L1"

demo-receipts: ## [DEMO] Show the latest 10 receipts across the chain
	@echo -e "$(YELLOW)=== SZL Demo — Receipt Chain (latest 10) ===$(NC)"
	@echo ""
	@echo "--- Local receipt file ---"
	@if [ -f receipts/demo-receipts.jsonl ]; then \
	  tail -10 receipts/demo-receipts.jsonl | python3 -c \
	    "import sys,json; \
	     [print(f\"  {r.get('timestamp','?')}  [{r.get('flagship','?')}]  \
	             action={r.get('action','?')}  verdict={r.get('verdict','?')}  \
	             hash={r.get('receipt_hash','?')[:12]}...\") \
	      for r in (json.loads(l) for l in sys.stdin)]"; \
	else \
	  echo "  No local receipt file. Run: make seed-receipts"; \
	fi
	@echo ""
	@echo "--- Live sentra audit log (top 10) ---"
	@curl -sf --max-time 8 \
	  https://szlholdings-sentra.hf.space/api/sentra/v1/audit-log 2>/dev/null \
	  | python3 -c \
	    "import json,sys; \
	     data=json.load(sys.stdin); \
	     entries=data if isinstance(data,list) else data.get('entries',[]); \
	     [print(f\"  {e.get('timestamp','?')}  verdict={e.get('verdict','?')}  \
	             action={str(e.get('action','?'))[:40]}\") \
	      for e in entries[-10:]]" 2>/dev/null \
	  || echo "  sentra not reachable"
	@echo ""
	@echo "--- Live amaru audit log (top 10) ---"
	@curl -sf --max-time 8 \
	  https://szlholdings-amaru.hf.space/api/amaru/v1/audit-log 2>/dev/null \
	  | python3 -c \
	    "import json,sys; \
	     data=json.load(sys.stdin); \
	     entries=data if isinstance(data,list) else data.get('entries',[]); \
	     [print(f\"  {e.get('timestamp','?')}  digest={str(e.get('digest','?'))[:16]}...\") \
	      for e in entries[-10:]]" 2>/dev/null \
	  || echo "  amaru not reachable"

demo-tear-down: ## [DEMO] Nuke the k3d cluster cleanly
	@echo -e "$(YELLOW)=== SZL Demo — tear-down ===$(NC)"
	@if k3d cluster list 2>/dev/null | grep -q "$(CLUSTER_NAME)"; then \
	  echo "  Deleting cluster: $(CLUSTER_NAME)"; \
	  k3d cluster delete $(CLUSTER_NAME); \
	  echo -e "  $(GREEN)✅  cluster deleted$(NC)"; \
	else \
	  echo "  No cluster named '$(CLUSTER_NAME)' found — nothing to do"; \
	fi
	@echo "  Removing dangling k3d volumes..."
	@docker volume prune -f --filter "label=app=k3d" 2>/dev/null || true
	@echo -e "$(GREEN)✅  tear-down COMPLETE$(NC)"

##@ Cluster Setup (called by demo-up)

preflight: ## Run scripts/preflight.sh before anything else
	@echo -e "$(YELLOW)--- preflight check ---$(NC)"
	@bash scripts/preflight.sh

cluster-create: ## Create k3d cluster with uds-k3d settings
	@echo -e "$(YELLOW)--- cluster-create ---$(NC)"
	@if k3d cluster list 2>/dev/null | grep -q "$(CLUSTER_NAME)"; then \
	  echo "  Cluster '$(CLUSTER_NAME)' already exists — skipping create"; \
	else \
	  echo "  Creating k3d cluster: $(CLUSTER_NAME)"; \
	  k3d cluster create $(CLUSTER_NAME) \
	    -p "80:80@server:*" \
	    -p "443:443@server:*" \
	    --api-port 6550 \
	    --runtime-ulimit nofile="1048576:1048576" \
	    --k3s-arg "--disable=traefik@server:*" \
	    --k3s-arg "--disable=metrics-server@server:*" \
	    --k3s-arg "--disable=servicelb@server:*" \
	    --k3s-arg "--disable=local-storage@server:*" \
	    --image ghcr.io/defenseunicorns/uds-k3d/k3s:v1.35.4-k3s1 \
	    --wait; \
	  echo -e "  $(GREEN)✅  cluster created$(NC)"; \
	fi
	@k3d kubeconfig get $(CLUSTER_NAME) > /tmp/szl-demo-kubeconfig.yaml
	@echo "  KUBECONFIG=/tmp/szl-demo-kubeconfig.yaml"
	$(eval export KUBECONFIG := /tmp/szl-demo-kubeconfig.yaml)
	@echo "  NOTE: export KUBECONFIG=/tmp/szl-demo-kubeconfig.yaml"

uds-init: ## Initialize zarf in the cluster
	@echo -e "$(YELLOW)--- uds zarf init ---$(NC)"
	@export KUBECONFIG=/tmp/szl-demo-kubeconfig.yaml && \
	  uds zarf tools download-init 2>/dev/null || true && \
	  uds zarf init --confirm --log-level warn
	@echo -e "  $(GREEN)✅  zarf initialized$(NC)"

uds-core-deploy: ## Deploy UDS Core (Istio, Keycloak, MetalLB, monitoring)
	@echo -e "$(YELLOW)--- uds-core deploy ---$(NC)"
	@echo "  Deploying uds-core $(UDS_CORE_TAG) (this takes 5-8 min)..."
	@export KUBECONFIG=/tmp/szl-demo-kubeconfig.yaml && \
	  uds deploy \
	    oci://ghcr.io/defenseunicorns/packages/uds/core:$(UDS_CORE_TAG) \
	    --confirm --log-level warn
	@echo -e "  $(GREEN)✅  UDS Core ready$(NC)"

flagships-deploy: ## Deploy all 5 flagship HF-based Deployments into cluster
	@echo -e "$(YELLOW)--- flagship deploy (5 apps) ---$(NC)"
	@export KUBECONFIG=/tmp/szl-demo-kubeconfig.yaml && \
	  kubectl apply -f configs/namespaces.yaml && \
	  kubectl apply -f configs/packages/package-a11oy.yaml -n szl-a11oy && \
	  kubectl apply -f configs/packages/package-sentra.yaml -n szl-sentra && \
	  kubectl apply -f configs/packages/package-amaru.yaml -n szl-amaru && \
	  kubectl apply -f configs/packages/package-rosie.yaml -n szl-rosie && \
	  kubectl apply -f configs/packages/package-killinchu.yaml -n szl-killinchu
	@echo -e "  Applying flagship Deployments..."
	@export KUBECONFIG=/tmp/szl-demo-kubeconfig.yaml && \
	  kubectl apply -f deploy/flagships/
	@echo -e "  $(GREEN)✅  flagship manifests applied$(NC)"
	@echo "  Waiting for flagship pods to be ready (timeout 300s)..."
	@export KUBECONFIG=/tmp/szl-demo-kubeconfig.yaml && \
	  for app in a11oy sentra amaru rosie killinchu; do \
	    kubectl rollout status deployment/szl-$${app} \
	      -n szl-$${app} --timeout=300s 2>/dev/null \
	      && echo -e "  $(GREEN)✅  $${app} ready$(NC)" \
	      || echo -e "  $(YELLOW)⚠️   $${app} not yet ready (may still be pulling)$(NC)"; \
	  done

szl-mesh-deploy: ## Deploy peat mesh node configs
	@echo -e "$(YELLOW)--- szl-mesh peat nodes ---$(NC)"
	@export KUBECONFIG=/tmp/szl-demo-kubeconfig.yaml && \
	  kubectl apply -f configs/peat/
	@echo -e "  $(GREEN)✅  peat mesh nodes applied$(NC)"

seed-receipts: ## Generate 20 demo receipts across 5 flagships
	@echo -e "$(YELLOW)--- seed-receipts ---$(NC)"
	@python3 scripts/seed-receipts.py
	@echo -e "  $(GREEN)✅  receipts seeded$(NC)"

##@ Build and Sign

sign-receipts: ## Generate and cosign-sign doctrine receipt checksums
	@echo -e "$(YELLOW)--- sign-receipts ---$(NC)"
	@mkdir -p receipts
	@find configs/ receipts/doctrine-pin.yaml -type f 2>/dev/null | sort | xargs sha256sum > receipts/checksums.txt
	@if [ -n "$${COSIGN_KEY_PATH}" ]; then \
	  cosign sign-blob \
	    --key "$${COSIGN_KEY_PATH}" \
	    --output-signature receipts/checksums.txt.sig \
	    receipts/checksums.txt && \
	  echo -e "  $(GREEN)✅  checksums.txt.sig written$(NC)"; \
	else \
	  echo -e "  $(YELLOW)⚠️   COSIGN_KEY_PATH not set — skipping signature$(NC)"; \
	  echo "  WARN: signature is PLACEHOLDER" > receipts/checksums.txt.sig; \
	fi

build: ## Build the Zarf package
	@echo -e "$(YELLOW)--- zarf package create ---$(NC)"
	@uds zarf package create . -a $(ARCH) --confirm --skip-sbom
	@echo -e "  $(GREEN)✅  Zarf package built$(NC)"

clean: ## Remove built Zarf package tarballs
	@rm -f zarf-package-*.tar.zst
	@echo "Cleaned Zarf tarballs"
