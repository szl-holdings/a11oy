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
