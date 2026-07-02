// Trading tools for Vesper (Crypto & Stock Genius). Alpaca REST.
// PAPER by default (APCA_PAPER !== "false"). Keys from env (loaded by env-loader).
// Gated into the agent ONLY when THINK_ENABLE_TRADING==="true" (vesper-think only).

const KEY = () => process.env.APCA_API_KEY_ID || "";
const SECRET = () => process.env.APCA_API_SECRET_KEY || "";
const IS_PAPER = () => process.env.APCA_PAPER !== "false";
const TRADE_BASE = () =>
  IS_PAPER() ? "https://paper-api.alpaca.markets" : "https://api.alpaca.markets";
const DATA_BASE = "https://data.alpaca.markets";
// Hard ceiling per single order (USD). Above this Vesper must get Rosa's explicit OK.
const MAX_NOTIONAL = Number(process.env.THINK_TRADE_MAX_NOTIONAL || 25000);

function headers() {
  return {
    "APCA-API-KEY-ID": KEY(),
    "APCA-API-SECRET-KEY": SECRET(),
    "Content-Type": "application/json",
  };
}
function configured() {
  return !!(KEY() && SECRET());
}
async function aGet(base, path) {
  const r = await fetch(base + path, { headers: headers() });
  const text = await r.text();
  let json;
  try { json = JSON.parse(text); } catch { json = { raw: text }; }
  if (!r.ok) return { ok: false, status: r.status, error: json.message || json, };
  return { ok: true, data: json };
}

export const account_summary = {
  name: "account_summary",
  description:
    "Get the current Alpaca brokerage account snapshot: buying power, cash, portfolio value, and whether this is a PAPER (practice) or LIVE account. Use before sizing any trade.",
  input_schema: { type: "object", properties: {}, required: [] },
  async execute() {
    if (!configured()) return { error: "Alpaca not configured (missing API keys)." };
    const r = await aGet(TRADE_BASE(), "/v2/account");
    if (!r.ok) return r;
    const a = r.data;
    return {
      mode: IS_PAPER() ? "PAPER (practice money)" : "LIVE (real money)",
      status: a.status,
      cash: a.cash,
      buying_power: a.buying_power,
      portfolio_value: a.portfolio_value,
      currency: a.currency,
      pattern_day_trader: a.pattern_day_trader,
    };
  },
};

export const market_quote = {
  name: "market_quote",
  description:
    "Get the latest market price for a stock (e.g. 'AAPL') or crypto (e.g. 'BTC/USD'). Returns the most recent trade price. Always quote a real price from here; never guess from memory.",
  input_schema: {
    type: "object",
    properties: { symbol: { type: "string", description: "Stock ticker like AAPL, or crypto pair like BTC/USD" } },
    required: ["symbol"],
  },
  async execute({ symbol }) {
    if (!configured()) return { error: "Alpaca not configured (missing API keys)." };
    if (!symbol) return { error: "symbol required" };
    const isCrypto = symbol.includes("/");
    if (isCrypto) {
      const r = await aGet(DATA_BASE, `/v1beta3/crypto/us/latest/trades?symbols=${encodeURIComponent(symbol)}`);
      if (!r.ok) return r;
      const t = r.data?.trades?.[symbol];
      return t ? { symbol, price: t.p, timestamp: t.t, asset: "crypto" } : { error: `no quote for ${symbol}`, raw: r.data };
    }
    const r = await aGet(DATA_BASE, `/v2/stocks/${encodeURIComponent(symbol)}/trades/latest`);
    if (!r.ok) return r;
    const t = r.data?.trade;
    return t ? { symbol, price: t.p, timestamp: t.t, asset: "stock" } : { error: `no quote for ${symbol}`, raw: r.data };
  },
};

export const list_positions = {
  name: "list_positions",
  description: "List all currently held positions (what the account owns right now) with market value and unrealized P/L.",
  input_schema: { type: "object", properties: {}, required: [] },
  async execute() {
    if (!configured()) return { error: "Alpaca not configured (missing API keys)." };
    const r = await aGet(TRADE_BASE(), "/v2/positions");
    if (!r.ok) return r;
    return {
      count: r.data.length,
      positions: r.data.map((p) => ({
        symbol: p.symbol, qty: p.qty, side: p.side, avg_entry: p.avg_entry_price,
        market_value: p.market_value, unrealized_pl: p.unrealized_pl, unrealized_plpc: p.unrealized_plpc,
      })),
    };
  },
};

export const list_orders = {
  name: "list_orders",
  description: "List recent orders (open and filled) so you can see what has been placed and its status.",
  input_schema: {
    type: "object",
    properties: { status: { type: "string", description: "open | closed | all (default: all)" } },
    required: [],
  },
  async execute({ status }) {
    if (!configured()) return { error: "Alpaca not configured (missing API keys)." };
    const s = ["open", "closed", "all"].includes(status) ? status : "all";
    const r = await aGet(TRADE_BASE(), `/v2/orders?status=${s}&limit=25&direction=desc`);
    if (!r.ok) return r;
    return {
      count: r.data.length,
      orders: r.data.map((o) => ({
        id: o.id, symbol: o.symbol, side: o.side, qty: o.qty, notional: o.notional,
        type: o.type, status: o.status, filled_qty: o.filled_qty, filled_avg_price: o.filled_avg_price, submitted_at: o.submitted_at,
      })),
    };
  },
};

export const place_order = {
  name: "place_order",
  description:
    "Place a buy or sell order for a stock or crypto. Defaults to a market order. You MUST quote the price (market_quote) and check account_summary first. In LIVE mode, orders above the safety cap are refused unless Rosa has explicitly approved them in this conversation (pass confirm_live=true only when she said yes).",
  input_schema: {
    type: "object",
    properties: {
      symbol: { type: "string", description: "AAPL (stock) or BTC/USD (crypto)" },
      side: { type: "string", description: "buy or sell" },
      notional: { type: "number", description: "Dollar amount to trade (use this OR qty)." },
      qty: { type: "number", description: "Number of shares/units (use this OR notional)." },
      type: { type: "string", description: "market (default) or limit" },
      limit_price: { type: "number", description: "Required if type=limit" },
      time_in_force: { type: "string", description: "day (stocks default) or gtc (required for crypto)" },
      confirm_live: { type: "boolean", description: "Only true when in LIVE mode and Rosa explicitly approved this specific trade." },
    },
    required: ["symbol", "side"],
  },
  async execute(input) {
    if (!configured()) return { error: "Alpaca not configured (missing API keys)." };
    const { symbol, side } = input;
    if (!symbol || !["buy", "sell"].includes(side)) return { error: "symbol and side(buy|sell) required" };
    if (!input.notional && !input.qty) return { error: "provide notional (dollars) or qty (units)" };

    const live = !IS_PAPER();
    const approxNotional = Number(input.notional || 0);
    if (approxNotional > MAX_NOTIONAL) {
      return {
        blocked: true,
        reason: `Order notional $${approxNotional} exceeds the safety cap of $${MAX_NOTIONAL}. Ask Rosa to confirm and split or raise the cap.`,
      };
    }
    if (live && !input.confirm_live) {
      return {
        blocked: true,
        reason: "This is a LIVE (real-money) account. Do not place it until Rosa explicitly approves; then retry with confirm_live=true.",
      };
    }

    const isCrypto = symbol.includes("/");
    const body = {
      symbol,
      side,
      type: input.type === "limit" ? "limit" : "market",
      time_in_force: input.time_in_force || (isCrypto ? "gtc" : "day"),
    };
    if (input.notional) body.notional = String(input.notional);
    else body.qty = String(input.qty);
    if (body.type === "limit") {
      if (!input.limit_price) return { error: "limit_price required for limit orders" };
      body.limit_price = String(input.limit_price);
    }

    const r = await fetch(TRADE_BASE() + "/v2/orders", {
      method: "POST", headers: headers(), body: JSON.stringify(body),
    });
    const text = await r.text();
    let json; try { json = JSON.parse(text); } catch { json = { raw: text }; }
    if (!r.ok) return { ok: false, status: r.status, error: json.message || json };
    return {
      ok: true,
      mode: IS_PAPER() ? "PAPER" : "LIVE",
      order: { id: json.id, symbol: json.symbol, side: json.side, qty: json.qty, notional: json.notional, type: json.type, status: json.status },
    };
  },
};

export const cancel_order = {
  name: "cancel_order",
  description: "Cancel an open order by its id.",
  input_schema: {
    type: "object",
    properties: { order_id: { type: "string" } },
    required: ["order_id"],
  },
  async execute({ order_id }) {
    if (!configured()) return { error: "Alpaca not configured (missing API keys)." };
    if (!order_id) return { error: "order_id required" };
    const r = await fetch(TRADE_BASE() + `/v2/orders/${encodeURIComponent(order_id)}`, {
      method: "DELETE", headers: headers(),
    });
    if (r.status === 204) return { ok: true, cancelled: order_id };
    const text = await r.text();
    return { ok: false, status: r.status, error: text.slice(0, 200) };
  },
};

export const TRADING_TOOLS = [account_summary, market_quote, list_positions, list_orders, place_order, cancel_order];
