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
