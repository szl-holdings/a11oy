<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->
# Shared shell source qualification

The shared shell color repair keeps evidence states separate from optical
decoration. Its original component fixture checks those semantics, text and
control contrast, touch targets, focus, reduced motion and forced colors.

That fixture alone does not cover the four HTML consumers: the current console,
legacy console, model estate and Atelier. Atelier's generic `nav` rules can also
turn the actual command palette's `nav.szl-pal-list` into columns. The palette now
declares a column flex layout in its existing component rule.

The first [hosted source run](https://github.com/szl-holdings/a11oy/actions/runs/37218043775)
passed all four component widths and 11 of 16 source cases. It retained two
remaining failures: the console More menu escaped at 320px, and Atelier's main
script contained a Python `or` inside a JavaScript template expression. The menu
now clamps its horizontal position to the actual viewport; the template uses the
JavaScript fallback operator. Shared investor navigation also only invokes the
console's view router, since Atelier has a different global `go` function for
model selection. The source check now requires Atelier's main content to render
and verifies its investor destination. Visual review also found the bottom flow
navigation painting above the palette backdrop. The palette now uses the
existing global layer token, and the browser check compares its layer with page
navigation. Fresh hosted results remain required.

Repairing Atelier boot also makes its toy callbacks reachable. Missing bundled
metrics and malformed weights must produce UNAVAILABLE; they cannot substitute a
fixed accuracy, probability, embedding, threshold, timing or residual. Valid
bundled NumPy observations retain their timestamp and synthetic/sample scope;
the toy callbacks do not establish live model quality. The source browser check
executes positive controls with the bundled data and negative controls with
missing, nonnumeric, nonfinite, out-of-range and malformed in-memory data. The
checked-in model inventory and bundled measurements are preserved.

The [second hosted run](https://github.com/szl-holdings/a11oy/actions/runs/37219765062)
passed all 16 candidate source cases and all 121 Atelier evidence controls.
Screenshot review still found Atelier's article confined to the sidebar column
and a mobile More destination obscured by the status row. The desktop sidebar
rule now follows its mobile default, the action zone paints above the status
zone, and the More menu scrolls within the available viewport height. The same
source check now verifies desktop column geometry and the first and last More
keyboard destinations by hit testing, with fresh screenshots required.

`tools/check_shared_shell_source_browser.py` loads each of those real sources,
their local CSS and JavaScript, and vendored font bytes through an intercepted
browser context. It never contacts a live provider. All provider requests receive
an explicit UNAVAILABLE response, except for named synthetic inventory cards
that exercise the existing estate renderer with long identifiers. Those cards
carry REPORTED and SOFTWARE labels and no measurement or verification result.

The source check covers 320×568, 375×812, 768×1024 and 1440×900. It records document
and shared component text overflow, effective action targets, declared fonts used
by the shell, and JavaScript errors. It exercises keyboard access to More,
command-palette layout, Escape handling and focus restoration, both console
themes, and the forced-color decoration fallback. Intentional horizontal scroll
regions are recorded separately from text escaping its containing viewport.

Each report records the exact HTML, stylesheet and served-asset SHA-256 values.
The optional immutable base comparison substitutes the base stylesheet into the
same candidate HTML and assets. It is a controlled stylesheet comparison, not a
reconstruction of an entire historical deployment. Baseline failures remain in
the report. Every candidate case must pass.

The read-only `Shared shell source qualification` job retains JSON reports and
screenshots. It uses the repository's existing pinned Playwright test runner and
does not add an application dependency, a publisher, a provider credential or a
new action path.

To reproduce with the already installed browser runner:

```sh
python tools/check_shared_shell_source_browser.py --output /new/evidence/directory
```

An optional `--chromium` selects a local executable; nothing is downloaded by the
script. `--base` accepts only a full commit SHA. A missing browser or a failed
source case remains a failure. Source qualification does not establish deployed
revision, API health, model quality, server authorization or WCAG conformance.
