const RELAY_HOST = "ntfy.a11oy.net";
const UPSTREAM_ORIGIN = "https://ntfy.sh";
const MAX_JSON_BYTES = 64 * 1024;
const TOPIC_HASH_HEX_LENGTH = 60;
const ALLOWED_METHODS = new Set(["GET", "HEAD", "POST", "PUT", "OPTIONS"]);
const BODYLESS_METHODS = new Set(["GET", "HEAD"]);
const SUBSCRIPTION_SUFFIXES = new Set(["json", "sse", "raw", "ws"]);

class PayloadTooLargeError extends Error {}

function jsonError(status, error) {
  return Response.json(
    { error },
    {
      status,
      headers: {
        "cache-control": "no-store",
      },
    },
  );
}

async function deriveTopic(pathname) {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(pathname),
  );
  const hex = [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
  return `szl_${hex.slice(0, TOPIC_HASH_HEX_LENGTH)}`;
}

function splitSubscriptionPath(pathname, method) {
  if (!BODYLESS_METHODS.has(String(method).toUpperCase())) {
    return { topicPath: pathname, suffix: "" };
  }
  const finalSlash = pathname.lastIndexOf("/");
  if (finalSlash <= 0) {
    return { topicPath: pathname, suffix: "" };
  }
  const candidate = pathname.slice(finalSlash + 1).toLowerCase();
  if (!SUBSCRIPTION_SUFFIXES.has(candidate)) {
    return { topicPath: pathname, suffix: "" };
  }
  return {
    topicPath: pathname.slice(0, finalSlash),
    suffix: `/${candidate}`,
  };
}

export async function toUpstreamUrl(requestUrl, method = "POST") {
  const incoming = new URL(requestUrl);
  const upstream = new URL(UPSTREAM_ORIGIN);
  if (incoming.pathname !== "/") {
    const { topicPath, suffix } = splitSubscriptionPath(incoming.pathname, method);
    upstream.pathname = `/${await deriveTopic(topicPath)}${suffix}`;
  }
  upstream.search = incoming.search;
  return upstream;
}

async function readBoundedText(request, maxBytes) {
  const declaredLength = Number(request.headers.get("content-length"));
  if (Number.isFinite(declaredLength) && declaredLength > maxBytes) {
    throw new PayloadTooLargeError("declared body exceeds limit");
  }
  if (!request.body) {
    return "";
  }

  const reader = request.body.getReader();
  const chunks = [];
  let received = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      received += value.byteLength;
      if (received > maxBytes) {
        await reader.cancel("body exceeds limit").catch(() => {});
        throw new PayloadTooLargeError("streamed body exceeds limit");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }

  const body = new Uint8Array(received);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new TextDecoder().decode(body);
}

function sanitizedHeaders(source) {
  const headers = new Headers(source);
  for (const name of [
    "host",
    "cookie",
    "cf-connecting-ip",
    "cf-ipcountry",
    "cf-ray",
    "cf-visitor",
    "x-forwarded-for",
    "x-forwarded-proto",
  ]) {
    headers.delete(name);
  }
  return headers;
}

function isJson(contentType) {
  const mediaType = (contentType || "").split(";", 1)[0].trim().toLowerCase();
  return mediaType === "application/json" || mediaType.endsWith("+json");
}

async function buildUpstreamRequest(request, upstream) {
  const headers = sanitizedHeaders(request.headers);
  if (!BODYLESS_METHODS.has(request.method) && isJson(headers.get("content-type"))) {
    let rawBody;
    try {
      rawBody = await readBoundedText(request, MAX_JSON_BYTES);
    } catch (error) {
      if (error instanceof PayloadTooLargeError) {
        return jsonError(413, "payload_too_large");
      }
      throw error;
    }

    let payload;
    try {
      payload = JSON.parse(rawBody);
    } catch {
      return jsonError(400, "invalid_json");
    }

    let body = rawBody;
    if (
      payload !== null &&
      typeof payload === "object" &&
      !Array.isArray(payload) &&
      Object.hasOwn(payload, "text")
    ) {
      if (typeof payload.text !== "string" || payload.text.trim() === "") {
        return jsonError(422, "invalid_slack_text");
      }
      body = payload.text;
      headers.set("content-type", "text/plain; charset=utf-8");
    }
    headers.delete("content-length");
    return new Request(upstream, {
      method: request.method,
      headers,
      body,
      redirect: "manual",
    });
  }

  let forwarded = new Request(upstream, request);
  forwarded = new Request(forwarded, {
    headers,
    redirect: "manual",
  });
  return forwarded;
}

export async function handleRequest(request, fetchImpl = fetch) {
  const incoming = new URL(request.url);
  if (incoming.hostname.toLowerCase() !== RELAY_HOST) {
    return jsonError(421, "misdirected_request");
  }
  if (!ALLOWED_METHODS.has(request.method)) {
    return new Response(null, {
      status: 405,
      headers: {
        allow: [...ALLOWED_METHODS].join(", "),
        "cache-control": "no-store",
      },
    });
  }
  if (!BODYLESS_METHODS.has(request.method) && incoming.pathname === "/") {
    return jsonError(404, "topic_required");
  }

  const upstream = await toUpstreamUrl(request.url, request.method);
  const outgoing = await buildUpstreamRequest(request, upstream);
  if (outgoing instanceof Response) {
    return outgoing;
  }

  try {
    const response = await fetchImpl(outgoing);
    return new Response(response.body, response);
  } catch (error) {
    console.error(
      JSON.stringify({
        event: "ntfy_relay_upstream_error",
        error_class: error instanceof Error ? error.name : "UnknownError",
      }),
    );
    return jsonError(502, "upstream_unavailable");
  }
}

export default {
  async fetch(request) {
    return handleRequest(request);
  },
};
