<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# vLLM and SGLang methodology

Primary status: **PREPARED IN A PR**

Generated: `2026-07-26T08:09:12.347408Z`

Status vocabulary: **DEPLOYED**, **IMPLEMENTED NOT DEPLOYED**, **PREPARED IN A PR**, **PROVED**, **MEASURED**, **MODELED**, **FAILED**, **BLOCKED**, **AWAITING AUTHORIZATION**, **DOWNGRADED**, and **RETIRED** are distinct and are not interchangeable.

The paired matrix fixes one GPU node, OS image digest, driver/CUDA versions, model revision, tokenizer revision, workload, prompt/output lengths, concurrency, request pattern, and repetition count. Each engine must run at least five repetitions for ShareGPT, random, long-context, and structured-output workloads. TTFT, TPOT, ITL, request and token throughput, error rate, failures, and environment identity are retained.

The Rust `vllm-bench` client is pinned to `v0.1.0` with x86_64-linux-musl digest `sha256:e2e246dfe34cd603b85e4d763f9aa6d60940be8b9cef48221f8a70d78420716c`. Candidate vLLM `0.26.0` and SGLang `0.5.16` are not compatibility-tested defaults.

Fairness and output validators fail on environment drift, missing paired engines, empty results, or unlabeled failure cells. Routing remains unchanged until all evidence is **MEASURED** and separately approved.
