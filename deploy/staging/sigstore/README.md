<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Staging Sigstore admission preparation

Status: **PREPARED IN A PR**, not installed.

These manifests pin policy-controller `v0.15.1` and configure a warning-mode policy for the exact A11oy GitHub Actions signing identity. They do not label a namespace, install a chart, or mutate a cluster. Applying them requires a named staging cluster, authenticated operator, backup and restoration evidence, and explicit authorization.

`unsigned-pod.negative.yaml` is a retained negative fixture. A real rejection or warning is not claimed until its server response and controller event are captured from staging.
