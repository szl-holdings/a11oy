<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# GitHub CLI immutable acquisition - 2026-10-21

## Plan and scope

Workcell: A11oy #2933 build unblock. Change only the Dockerfile's GitHub CLI
acquisition, its exact reviewed RUN hash, focused negative regression checks,
and identity/acquisition documentation. Preserve the NodeSource fingerprint,
source-file catalog, unchanged layer ceiling, and every runtime admission gate.
No merge, provider publication, restart, credential change, or effect activation.

## Evidence and selected artifact

MEASURED: container workflow [39561712741](https://github.com/szl-holdings/a11oy/actions/runs/39561712741)
failed at `apt-get install gh=2.102.0`. The same pin exists in the base main
Dockerfile. The official [amd64 apt index](https://cli.github.com/packages/dists/stable/main/binary-amd64/Packages)
listed only 2.102.1 during this investigation. Pinning that moving index again
would leave acquisition dependent on its current contents.

The selected [official immutable 2.102.1 release](https://github.com/cli/cli/releases/tag/v2.102.1)
has release ID `418794335`, package asset ID `660284788`, and package size
15,396,970 bytes. Package URL:
`https://github.com/cli/cli/releases/download/v2.102.1/gh_2.102.1_linux_amd64.deb`.
SHA-256: `5b91c75d971509e96f673fa9f46e5d8ea294b6bbfedbc8ff458aedd88775d94c`.

MEASURED: downloaded package hash matches both the release API digest and
the current signed-repository index digest. Command
`gh release verify-asset v2.102.1 gh_2.102.1_linux_amd64.deb --repo cli/cli --format json`
returned exit 0 and verified the immutable release statement naming `cli/cli`,
tag `v2.102.1`, release ID `418794335`, and this package digest. This is upstream
release authentication, not A11oy deployment or independent runtime evidence.

The patch version is deliberate. The [official release notes](https://github.com/cli/cli/releases/tag/v2.102.1)
upgrade Go 1.27.1 to 1.27.3 and `golang.org/x/net` 0.58.0 to 0.60.0.
[Go release history](https://go.dev/doc/devel/release) identifies the 1.27.3
`crypto/x509` security repair; [GO-2026-6610](https://pkg.go.dev/vuln/GO-2026-6610)
and [GO-2026-6611](https://pkg.go.dev/vuln/GO-2026-6611) cover HTTP/2 dependency
versions below 0.60.0. This closes those version ranges; a complete binary
vulnerability audit and application-specific reachability analysis are NOT RUN.

## Validation

MEASURED: `docker build --progress=plain --pull=false` using an isolated context
containing the exact production base image and the unchanged extracted
Node/GitHub CLI acquisition RUN completed with exit 0. Its local image ID is
`sha256:26098dcf2273b2a50d3fee19944f309f121b776fd67036640828195bd4d96621`.
The build printed a successful package checksum before `dpkg` installation and
the exact `gh version 2.102.1` check. A subsequent `docker run --network none`
confirmed the installed version. This image contains only that acquisition
slice; it is not the complete application image.

MEASURED: inside that Linux image, with the source mounted read-only,
`python -m pytest -q -p no:cacheprovider --basetemp /tmp/a11oy-gh-tests tests/test_gdw_installed_source_builder.py tests/test_dockerfile_layer_budget.py`
completed with exit 0: 80 passed, zero skipped, in 18.19 seconds using pytest
8.4.2. Five negative cases reject acquisition URL, digest, version, architecture,
or checksum-command changes through the existing exact RUN review boundary.
An independent six-case source review run also passed. A separate network-free
checksum harness altered the downloaded package and observed checksum exit 1;
no installer was invoked for those altered bytes.

The Windows command encountered the existing pytest temporary-root access
denial: 68 passed, 13 setup errors after the change versus 63 passed and the
same 13 errors before it. No test was relaxed or skipped. An initial Linux
invocation raced image export and exited 125; its failed log remains preserved
beside the successful retry.

Local evidence directory: `outputs/a11oy-gh-release-20261021/` in the execution
workspace. The command-bound `report.json` SHA-256 is
`383074bbd8717cd025a4ecb4b17d03dade32dfefbf940d0956d3e6b7b08f3eec`.
It binds source-file hashes, verified upstream statement, build, Linux tests,
Windows limitation, and altered-package result. Build log SHA-256:
`3a3546309d68d4edb8c02d3c02a80b31e052c93c5edeaac603076702dcc83894`;
Linux test log SHA-256:
`8576868172cf883f608f52b0ff98170f6f0f876382c472f6d8d1a3e8139d85b3`.

Full application container build: NOT RUN locally; exact combined-candidate
hosted CI remains required. Live deployment and runtime identity qualification:
NOT RUN by this workcell.

## Isolated current-main recovery qualification

The five-file acquisition repair is also isolated onto protected main
`5d737c092d988de54713eabd0a38e602292169ce` so it can recover the canonical
build independently of the replication candidate. The exact Node/GitHub CLI
RUN and runtime base equal the slice built above; its logical RUN SHA-256 is
`4f419e3db1a8e5176e265daea5880d65dde18c5c26d9f6f704d4c5f61cd42789`.
This preserves all NodeSource fingerprint checks. It does not assume a stale
published Docker layer will be reusable.

MEASURED: the same two test files reran against the isolated recovery checkout
in Linux with a read-only source mount, read-only root filesystem, writable
temporary filesystem and networking disabled: **80 passed, zero skipped,
10.61 seconds**. The command used pytest 8.4.2 installed in a test-only child
of the verified acquisition image. The first test-image build incorrectly used
a local image ID as a registry image name and failed; the retained retry checked
the local tag's exact image ID before building. Evidence is in
`outputs/a11oy-gh-main-recovery-20261021/`, including `source-equality.json`,
`linux-test-command.json` and `linux-tests.log`. Test log SHA-256:
`1a180dbab9de4b86bc5d72ed5297ee70da6e061195ba4d0021e32e8dc682a8e0`.

MEASURED: main-push [hf-sync run 39548239025](https://github.com/szl-holdings/a11oy/actions/runs/39548239025)
reported `Deploy window closed (stage=RUNNING); nothing was written or deployed`.
Deployment and downstream runtime jobs were skipped. A fresh public Space API
read at 2026-10-21T07:52:06Z still reported RUNNING at revision
`5b24fb31077a464951b0d4236a427a6a6bb5fd99`. The unchanged workflow opens the
window only for a PAUSED Space or explicit workflow dispatch with
`open_deploy_window=true`; it gates configuration convergence and deploy on
that decision. A future merge must re-read the current stage. Main pushes also
trigger the existing GHCR image-publish workflow; this is distinct from a Space
restart. No provider write, pause, restart or dispatch was performed here.

Existing PR #2930 covers overlapping immutable acquisition for 2.102.0. This
repair uses the independently verified 2.102.1 security release and leaves that
PR untouched. The exact-head full application build and normal protected merge
checks remain required; local source qualification is not live readiness.

## Required dependency and fixture companions

The first isolated recovery head `50945dd38fbaa7270b8a6bcde53e941682ad2227`
passed all eight protected status contexts but exposed existing security and
fixture failures in additional checks. Their logs and artifacts are preserved:

- Grype run 39565357265 found only Vite 6.4.3: one High and two Medium
  advisories. The reviewed exact 6.4.4 override/lock repair is included; see
  `audit/VITE_ADVISORY_2026-10-21.md` for frozen-install, consumer tests and
  old/new same-database scan evidence. No unrelated package graph changes.
- Finance run 39565357383 artifact 12329795947 identifies only generated
  `certifi==2026.7.22`, PYSEC-2026-4320 / GHSA-6q48-6c7w-9gw2. Apply the
  reviewed 2026.10.19 requirement, its expected-version assertion and exact
  generated requirements hash. The earlier actual generated Linux image
  qualification checked 23 installed pins, 15 route outcomes and zero audit
  findings. Its receipt is `outputs/finance-certifi-image-linux-20261021/receipt.json`,
  SHA-256 `f9488e2f4aab73550135a891927e5196ec5c4f2133f4094c43de10335944fca4`.
- GDW run 39565357743 job 119106205804 reported 1 failed, 3,096 passed,
  22 skipped and 11 passing subtests:
  the historical rehearsal expected the old upload-artifact SHA, while main
  already uses v7.0.2. Refresh only that exact expected SHA, as in existing
  PR #2931; leave the workflow and assertion strictness unchanged. That PR
  remains untouched. Fresh selected historical tests: 10 passed, 91 deselected.

MEASURED: the recovery's Finance source and exact generated-file mutation tests
ran in a network-disabled Linux container with read-only source/root:
`python -B -m pytest tests/test_finance_emitted_runtime.py tests/test_hf_publish_vertical_flagships_v4.py -q -p no:cacheprovider --basetemp /tmp/pytest`.
Result: **96 passed, zero skipped, two existing deprecation warnings, 26.35 seconds**.
The command receipt is `outputs/a11oy-gh-main-recovery-20261021/finance-companion-test-command.json`;
log SHA-256 `9b0443a68fdf7b61e906c00fe518bb1826c2f7fdf6e83e89fb778818c1ee39c6`.
These companions contain no replication implementation or authentication changes.

The canonical deploy-window observation above applies only to Space
`SZLHOLDINGS/a11oy`. The separate unchanged
`.github/workflows/hf-publish-vertical-flagships.yml` triggers on this Finance
contract path, hourly, and after a successful hf-sync workflow (including a
closed canonical window). Its plan may publish changed vertical Spaces without
the canonical window input. Therefore the closed canonical window is not a
global provider hold. Merge remains held pending review of those target-state
effects, the exact-head full image build, required checks and security checks.
