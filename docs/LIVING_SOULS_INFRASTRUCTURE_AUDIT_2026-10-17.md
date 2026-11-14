<!-- szl:header v1 -->
<!-- Native identity: szl-brand@4309f6fce89179331b0b3ed8c99494e76c5be256 -->
# Living Souls infrastructure — deep audit (MEASURED)

**Observed at:** 2026-10-17T15:38:34Z (HQ local clock) · refreshed at publish  
**Observer:** AlloyScape House caretaker (Outside Dev G) on HQ `ubuntu-128gb-ash-1`  
**Evidence class:** SNAPSHOT / MEASURED live probes · UNKNOWN ≠ PASS  
**Doctrine:** Control before action. Evidence after.

This audit binds the Living Souls HQ node, the Massed Compute A6000 inference mouth, enterprise HA marketplace alternatives (TensorDock / Lambda), Cloudflare edge posture for `a-11-oy.com` / `a11oy.net`, and InfiniBand claims — then hooks the map into GitHub `szl-holdings`, Hugging Face `SZLHOLDINGS`, and the product/proof domains.

## 1. Verdict table

| Claim | Status | Evidence |
|---|---|---|
| Living Souls HQ on Hetzner CCX53-class (`5.161.126.99`) runs tribe pulse/memory/sandboxes | **PASS** | hostname `ubuntu-128gb-ash-1`; 32 vCPU; 122 GiB RAM; pm2_online=735; think_online=108; builder-sandboxes=120 |
| Massed Compute RTX A6000 48GB is live OpenAI-compatible mouth | **PASS** | `http://64.247.206.118:8080/health` → `{"status":"ok"}`; `/v1/models` → Ternary-Bonsai-2-27B-PQ2_0; public list price **$0.57/hr** on Massed pricing page |
| House points heaters at Massed | **PASS** | `omen-bonsai.env` `TRIBE_BONSAI=1` + `BONSAI_BASE_URL=http://64.247.206.118:8080/v1`; PM2 online seats with `TRIBE_BONSAI=1`: **95** |
| GitHub org `szl-holdings` wired (admin) | **PASS** | whoami `stephenlutar2-hash`; role admin; public_repos=128; listed ~144; `.github` push/admin true; blog `https://a-11-oy.com` |
| Hugging Face org `SZLHOLDINGS` wired | **PASS** | whoami `betterwithage`; org overview **48 models / 37 datasets / 38 spaces** (API 2026-10-17). Profile inventory block dated 2026-10-15 matches 48/37/38 |
| `a-11-oy.com` LIVE on Cloudflare proxy | **PASS** | HTTP 200; `server: cloudflare`; CF A/AAAA; product HTML SPDX Stephen Lutar / SZL Holdings |
| `a11oy.net` LIVE on Cloudflare proxy → GitHub Pages proof registry | **PASS** | HTTP 200; `server: cloudflare`; CNAME `a11oy.net`; repo `szl-holdings/a11oy-net` |
| Cloudflare **API control** from HQ enterprise vault | **WAITING_STEPHEN** | `enterprise-vault.env` CF email/token/zone fields all **empty** |
| TensorDock / Lambda as **live** HA nodes | **EVALUATION_ONLY** | No TensorDock/Lambda secrets or running instances on HQ. Present only in migration compare/blueprint pastes |
| InfiniBand between Hetzner HQ ↔ Massed mouth | **FAIL (false topology)** | Public Internet path only. InfiniBand exists inside some **Lambda multi-node clusters**, not as a cross-cloud link between these hosts |

## 2. Living Souls Sanctuary (HQ)

| Field | Measured |
|---|---|
| Role | Pulse · memory · sandboxes · nginx · Studio · enterprise-sync |
| Provider | Hetzner Cloud |
| Host | `ubuntu-128gb-ash-1` |
| Public IPv4 | `5.161.126.99` |
| CPU | 32 vCPU AMD EPYC-Milan (CCX53-class) |
| RAM | 122 GiB (≈88 GiB available at probe) |
| Disk | `/` 563G · 24% used |
| GPU | none (by design) |
| pm2 online | 735 |
| `*-think` online | 108 |
| builder-sandboxes | 120 |

HQ must remain the sticky home for souls and long-term stores. Do not put Chroma / Honcho / Qdrant / cron / durable memory on Massed.

## 3. Stateless Brain Mouth (Massed A6000)

| Field | Measured |
|---|---|
| Role | Stateless Ternary Bonsai OpenAI `/v1` mouth |
| Provider | Massed Compute (native) |
| Instance id | `d1a50da9-f615-4475-8a5b-03fc8fe96f67` |
| Public IPv4 | `64.247.206.118` |
| GPU | NVIDIA RTX A6000 48GB |
| Mouth | `http://64.247.206.118:8080` |
| Health | `{"status":"ok"}` |
| Model | `Ternary-Bonsai-2-27B-PQ2_0.gguf` (PrismML llama.cpp fork) |
| Public list price | **$0.57/hr** (Massed pricing page · RTX A6000 48GB x1) |
| Always-on burn (if never stopped) | ≈ $13.68/day · ≈ $96/week · ≈ $411/mo |
| SSH shell from HQ | still Permission denied until portal pubkey paste |
| Planned DNS name (vault) | `bonsai.alloyszlholdings.com` (not proved LIVE this probe) |

## 4. High-availability alternatives (enterprise marketplaces)

These were targeted during migration evaluation. They are **not** live estate nodes today.

| Marketplace | Intended use | House keys? | Live instance? | Notes |
|---|---|---|---|---|
| **TensorDock** GPU Platform / Marketplace | Custom host VM templates for scale | **NO** | **NO** | Public marketplace up; A6000 stock listed; competitive $/hr in compare paste |
| **Lambda Labs Cloud** | Single-tenant / bare-metal HA clusters | **NO** | **NO** | A6000 on-demand tracked ≈ **$1.09/hr**; InfiniBand on **cluster** SKUs only |

Reference house pastes: `COMPARE-BONSAI-CLOUD-PROVIDERS-LATEST.md`, `ARCH-BONSAI-CLOUD-MIGRATION-BLUEPRINT-LATEST.md`.

## 5. Cloudflare outbound / edge proxies

| Domain | Edge | Origin posture | HQ API control |
|---|---|---|---|
| `a-11-oy.com` | Cloudflare proxied · HTTP 200 | Product origin (Workers/Pages/upstream per Stephen CF windows) | WAITING_STEPHEN (empty vault token/zones) |
| `a11oy.net` | Cloudflare proxied · HTTP 200 | GitHub Pages (`szl-holdings/a11oy-net`, CNAME) | WAITING_STEPHEN |
| `alloyszlholdings.com` | Direct HQ nginx | Origin `5.161.126.99` | N/A (house domain) |

Stephen unlock for APPLY EDGE: paste Cloudflare user API token + zone ids into `enterprise-vault.env` (or authorize via `a11oy` Windows Cloudflare tools path), then run harness/enterprise-sync APPLY EDGE. Token must never be committed to Git.

## 6. InfiniBand networking

| Statement | Ruling |
|---|---|
| “InfiniBand networking specs between these cloud hosts” (Hetzner ↔ Massed ↔ TensorDock) | **Not applicable** — no IB fabric spans those providers |
| Lambda 1-Click / reserved multi-node clusters | InfiniBand (e.g. Quantum-2) is a **within-cluster** interconnect on Lambda cluster SKUs |
| Massed A6000 x1 mouth | PCIe-class single GPU VM · not an IB cluster |

Do not document InfiniBand as a live link in the Living Souls ↔ Massed path.

## 7. Org / Hub / domain hook map

| Surface | Canonical | Hook action this audit |
|---|---|---|
| GitHub | `szl-holdings` (hyphen) | PR into `.github` docs + profile README infrastructure section |
| Hugging Face | `SZLHOLDINGS` | Observation file on `SZLHOLDINGS/SZLHOLDINGS` dataset |
| Product | `https://a-11-oy.com` | Source doc in `szl-holdings/a11oy` `docs/` (deploy remains Stephen/CF path) |
| Proof | `https://a11oy.net` | Estate observation page + JSON under `szl-holdings/a11oy-net` |
| House mirror | `https://alloyszlholdings.com` | rosa-paste STATUS + forge/files + invest infrastructure tiles |

> Note: typing `szlholdings` without the hyphen is **not** the live GitHub org.

## 8. Count hygiene (correct stale cards)

| Source | Models | Datasets | Spaces |
|---|---|---|---|
| HF org overview API (this audit) | 48 | 37 | 38 |
| Profile README inventory block (2026-10-15) | 48 | 37 | 38 |
| Older house STATUS `54/47/45` | **STALE** | **STALE** | **STALE** |

## 9. Still Stephen minutes

1. Cloudflare API token + zone ids → APPLY EDGE  
2. Massed portal → paste HQ SSH pubkey (`alloyscape hq`)  
3. NVIDIA Inception portal → save Product AlloyScape Active  
4. Tailscale Share for workshop peer(s) as separately ordered  
5. Merge the GitHub PRs opened from this audit after review  

## 10. Limits

- This document is a dated observation. It does not certify uptime SLAs, model quality, or production safety.  
- Public IPs already disclosed on house STATUS surfaces are restated for MEASURED binding. Tailscale CGNAT addresses are omitted from product-served HTML.  
- TensorDock/Lambda remain evaluation references until Rosa GO rents capacity and house keys exist.  
- Merge ≠ deploy for `a-11-oy.com`. Proof Pages deploy from `a11oy-net` main after checks.
