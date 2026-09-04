# /command-v2 ship path

Product origin: https://a-11-oy.com
Proof origin: https://a11oy.net
PR: https://github.com/szl-holdings/a11oy/pull/1935
Branch tip at time of writing: 9866f16

## Already on the branch
- web/command_v2.html (8-room monochrome skin, live API probes)
- a11oy_command_center.py registers GET+HEAD /command-v2
- /command and /console are not touched

## Blocker before merge
Dockerfile copies web HTML per-file. There is no `COPY web/ ./web/` and no `COPY web/command_v2.html`.
`COPY pages/ ./pages/` does exist.
`_v2_path()` on 9866f16 looks only at web/.
pages/command_v2.html is 404.

If 1935 merges as-is, hf-sync rebuilds SZLHOLDINGS/a11oy and /command-v2 returns 200 JSON UNAVAILABLE instead of the skin.

## Required next commit
One of:
1. Add pages/command_v2.html (byte copy of web/command_v2.html) and make `_v2_path()` check pages/ first.
2. Add `COPY web/command_v2.html ./web/` to the Dockerfile.

Then merge 1935. Then wait for hf-sync. Then GET https://a-11-oy.com/command-v2 must return text/html.

## Not in scope of this PR
Do not flip configured_is_operational.
Do not mint receipts.
Do not claim HMAC persistent.
Do not merge 1933/1934 with this PR.
