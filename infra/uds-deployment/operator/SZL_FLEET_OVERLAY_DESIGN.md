# SZL Fleet Overlay Design
<!-- PhD Systems Engineering — phd-systems-engineering/SZL_FLEET_OVERLAY_DESIGN.md -->
<!-- Doctrine: v11 LOCKED 749/14/163 at kernel commit c7c0ba17 | Λ = Conjecture 1 | SLSA L1 | Section 889 = 5 vendors -->

## 1. Purpose

`szl-fleet-overlay` is a UDS-managed package that **registers each SZL flagship application** (a11oy, sentra, amaru, rosie, killinchu) as a first-class UDS-managed application. It provides:

1. `Package` CRs for each flagship → Istio routing, NetworkPolicy, SSO, portal tiles
2. Doctrine-pinned receipts (`checksums.txt` + cosign signatures) for SLSA L1 attestation
3. Three deployment variants: **Helm chart**, **pure Zarf**, **peat-mesh-node**

All variants share the same `Package` CR definitions but differ in _how_ the application workloads are delivered.

**Compliance constraints from SHARED_CONTEXT.md**:
- SLSA L1 only (honest attestation)
- NO Iron Bank, NO FedRAMP, NO CMMC, NO SWFT
- Section 889: exclude Huawei, ZTE, Hytera, Hikvision, Dahua from image supply chain
- Doctrine v11 LOCKED 749/14/163

---

## 2. Fleet Application Inventory

| App | Namespace | Service Port | SSO Client ID | Group Gate | Peat Node |
|---|---|---|---|---|---|
| a11oy | `szl-a11oy` | 8080 | `uds-szl-a11oy` | `/szl-operators` | Yes |
| sentra | `szl-sentra` | 8080 | `uds-szl-sentra` | `/szl-operators` | Yes |
| amaru | `szl-amaru` | 8080 | `uds-szl-amaru` | `/szl-operators` | Yes |
| rosie | `szl-rosie` | 8080 | `uds-szl-rosie` | `/szl-operators` | Yes |
| killinchu | `szl-killinchu` | 8080 | `uds-szl-killinchu` | `/szl-operators` | Yes |

All applications are served over the UDS **tenant** gateway (default). No passthrough or admin gateway exposure unless a specific app requires raw TLS.

---

## 3. Repository Layout (`szl-fleet-overlay/`)

```
szl-fleet-overlay/
├── zarf.yaml                          # Pure-Zarf variant (canonical source)
├── uds-bundle.yaml                    # UDS Bundle for fleet deployment
├── tasks.yaml                         # Maru build/deploy tasks
│
├── chart/                             # Helm variant
│   ├── Chart.yaml
│   ├── values.yaml                    # Default values
│   ├── values/
│   │   ├── dev.yaml
│   │   ├── staging.yaml
│   │   └── prod.yaml
│   ├── crds/                          # (empty — CRDs shipped by uds-core)
│   └── templates/
│       ├── _helpers.tpl
│       ├── namespace-a11oy.yaml
│       ├── package-a11oy.yaml
│       ├── namespace-sentra.yaml
│       ├── package-sentra.yaml
│       ├── namespace-amaru.yaml
│       ├── package-amaru.yaml
│       ├── namespace-rosie.yaml
│       ├── package-rosie.yaml
│       ├── namespace-killinchu.yaml
│       └── package-killinchu.yaml
│
├── configs/
│   ├── packages/                      # Package CR YAMLs (all variants use these)
│   │   ├── package-a11oy.yaml
│   │   ├── package-sentra.yaml
│   │   ├── package-amaru.yaml
│   │   ├── package-rosie.yaml
│   │   └── package-killinchu.yaml
│   └── peat/                          # Peat mesh node configs
│       ├── peat-node-a11oy.yaml
│       ├── peat-node-sentra.yaml
│       ├── peat-node-amaru.yaml
│       ├── peat-node-rosie.yaml
│       └── peat-node-killinchu.yaml
│
└── receipts/                          # Doctrine-pinned receipts
    ├── checksums.txt                  # SHA256 of every config file
    ├── checksums.txt.sig              # cosign detached signature
    └── doctrine-pin.yaml             # Doctrine version lock record
```

---

## 4. Package CR Specification (canonical — shared by all variants)

### 4.1 Generic Package CR Template

```yaml
# configs/packages/package-<app>.yaml
apiVersion: uds.dev/v1alpha1
kind: Package
metadata:
  name: szl-<app>
  namespace: szl-<app>
  annotations:
    szl.io/doctrine-version: "v11"
    szl.io/doctrine-pin: "749/14/163"
    szl.io/kernel-commit: "c7c0ba17"
    szl.io/slsa-level: "L1"
spec:
  network:
    expose:
      - host: <app>
        service: szl-<app>
        port: 8080
        gateway: tenant
        selector:
          app: szl-<app>
    allow:
      # Egress to Keycloak for token introspection
      - direction: Egress
        description: "Keycloak OIDC endpoint"
        remoteNamespace: keycloak
        remoteSelector:
          app.kubernetes.io/name: keycloak
        port: 8443
        remoteProtocol: TLS
      # Egress to peat-mesh for CRDT sync
      - direction: Egress
        description: "Peat mesh QUIC sync"
        remoteNamespace: peat-system
        remoteSelector:
          app.kubernetes.io/name: peat-mesh
        port: 4001
        remoteProtocol: UDP
      # Intra-namespace: allow sidecar → app
      - direction: Ingress
        description: "IntraNamespace sidecar"
        remoteGenerated: IntraNamespace
  sso:
    - clientId: uds-szl-<app>
      name: "SZL <App>"
      protocol: openid-connect
      redirectUris:
        - "https://<app>.uds.dev/*"
      webOrigins:
        - "https://<app>.uds.dev"
      standardFlowEnabled: true
      enableAuthserviceSelector:
        app: szl-<app>
      groups:
        anyOf:
          - /szl-operators
      secretConfig:
        name: szl-<app>-oidc-secret
        template: |
          OIDC_CLIENT_ID: "{{ .clientId }}"
          OIDC_CLIENT_SECRET: "{{ .secret }}"
          OIDC_ISSUER: "https://sso.uds.dev/realms/uds"
  monitor:
    - description: "szl-<app> metrics"
      portName: http-metrics
      targetPort: 9090
      selector:
        app: szl-<app>
      path: /metrics
      kind: ServiceMonitor
```

### 4.2 App-Specific Package CRs

Each app follows the generic template above with concrete values substituted. The `package-a11oy.yaml` through `package-killinchu.yaml` files in `configs/packages/` are the authority. Helm and Zarf variants both **reference** these files rather than duplicating them.

---

## 5. Variant 1: Pure Zarf Package (`zarf.yaml`)

This is the **canonical air-gap delivery mechanism**. Produces a self-contained `.tar.zst` that requires only `zarf init` and `zarf package deploy`.

```yaml
# zarf.yaml
kind: ZarfPackageConfig
metadata:
  name: szl-fleet-overlay
  description: "SZL Fleet UDS Package Overlay — registers all SZL flagships as UDS-managed apps"
  version: "###ZARF_VAR_VERSION###"
  vendor: "SZL Holdings"
  url: "https://github.com/szl-holdings/szl-fleet-overlay"
  architecture: "###ZARF_VAR_ARCH###"
  # SLSA L1 — honest attestation only (no Iron Bank, no FedRAMP)
  yolo: false

constants:
  - name: DOCTRINE_VERSION
    value: "v11"
    description: "Locked doctrine version — NEVER change without board sign-off"
  - name: DOCTRINE_PIN
    value: "749/14/163"
  - name: KERNEL_COMMIT
    value: "c7c0ba17"
  - name: SLSA_LEVEL
    value: "L1"

variables:
  - name: VERSION
    description: "Package version"
    default: "0.1.0"
  - name: ARCH
    description: "Target architecture"
    default: "amd64"
  - name: DOMAIN
    description: "UDS cluster domain"
    default: "uds.dev"
  - name: SSO_GROUP
    description: "Keycloak group gate for all SZL apps"
    default: "/szl-operators"

components:
  # ── Phase 1: Namespaces (must exist before Package CRs) ──────────────────
  - name: szl-namespaces
    required: true
    description: "Create SZL application namespaces with UDS labels"
    manifests:
      - name: szl-namespaces
        files:
          - configs/namespaces.yaml   # all 5 namespaces in one file
    actions:
      onDeploy:
        after:
          - wait:
              cluster:
                kind: Namespace
                name: szl-a11oy
                condition: Exists

  # ── Phase 2: Package CRs (one component per app for granular control) ────
  - name: szl-a11oy-package
    required: true
    description: "UDS Package CR for a11oy"
    manifests:
      - name: szl-a11oy-package
        namespace: szl-a11oy
        files:
          - configs/packages/package-a11oy.yaml
    actions:
      onDeploy:
        after:
          - wait:
              cluster:
                kind: Package
                name: szl-a11oy
                namespace: szl-a11oy
                condition: "'{.status.phase}'=Ready"

  - name: szl-sentra-package
    required: true
    description: "UDS Package CR for sentra"
    manifests:
      - name: szl-sentra-package
        namespace: szl-sentra
        files:
          - configs/packages/package-sentra.yaml

  - name: szl-amaru-package
    required: true
    description: "UDS Package CR for amaru"
    manifests:
      - name: szl-amaru-package
        namespace: szl-amaru
        files:
          - configs/packages/package-amaru.yaml

  - name: szl-rosie-package
    required: true
    description: "UDS Package CR for rosie"
    manifests:
      - name: szl-rosie-package
        namespace: szl-rosie
        files:
          - configs/packages/package-rosie.yaml

  - name: szl-killinchu-package
    required: true
    description: "UDS Package CR for killinchu"
    manifests:
      - name: szl-killinchu-package
        namespace: szl-killinchu
        files:
          - configs/packages/package-killinchu.yaml

  # ── Phase 3: Peat mesh node configs (optional) ───────────────────────────
  - name: szl-peat-mesh-nodes
    required: false
    default: true
    description: "Peat mesh node CRDs and configs for CRDT-based state sync"
    manifests:
      - name: szl-peat-nodes
        files:
          - configs/peat/peat-node-a11oy.yaml
          - configs/peat/peat-node-sentra.yaml
          - configs/peat/peat-node-amaru.yaml
          - configs/peat/peat-node-rosie.yaml
          - configs/peat/peat-node-killinchu.yaml

  # ── Phase 4: Receipts ─────────────────────────────────────────────────────
  - name: szl-doctrine-receipts
    required: true
    description: "Doctrine-pinned receipts for SLSA L1 attestation"
    files:
      - source: receipts/checksums.txt
        target: /var/szl/receipts/checksums.txt
      - source: receipts/checksums.txt.sig
        target: /var/szl/receipts/checksums.txt.sig
      - source: receipts/doctrine-pin.yaml
        target: /var/szl/receipts/doctrine-pin.yaml
    actions:
      onDeploy:
        after:
          - cmd: |
              cosign verify-blob \
                --key /var/szl/receipts/cosign.pub \
                --signature /var/szl/receipts/checksums.txt.sig \
                /var/szl/receipts/checksums.txt && echo "Receipt signature VALID"
            description: "Verify doctrine receipt cosign signature"
```

---

## 6. Variant 2: Helm Chart

The Helm chart variant is for operators already running Helm-based GitOps (ArgoCD/Flux). The chart renders the same Package CRs as the Zarf variant, parameterized via Helm values.

### Chart.yaml

```yaml
apiVersion: v2
name: szl-fleet-overlay
description: "SZL Fleet UDS Package Overlay — Helm variant"
type: application
version: 0.1.0
appVersion: "0.1.0"
keywords:
  - uds
  - szl
  - fleet
  - air-gap
maintainers:
  - name: SZL Holdings Engineering
    email: eng@szlholdings.ai
dependencies: []   # uds-core CRDs assumed pre-installed
```

### values.yaml (excerpt)

```yaml
global:
  domain: uds.dev
  doctrinePinVersion: "v11"
  doctrinePinRef: "749/14/163"
  kernelCommit: "c7c0ba17"
  slsaLevel: "L1"
  ssoGroup: "/szl-operators"
  gatewayName: tenant

apps:
  a11oy:
    enabled: true
    namespace: szl-a11oy
    servicePort: 8080
    metricsPort: 9090
    clientId: uds-szl-a11oy
    displayName: "SZL A11oy"
    peatEnabled: true

  sentra:
    enabled: true
    namespace: szl-sentra
    servicePort: 8080
    metricsPort: 9090
    clientId: uds-szl-sentra
    displayName: "SZL Sentra"
    peatEnabled: true

  amaru:
    enabled: true
    namespace: szl-amaru
    servicePort: 8080
    metricsPort: 9090
    clientId: uds-szl-amaru
    displayName: "SZL Amaru"
    peatEnabled: true

  rosie:
    enabled: true
    namespace: szl-rosie
    servicePort: 8080
    metricsPort: 9090
    clientId: uds-szl-rosie
    displayName: "SZL Rosie"
    peatEnabled: true

  killinchu:
    enabled: true
    namespace: szl-killinchu
    servicePort: 8080
    metricsPort: 9090
    clientId: uds-szl-killinchu
    displayName: "SZL Killinchu"
    peatEnabled: true
```

### templates/_helpers.tpl

```
{{/*
Generate a UDS Package CR for an SZL app.
Usage: {{ include "szl-fleet.package" (dict "name" "a11oy" "app" .Values.apps.a11oy "global" .Values.global) }}
*/}}
{{- define "szl-fleet.package" -}}
apiVersion: uds.dev/v1alpha1
kind: Package
metadata:
  name: szl-{{ .name }}
  namespace: {{ .app.namespace }}
  annotations:
    szl.io/doctrine-version: {{ .global.doctrinePinVersion | quote }}
    szl.io/doctrine-pin: {{ .global.doctrinePinRef | quote }}
    szl.io/kernel-commit: {{ .global.kernelCommit | quote }}
    szl.io/slsa-level: {{ .global.slsaLevel | quote }}
    helm.sh/chart: {{ include "szl-fleet-overlay.chart" . }}
spec:
  network:
    expose:
      - host: {{ .name }}
        service: szl-{{ .name }}
        port: {{ .app.servicePort }}
        gateway: {{ .global.gatewayName }}
        selector:
          app: szl-{{ .name }}
    allow:
      - direction: Egress
        description: "Keycloak OIDC"
        remoteNamespace: keycloak
        remoteSelector:
          app.kubernetes.io/name: keycloak
        port: 8443
        remoteProtocol: TLS
      {{- if .app.peatEnabled }}
      - direction: Egress
        description: "Peat mesh QUIC"
        remoteNamespace: peat-system
        remoteSelector:
          app.kubernetes.io/name: peat-mesh
        port: 4001
        remoteProtocol: UDP
      {{- end }}
      - direction: Ingress
        description: "IntraNamespace"
        remoteGenerated: IntraNamespace
  sso:
    - clientId: {{ .app.clientId }}
      name: {{ .app.displayName | quote }}
      protocol: openid-connect
      redirectUris:
        - "https://{{ .name }}.{{ .global.domain }}/*"
      webOrigins:
        - "https://{{ .name }}.{{ .global.domain }}"
      standardFlowEnabled: true
      enableAuthserviceSelector:
        app: szl-{{ .name }}
      groups:
        anyOf:
          - {{ .global.ssoGroup }}
      secretConfig:
        name: szl-{{ .name }}-oidc-secret
        template: |
          OIDC_CLIENT_ID: "{{ "{{" }} .clientId {{ "}}" }}"
          OIDC_CLIENT_SECRET: "{{ "{{" }} .secret {{ "}}" }}"
          OIDC_ISSUER: "https://sso.{{ .global.domain }}/realms/uds"
  monitor:
    - description: "szl-{{ .name }} metrics"
      portName: http-metrics
      targetPort: {{ .app.metricsPort }}
      selector:
        app: szl-{{ .name }}
      path: /metrics
      kind: ServiceMonitor
{{- end -}}
```

### templates/package-a11oy.yaml

```yaml
{{- if .Values.apps.a11oy.enabled }}
{{ include "szl-fleet.package" (dict "name" "a11oy" "app" .Values.apps.a11oy "global" .Values.global "Chart" .Chart) }}
{{- end }}
```

*(Identical pattern for sentra, amaru, rosie, killinchu.)*

---

## 7. Variant 3: Peat Mesh Node

The peat-mesh-node variant wraps the fleet overlay with `peat-node` sidecars, enabling Automerge+Iroh QUIC CRDT-based state sync between the SZL flagship apps.

### Architecture

```
┌────────────────────────────────────────────────────────────────┐
│ szl-a11oy namespace                                            │
│                                                                │
│  ┌─────────────────────────────┐    ┌──────────────────────┐  │
│  │  szl-a11oy (main container) │←──→│  peat-node sidecar   │  │
│  │  port 8080 (HTTP)           │    │  port 4001 (QUIC)    │  │
│  │  port 9090 (metrics)        │    │  port 50051 (gRPC)   │  │
│  └─────────────────────────────┘    └──────────┬───────────┘  │
└───────────────────────────────────────────────┼────────────────┘
                                                │ QUIC/Iroh
                                        ┌───────▼──────────┐
                                        │  peat-mesh CRDT  │
                                        │  (peat-system ns)│
                                        └──────────────────┘
```

### peat-node config (`configs/peat/peat-node-a11oy.yaml`)

```yaml
# PeatNode CR — instructs peat-mesh to inject a peat-node sidecar
# into the szl-a11oy deployment
apiVersion: peat.dev/v1alpha1
kind: PeatNode
metadata:
  name: szl-a11oy
  namespace: szl-a11oy
spec:
  selector:
    matchLabels:
      app: szl-a11oy
  mesh:
    # Reference to the peat-mesh instance in peat-system
    meshRef:
      name: szl-fleet-mesh
      namespace: peat-system
  grpc:
    port: 50051
  quic:
    port: 4001
    listenAddr: "0.0.0.0"
  crdt:
    # Automerge document namespace for this app
    documentNamespace: "szl.a11oy"
    # Sync all SZL apps in the same document set
    peers:
      - "szl.sentra"
      - "szl.amaru"
      - "szl.rosie"
      - "szl.killinchu"
  resources:
    requests:
      cpu: "50m"
      memory: "64Mi"
    limits:
      cpu: "200m"
      memory: "256Mi"
```

---

## 8. Doctrine-Pinned Receipts

### `receipts/doctrine-pin.yaml`

```yaml
# SZL Doctrine Receipt — SLSA L1 honest attestation
# Doctrine v11 LOCKED — NEVER change these values without board sign-off
apiVersion: szl.io/v1
kind: DoctrineReceipt
metadata:
  name: szl-fleet-overlay-receipt
  createdAt: "2026-06-03T00:00:00Z"
spec:
  doctrine:
    version: "v11"
    pin: "749/14/163"
    kernelCommit: "c7c0ba17"
    lambda: "Conjecture 1"   # Λ = Conjecture 1 (NEVER theorem)
  compliance:
    slsaLevel: "L1"
    section889Vendors:       # Exactly 5 — Section 889 prohibited vendors
      - Huawei
      - ZTE
      - Hytera
      - Hikvision
      - Dahua
    excludedFrameworks:
      - IronBank
      - FedRAMP
      - CMMC
      - SWFT
      - MissionOwner
  packages:
    - name: szl-fleet-overlay
      version: "0.1.0"
      checksumFile: "checksums.txt"
      signedBy: "szl-holdings-cosign-key"
  attestations:
    - type: "PackageIntegrity"
      method: "cosign-detached-signature"
      keyRef: "cosign.pub"
```

### Generating the Receipt in CI

```bash
# In tasks.yaml:
tasks:
  - name: sign-receipts
    description: "Generate and sign doctrine receipts"
    actions:
      - cmd: |
          # Generate checksums of all config files
          find configs/ -type f | sort | xargs sha256sum > receipts/checksums.txt
          echo "$(sha256sum receipts/doctrine-pin.yaml)" >> receipts/checksums.txt
          # Sign with cosign (key in COSIGN_KEY env var injected by CI)
          cosign sign-blob \
            --key "${COSIGN_KEY_PATH}" \
            --output-signature receipts/checksums.txt.sig \
            receipts/checksums.txt
        description: "Sign receipts with cosign"
```

---

## 9. Deployment Order (strictly follows SHARED_CONTEXT.md sequence)

```
Phase                     Command
─────────────────────────────────────────────────────────────────
1. Zarf init (once)       uds zarf init --confirm
2. Deploy uds-core        uds deploy oci://ghcr.io/defenseunicorns/packages/uds/core:0.33.0-upstream
3. Deploy fleet overlay   uds deploy oci://ghcr.io/szl-holdings/fleet-overlay:0.1.0 --confirm
   (or Helm variant)      helm upgrade --install szl-fleet-overlay ./chart -n szl-system --create-namespace \
                            -f chart/values/prod.yaml
4. Verify portal tiles    curl -sk https://portal.uds.dev/api/packages | jq '.[] | select(.name | startswith("szl"))'
5. Verify receipts        cosign verify-blob --key cosign.pub --signature receipts/checksums.txt.sig receipts/checksums.txt
```

---

## 10. tasks.yaml (Maru)

```yaml
includes:
  - actions: https://raw.githubusercontent.com/defenseunicorns/uds-common/refs/tags/v1.24.9/tasks/actions.yaml

variables:
  - name: VERSION
    default: "0.1.0"
  - name: ARCH
    default: "amd64"
  - name: REGISTRY
    default: "ghcr.io/szl-holdings"

tasks:
  - name: default
    description: "Full build and local dev deploy"
    actions:
      - task: build
      - task: deploy-local

  - name: build
    description: "Build the Zarf package"
    actions:
      - cmd: uds zarf package create . -a ${ARCH} --confirm --skip-sbom
        description: "Create szl-fleet-overlay Zarf package"

  - name: sign-receipts
    description: "Sign doctrine receipts"
    actions:
      - cmd: |
          find configs/ -type f | sort | xargs sha256sum > receipts/checksums.txt
          cosign sign-blob --key "${COSIGN_KEY_PATH}" \
            --output-signature receipts/checksums.txt.sig \
            receipts/checksums.txt
        description: "Generate and sign checksums"

  - name: publish
    description: "Publish to GHCR"
    actions:
      - cmd: uds zarf package publish zarf-package-szl-fleet-overlay-${ARCH}-${VERSION}.tar.zst oci://${REGISTRY}/
        description: "Push to GHCR"

  - name: deploy-local
    description: "Deploy to local k3d cluster"
    actions:
      - cmd: uds zarf package deploy zarf-package-szl-fleet-overlay-${ARCH}-*.tar.zst --confirm
        description: "Deploy fleet overlay"

  - name: validate
    description: "Validate all Package CRs reached Ready phase"
    actions:
      - cmd: |
          for app in a11oy sentra amaru rosie killinchu; do
            phase=$(kubectl get package szl-${app} -n szl-${app} -o jsonpath='{.status.phase}' 2>/dev/null)
            if [ "${phase}" != "Ready" ]; then
              echo "FAIL: szl-${app} phase=${phase}"
              exit 1
            fi
            echo "OK: szl-${app} Ready"
          done
        description: "Check Package CR phases"
      - cmd: |
          cosign verify-blob \
            --key receipts/cosign.pub \
            --signature receipts/checksums.txt.sig \
            receipts/checksums.txt && echo "Receipt VALID"
        description: "Verify doctrine receipt"
```
