/* SZL A11oy www-only canonical redirect v2.

   This edge worker is intentionally incapable of proxying the product apex or
   any application runtime. Its sole authority is to redirect the legacy
   `www.a-11-oy.com` hostname to the canonical `a-11-oy.com` product front
   door while preserving path and query. Unexpected hosts fail closed.
*/
const PRODUCT_HOST = "a-11-oy.com";
const WWW_HOST = "www.a-11-oy.com";
const EDGE_VERSION = "a11oy-www-redirect-v2";

function canonicalLocation(requestUrl) {
  const target = new URL(requestUrl);
  target.protocol = "https:";
  target.hostname = PRODUCT_HOST;
  target.port = "";
  return target.toString();
}

export default {
  async fetch(request) {
    const incoming = new URL(request.url);
    if (incoming.hostname !== WWW_HOST) {
      return new Response("Misdirected Request", {
        status: 421,
        headers: {
          "cache-control": "no-store",
          "content-type": "text/plain; charset=utf-8",
          "x-szl-edge": EDGE_VERSION,
        },
      });
    }

    return new Response(null, {
      status: 301,
      headers: {
        "cache-control": "public, max-age=86400",
        location: canonicalLocation(incoming.toString()),
        "x-szl-edge": EDGE_VERSION,
      },
    });
  },
};
