/* SZL A11oy product-root edge adapter v1.
   Scope: exact apex root plus the www redirect route configured by the controller. */
const PRODUCT_HOST = "a-11-oy.com";
const WWW_HOST = "www.a-11-oy.com";
const ORIGIN_HOST = "szlholdings-a11oy.hf.space";
const EDGE_VERSION = "a11oy-product-root-v1";

function productLocation(value) {
  if (!value) return value;
  try {
    const target = new URL(value);
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

export default {
  async fetch(request) {
    const incoming = new URL(request.url);
    if (incoming.hostname === WWW_HOST) {
      incoming.protocol = "https:";
      incoming.hostname = PRODUCT_HOST;
      incoming.port = "";
      return Response.redirect(incoming.toString(), 301);
    }

    const upstream = new URL(request.url);
    upstream.protocol = "https:";
    upstream.hostname = ORIGIN_HOST;
    upstream.port = "";

    const headers = new Headers(request.headers);
    headers.delete("host");
    headers.set("x-forwarded-host", PRODUCT_HOST);
    headers.set("x-forwarded-proto", "https");
    headers.set("x-szl-edge-request", EDGE_VERSION);

    const init = {
      method: request.method,
      headers,
      redirect: "manual",
    };
    if (request.method !== "GET" && request.method !== "HEAD") init.body = request.body;

    const response = await fetch(upstream, init);
    const output = new Headers(response.headers);
    output.set("x-szl-edge", EDGE_VERSION);
    output.set("link", `<https://${PRODUCT_HOST}${incoming.pathname || "/"}>; rel="canonical"`);
    const location = productLocation(output.get("location"));
    if (location) output.set("location", location);

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: output,
    });
  },
};
