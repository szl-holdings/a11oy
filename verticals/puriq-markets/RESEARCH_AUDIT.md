<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# PURIQ research audit

The research workspace extends the existing Finance presentation with a stateless
annual-panel audit. It does not fit a regression, run a backtest, fetch arbitrary
URLs, persist submitted records, or authorize trades. The public Finance
projection forwards only to the canonical A11oy endpoint and verifies its exact
source revision, submitted input digest, response contract, and unsigned receipt.

## Use

Open the Finance `/research` page. Load the explicitly synthetic example or paste
a JSON packet, choose **As known on**, and select **Audit research packet**.
The date control overrides the packet's `as_of` field. Editing any input clears
the previous result and export. Export retains submitted inputs, the complete
bounded audit, and an unsigned integrity receipt. It proves internal consistency,
not source authenticity or causal validity.

Canonical API: `POST /api/a11oy/v1/finance/research/audit`.
Finance projection: `POST /api/finance/research/audit`.
Both reject query parameters and bodies over 160,000 bytes. Provider URLs are
metadata only and are never fetched by this audit.

```json
{
  "as_of": "2024-12-31",
  "expected_entities": ["County A", "County B"],
  "start_year": 2023,
  "end_year": 2023,
  "records": [
    {"entity": "County A", "period": 2023, "value": 0,
     "state": "observed", "available_at": "2024-06-01", "group": "Large"},
    {"entity": "County B", "period": 2023, "value": 0,
     "state": "suppressed", "available_at": "2024-06-01", "group": "Small"}
  ],
  "specifications": [
    {"label": "Synthetic baseline", "estimate": 0.2, "standard_error": 0.1,
     "n": 60, "clusters": 4},
    {"label": "Synthetic alternate trend", "estimate": -0.1,
     "standard_error": 0.15, "n": 48, "clusters": 4}
  ]
}
```

## Interpretation and bounds

- Classify disclosure flags before submission. For BLS QCEW employment/wages,
  a zero with disclosure code `N` is suppressed; a true disclosed zero remains
  observed. The generic panel audit does not parse source-specific raw files.
- Kept observations require an observed finite numeric value, a unique in-scope
  entity-year, no caller exclusion, and a supplied release date on or before the
  cutoff. Omit `available_at` when unknown; it will be flagged and excluded.
  Supplied dates are not independently verified historical vintages.
- Suppressed, missing, invalid, and observed-null records stay distinct. All
  duplicate rows are excluded; no arbitrary duplicate wins. Duplicates block
  structural acceptance. Other flags remain visible even when an audit completes.
- Coverage counts distinct observed numeric cells before date/exclusion filters.
  Eligibility counts use those filters. Missing cells include unusable or absent
  cells; absent cells have no supplied row. Raw records and cells have different
  denominators. A zero denominator returns null. Without a complete expected grid,
  wholly absent entities or periods may be invisible.
- Supplied estimates are `REPORTED`, unverified, and never recomputed. A sign change
  prompts review. Fewer than 30 declared clusters is a screening heuristic, not a
  significance or validity test. Matched split-sample estimates and year effects
  alone do not resolve a differential measurement discontinuity.
- The engine accepts at most 5,000 records, 1,000 entities, a 100-year range,
  10,000 expected cells, and 100 specifications; HTTP byte limits may bind earlier.
  Coverage detail is capped at 1,000 cells with an explicit truncation flag. The UI
  displays 150 of those cells. Per-record audit and aggregate counts remain in
  the export. JSON numeric underflow/nonfinite values are rejected; floating-point
  values are audit inputs, not exact decimal accounting amounts.

## Public sources and product decisions

Reviewed 7 October 2026. This is a selected primary-source research set, not an
exhaustive industry census. No third-party implementation was copied and no
endorsement is implied.

| Reference | Applied pattern |
| --- | --- |
| [OpenBB standardization](https://docs.openbb.co/odp/v4/python/developer/standardization) | Explicit schemas and missing-value semantics. |
| [QuantConnect custom data](https://www.quantconnect.com/docs/v2/writing-algorithms/importing-data/streaming-data/custom-securities/key-concepts) | Information-availability time separate from observation period. |
| [Microsoft Qlib](https://github.com/microsoft/qlib) | Data preparation and quality checks as visible stages of research. |
| [FRED / ALFRED real-time periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html) | As-of controls; actual vintage retrieval remains future work for this audit. |
| [BLS QCEW FAQ](https://www.bls.gov/cew/questions-and-answers.htm) | Disclosure-aware zero/suppression classification. |
| [IRS migration data](https://www.irs.gov/statistics/soi-tax-stats-migration-data) | Period-specific source documentation and methodological changes. |
| [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) | Preserve filing dates, units, and period context. |
| [Susan Athey, Stanford](https://economics.stanford.edu/people/susan-athey) | Identification and research design alongside machine learning. |
| [Andrew Patton, Duke](https://scholars.duke.edu/person/andrew.patton) | Financial forecast evaluation and volatility research. |
| [Athey and Imbens, applied econometrics](https://arxiv.org/abs/1607.00699) | Sensitivity and robustness comparisons with explicit scope. |

## Validation and release

Run the existing Finance source-contract suite plus
`tests/test_finance_research_audit.py` and `tests/test_finance_research_routes.py`.
The existing browser qualification also exercises the research example, cutoff,
zero/suppression distinction, sign flag, input invalidation, literal-text rendering,
and export at four viewport widths.

Use the canonical controller after protected-main merge, then the existing
flagship publisher with explicit `scope=finance`. The publisher must observe the
same source revision on canonical A11oy before writing Finance. Read back both
revision identities and exercise the new audit endpoint before claiming the
feature is published. Do not publish directly around these gates.
