# Canonical PURIQ finance source backend

Status: source implementation and qualification, not a production-release receipt.
The logical home is **services/finance**, serving the canonical
`verticals/puriq-markets` core in `szl-holdings/a11oy`. The current generated
vertical manifest is preserved; this implementation does not rewrite its claims,
retire the independent `szl-quant` paper book, or create a second publisher.

## Connection and deployment path

`serve.py`'s existing `a11oy_markets.register` assembly registers
`verticals/puriq-markets/runtime/routes.py` before the SPA fallback. The existing
Docker COPY of `verticals/puriq-markets` already includes the full package.
A constant `importlib.import_module` path loads the existing hyphenated vertical
namespace; no caller input is used in module loading. Existing legacy market routes remain intact.

The existing flagship publisher's policy overlay adds only a thin finance read
projection to the generated app. The immutable base renderer is unchanged.
`SZLHOLDINGS/finance` remains the target. No new workflow writes Hugging Face.
A projection response fails closed when its canonical backend reports a different
source revision. Deploy and verify the canonical backend before publishing the
finance projection from the same admitted source revision.

## API

Canonical backend:

- `GET /api/a11oy/v1/finance/providers`: configured adapter metadata and prior
  observations, **not** an implicit connection test.
- `GET /api/a11oy/v1/finance/overview`: four bounded public snapshots, with explicit
  partial-failure state; not an all-market census or cross-venue equivalence claim.
- `GET /api/a11oy/v1/finance/observations/{source}`: one validated read request.

Existing finance Space projection:

- `GET /api/finance/providers`
- `GET /api/finance/overview`
- `GET /api/finance/observations/{source}` (public sources only)

The existing finance `/api/live` uses the new overview. A 200 response with a
partially unavailable body does not become LIVE. Endpoints contain no wallet,
account, custody, signing, order, cancel, deposit or withdrawal method.

## Adapters

| Source ID | Source-specific parameters | Notes |
|---|---|---|
| polymarket-markets | limit, offset | Active open Gamma markets; outcomes/prices/token IDs remain positional. |
| polymarket-book | token_id | Outcome-token CLOB book, bid/ask ordering, crossed-book and age flags. |
| polymarket-history | token_id, interval, fidelity | Bounded 1h/6h/1d/1w/1m history, no interpolation. |
| kalshi-markets | limit, cursor, series_ticker | Open markets; rules and fixed-point dollar prices; contract-volume units. |
| kalshi-book | ticker, depth | YES/NO bids; asks explicitly derived from complementary NO bids. |
| coinbase-products | none | Discover Exchange product identifiers, not a claim all products are tradable. |
| coinbase-ticker | product | Last-trade and bid/ask snapshot; 24h volume is in base-asset units. |
| coinbase-candles | product, granularity, end, count | Up to 300 completed candles in an explicit window; missing intervals preserved. |
| sec-submissions | cik, limit | Recent submission columns, CIK identity, filing/report dates; no historic-file inference. |
| sec-companyfacts | cik, limit | Bounded GAAP concepts with units and period context; no false full-year inference. |
| treasury-rates | limit | Average rates on Treasury securities, **not a current spot yield curve**. |
| treasury-debt | limit | Debt to the Penny, exact decimal-string values. |
| bls-series | series_id | Public recent series, annual averages distinguished from monthly observations. |
| fred-series | series_id, as_of, limit | Private read endpoint; explicit FRED/ALFRED as-of date and missing values. |
| alpaca-quote | symbol | Private entitled feed; defaults to IEX, not a consolidated-market claim. |
| alpaca-bars | symbol, timeframe, start, end, limit, page_token | Private raw bars; session completeness is not verified and replay eligibility remains false. |

All provider connections are HTTPS GET only. No automatic alternative provider
substitution, geographic bypass, account actions or raw upstream error messages.
Provider data and text are untrusted content, never agent instructions.

## Operator configuration

- `SZL_SEC_USER_AGENT`: an identified SEC User-Agent with your valid contact email.
  Missing or invalid configuration is explicitly unavailable, never guessed.
- `SZL_FRED_API_KEY`: FRED's required server-side API key.
- `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`: existing Alpaca data entitlements.
- `SZL_ALPACA_DATA_FEED`: `iex` (default), `sip`, or `delayed_sip`. Entitlements
  are not inferred from the presence of keys; provider denial remains visible.
- `SZL_FINANCE_PRIVATE_READ_TOKEN`: independently generated, minimum 32-character
  owner read token, required for **all FRED/Alpaca reads** in
  `X-SZL-Finance-Read-Token`. The public HF projection never forwards it.

Do not put credentials in code, URLs to these public endpoints, reports, browser
storage, CI output or chat. These are owner-only private sources, not a tenant
RBAC or data-redistribution grant. Review provider rights before customer use.

The documented FRED API itself requires an `api_key` query parameter. Only the
fixed server-to-FRED transport sends it; public provenance removes it, request
repr hides it, HTTP debugging is forced off, and exceptions never include URLs
or upstream response bodies. Environment proxies and redirects are disabled.

## Evidence, limits and availability

A source observation reports source-byte and normalized-data SHA-256 digests,
validated non-secret query, retrieval timestamp, adapter version and the
runtime-reported GitHub revision. Digests are not signatures and do not prove a
provider is correct. No receipt or signing side effect occurs on GET.

`SNAPSHOT`, `CACHED`, `STALE`, and `UNAVAILABLE` describe retrieval state.
Provider quote age is a separate field where the provider supplies a timestamp.
TTL freshness never grants execution eligibility. An expired cache entry can be
returned after refresh failure only as `STALE`, with `ok=false`, its original
provenance and timestamp, and the current failure code. Missing data stay null.

Requests are bounded by fixed hosts, scalar parameter schemas, response-size and
read deadlines, a 128-entry cache, per-provider locks and source cooldowns. There
is no recursive paging or uncontrolled retry loop. Coinbase gaps are not filled;
pagination is reported explicitly and does not imply whole-market completeness.
The public BLS budget uses at most one provider fetch per hour per process.

These are process-local controls, **not distributed rate quotas or durable
market-history storage**. Multi-replica deployment needs a reviewed shared
limiter. Historical archives, WebSocket reconnect/reconciliation, model
qualification, tick-to-trade latency and financial profitability are not claimed.
Neither the public Space nor these endpoints can spend the user's $1,000.

## Qualification and release

Run `python -m pytest tests/test_finance_source_contracts.py -q` from the repository
root. The dedicated workflow runs on every eligible main push and pull request
without path filters, using exact versions from the existing Docker API closure.
It tests parsing, money units, identity, missingness, cooldowns, concurrency,
stale behavior, transport controls, full market-route assembly and generated
finance-Space forwarding. It is not a replacement for the repository's existing
CI, scanners, doctrine, container, source-admission or publication gates.

`python scripts/finance_source_smoke.py` creates a public-read evidence folder.
Its success means collection finished; inspect `all_attempted_sources_available`
and individual failures. Credentialed sources are excluded, not counted as zero
or passed. A successful probe from GitHub is not proof the deployed HF runtime
has the same access or source revision.

After normal source admission: deploy through the existing canonical writer;
verify new routes return JSON from the exact current source; publish the finance
projection from that same source; verify all selected providers from the actual
runtime; retain provider failures, exact IDs and rollback evidence. Do not mark
production ready, trade-capable, calibrated or profitable from unit tests.

## Primary references

- Polymarket public data and outcome mapping: https://docs.polymarket.com/market-data/overview
- Kalshi public access: https://docs.kalshi.com/getting_started/quick_start_market_data
- Kalshi fixed-point books: https://docs.kalshi.com/getting_started/orderbook_responses
- Coinbase candle semantics and bounds: https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles
- SEC EDGAR API: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- Treasury FiscalData: https://fiscaldata.treasury.gov/api-documentation/
- BLS signatures: https://www.bls.gov/developers/api_signature_v2.htm
- FRED as-of observations: https://fred.stlouisfed.org/docs/api/fred/series_observations.html
- Alpaca market data: https://docs.alpaca.markets/docs/about-market-data-api
