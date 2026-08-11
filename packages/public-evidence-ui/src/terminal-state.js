export const TERMINAL_STATES = Object.freeze([
  "VERIFIED",
  "REACHABLE",
  "DEGRADED",
  "STALE",
  "FAILED",
  "BLOCKED",
  "UNAVAILABLE",
]);

export const TRANSIENT_STATES = Object.freeze(["OBSERVING"]);

const TERMINAL_SET = new Set(TERMINAL_STATES);
const TRANSIENT_SET = new Set(TRANSIENT_STATES);

export function normalizeState(state) {
  return String(state ?? "UNAVAILABLE").trim().toUpperCase();
}

export function isTerminalState(state) {
  return TERMINAL_SET.has(normalizeState(state));
}

export function isPublicState(state) {
  const normalized = normalizeState(state);
  return TERMINAL_SET.has(normalized) || TRANSIENT_SET.has(normalized);
}

export function observation(state, detail, extras = {}) {
  const normalized = normalizeState(state);
  if (!isPublicState(normalized)) {
    throw new TypeError(`Unsupported public state: ${normalized}`);
  }

  return Object.freeze({
    state: normalized,
    detail: String(detail ?? ""),
    observedAt: extras.observedAt ?? new Date().toISOString(),
    source: extras.source ?? null,
    httpStatus: extras.httpStatus ?? null,
    value: extras.value ?? null,
    reasons: Array.isArray(extras.reasons) ? extras.reasons : [],
  });
}

export async function observeJson(
  url,
  {
    timeoutMs = 8_000,
    fetchImpl = globalThis.fetch,
    assessor = null,
    requestInit = {},
  } = {},
) {
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0 || timeoutMs > 8_000) {
    throw new TypeError("timeoutMs must be a positive finite number no greater than 8000");
  }

  if (typeof fetchImpl !== "function") {
    return observation("UNAVAILABLE", "Fetch transport is unavailable.", {
      source: url,
    });
  }

  const controller = new AbortController();
  let timer;
  const timeout = new Promise((resolve) => {
    timer = setTimeout(() => {
      controller.abort("public observation timeout");
      resolve(
        observation("UNAVAILABLE", `No response within ${timeoutMs} ms.`, {
          source: url,
        }),
      );
    }, timeoutMs);
  });

  const request = (async () => {
    try {
      const response = await fetchImpl(url, {
        cache: "no-store",
        credentials: "omit",
        redirect: "follow",
        ...requestInit,
        signal: controller.signal,
      });

      if (!response || typeof response.ok !== "boolean") {
        return observation("FAILED", "Fetch returned an invalid response object.", {
          source: url,
        });
      }

      if (!response.ok) {
        return observation("FAILED", `HTTP ${response.status}.`, {
          source: url,
          httpStatus: response.status,
        });
      }

      let payload;
      try {
        payload = await response.json();
      } catch (error) {
        return observation(
          "FAILED",
          `Response was not valid JSON: ${String(error)}`,
          { source: url, httpStatus: response.status },
        );
      }

      if (typeof assessor === "function") {
        const assessed = assessor(payload, {
          source: url,
          httpStatus: response.status,
        });
        if (!assessed || !isTerminalState(assessed.state)) {
          return observation(
            "FAILED",
            "Assessor did not return a terminal public state.",
            { source: url, httpStatus: response.status },
          );
        }
        return assessed;
      }

      return observation("REACHABLE", "JSON source answered.", {
        source: url,
        httpStatus: response.status,
        value: payload,
      });
    } catch (error) {
      if (controller.signal.aborted) {
        return observation("UNAVAILABLE", `No response within ${timeoutMs} ms.`, {
          source: url,
        });
      }
      return observation(
        "UNAVAILABLE",
        `Transport unavailable: ${String(error)}`,
        { source: url },
      );
    }
  })();

  try {
    return await Promise.race([request, timeout]);
  } finally {
    clearTimeout(timer);
  }
}

export function stateClass(state) {
  return `szl-state szl-state--${normalizeState(state).toLowerCase()}`;
}
