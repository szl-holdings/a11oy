<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->
# Command Observation Context

## Scope

The existing additive `/command-v2` page gains a source inspector, explicit
refresh, and bounded client observation lifetime. `/command`, `/console`, the
canonical HF publisher, credentials, and action authorization are unchanged.
The original explicit kernel probe remains a separate user-initiated POST;
automatic refresh and source inspection never invoke it.

Missing counts are UNAVAILABLE, not zero. A real source-reported zero remains
zero. HTTP success plus a JSON object establishes only an OBSERVED response;
application health is rendered from its own status. Receipt signatures and chain
claims remain source-reported, not browser-verified. Numeric advisory values do
not coerce null, blank text, booleans, arrays, or numeric strings into readings.

Observations expire after 60 seconds of client time. This is a UI lifetime, not a
sensor calibration or freshness guarantee. A failed refresh replaces earlier
observations; expired payloads remain inspectable with an explicit STALE label,
but no longer supply headline values. Refresh is single-flight and uses the
existing 11 same-origin GET contracts, no credentials and no redirects. The
client batch is not an atomic server or cross-service snapshot.

## Comparative Interaction Study

On 2026-09-24, public browser interaction was performed on
[MetaMAP](https://metamap.bzzzbx.com/engine) and
[BOB](https://bob.bzzzbx.com/dashboard.html). This follows an earlier static
source inspection, not access to their private repository or backend.

- MetaMAP: opened the geography filter, entered a place, changed Now to Today,
  selected a location, and opened its BOBee pane. The pane explicitly named the
  selected location. Geographic search did not produce a selectable suggestion
  in this run, so successful place filtering is not claimed.
- BOB: selected the sessions metric, inspected its channel breakdown, opened
  its contextual BOBee pane, and changed Ahora to Hoy. The metric and date
  context visibly changed. Both tools contain simulation data; changing counters
  do not demonstrate real telemetry.
- No assistant messages, configuration applications, calls, SMS, email,
  uploads, or paid requests were initiated. No source, branding, or assets were
  copied. Only the general selected-item-to-evidence interaction is adapted.

## Physics Boundary

This change is an evidence interface, not a physics engine. Existing estate
thermal/PINN and energy instrumentation should be evaluated with device identity,
units, timestamps, counter resets and uncertainty before physical claims enter
the command center. GPU counters do not by themselves establish whole-machine
energy or isolated per-request attribution. Start with measured compute thermal
runs, a persistence/thermal-RC baseline, held-out run/device/time evaluation, and
advisory-only forecasts. Do not infer physical safety from abstract proof labels.

## Verification

```sh
node --test tests/test_command_observations.cjs
python -m unittest discover -s tests -p test_command_preview.py -v
python scripts/preview_command_observations.py --source fixture --port 8788
```

The loopback preview serves only this candidate page and 11 exact API paths.
Fixture mode is SYNTHETIC SOFTWARE QA, not a deployment witness. `--source live`
reads the public product origin without credentials; HTTP failures stay failures.
All preview POSTs are rejected, including the existing kernel probe. It does not
boot the application or start a GPU operator.

The broader command-origin/read-only run found 17 passes and 2 failures in
untouched code: a required quarantine wording marker and a legacy self-test that
rejects any Hugging Face Space link in the Killinchu page. Both failures also
reproduced in the earlier checkout. They are not suppressed or rewritten here.
Passing the new isolated tests is not a claim that the full suite is green.

Publication and runtime closure require the protected merge, canonical `hf-sync`
publication, immutable artifact verification and a new live browser witness.
