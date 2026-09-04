/* SZL A11oy canonical product edge v3.

   Protected-main proof retrigger: 2026-09-04. Runtime semantics unchanged.

   Exact authority:
   - a-11-oy.com/*      -> fixed SZLHOLDINGS/a11oy Space origin
   - www.a-11-oy.com/*  -> 301 to the canonical apex, preserving path + query

   The browser never receives a redirect to the .hf.space origin. Unexpected
   hosts fail closed. Provider/network failures return 502, never a synthetic 2xx.
*/
const PRODUCT_HOST = "a-11-oy.com";
const WWW_HOST = "www.a-11-oy.com";
const ORIGIN_HOST = "szlholdings-a11oy.hf.space";
const EDGE_VERSION = "a11oy-product-edge-v3";
const READ_ONLY_METHODS = new Set(["GET", "HEAD"]);
const PUBLIC_ROUTE_ALIASES = Object.freeze({
  "/spectral": "/static/3d/holographic.html",
  "/spectral/": "/static/3d/holographic.html",
  "/controller": "/api/a11oy/v1/honest",
  "/controller/": "/api/a11oy/v1/honest",
});

const STRIP_REQUEST_HEADERS = [
  "host",
  "cf-connecting-ip",
  "cf-ipcountry",
  "cf-ray",
  "cf-visitor",
  "x-forwarded-for",
  "x-forwarded-host",
  "x-forwarded-proto",
  "x-real-ip",
];

export function canonicalLocation(requestUrl) {
  const target = new URL(requestUrl);
  target.protocol = "https:";
  target.hostname = PRODUCT_HOST;
  target.port = "";
  return target.toString();
}

export function resolveOriginPath(pathname, method = "GET") {
  if (!READ_ONLY_METHODS.has(String(method).toUpperCase())) return pathname;
  return PUBLIC_ROUTE_ALIASES[pathname] || pathname;
}

export function originLocation(requestUrl, method = "GET") {
  const target = new URL(requestUrl);
  target.protocol = "https:";
  target.hostname = ORIGIN_HOST;
  target.port = "";
  target.pathname = resolveOriginPath(target.pathname, method);
  return target;
}

export function rewriteOriginLocation(value) {
  if (!value) return value;
  try {
    const target = new URL(value, `https://${ORIGIN_HOST}`);
    if (target.hostname === ORIGIN_HOST || target.hostname.endsWith(".hf.space")) {
      target.protocol = "https:";
      target.hostname = PRODUCT_HOST;
      target.port = "";
      return target.toString();
    }
  } catch (_) {
    return value;
  }
  return value;
}

function requestHeaders(source) {
  const headers = new Headers(source);
  for (const name of STRIP_REQUEST_HEADERS) headers.delete(name);
  headers.set("x-forwarded-host", PRODUCT_HOST);
  headers.set("x-forwarded-proto", "https");
  headers.set("x-szl-edge-request", EDGE_VERSION);
  return headers;
}

function errorResponse(status, error) {
  return Response.json(
    { error },
    {
      status,
      headers: {
        "cache-control": "no-store",
        "x-szl-edge": EDGE_VERSION,
      },
    },
  );
}

export async function handleRequest(request, fetchImpl = fetch) {
  const incoming = new URL(request.url);

  if (incoming.hostname === WWW_HOST) {
    return new Response(null, {
      status: 301,
      headers: {
        "cache-control": "public, max-age=86400",
        location: canonicalLocation(incoming.toString()),
        "x-szl-edge": EDGE_VERSION,
      },
    });
  }

  if (incoming.hostname !== PRODUCT_HOST) {
    return errorResponse(421, "misdirected_request");
  }

  const upstream = originLocation(incoming.toString(), request.method);
  const headers = requestHeaders(request.headers);
  let outgoing;
  try {
    outgoing = new Request(upstream.toString(), request);
    outgoing = new Request(outgoing, { headers, redirect: "manual" });
  } catch (_) {
    return errorResponse(400, "invalid_request");
  }

  let response;
  try {
    response = await fetchImpl(outgoing);
  } catch (_) {
    return errorResponse(502, "origin_unavailable");
  }

  const output = new Headers(response.headers);
  output.set("x-szl-edge", EDGE_VERSION);
  if (upstream.pathname !== incoming.pathname) {
    output.set("x-szl-edge-alias", `${incoming.pathname}->${upstream.pathname}`);
  }
  output.set(
    "link",
    `<https://${PRODUCT_HOST}${incoming.pathname || "/"}>; rel="canonical"`,
  );

  for (const name of ["location", "content-location"]) {
    const rewritten = rewriteOriginLocation(output.get(name));
    if (rewritten) output.set(name, rewritten);
  }

  const allowOrigin = output.get("access-control-allow-origin");
  if (allowOrigin === `https://${ORIGIN_HOST}`) {
    output.set("access-control-allow-origin", `https://${PRODUCT_HOST}`);
  }

  return new Response(request.method === "HEAD" ? null : response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: output,
  });
}

export default {
  async fetch(request) {
    return handleRequest(request);
  },
};
