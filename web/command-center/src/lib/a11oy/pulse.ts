export type Honesty = "MEASURED" | "UNKNOWN" | "UNAVAILABLE";

export type Pulse = {
  id: string;
  label: string;
  url: string;
  honesty: Honesty;
  ms: number;
  status: number | null;
  detail: string;
};

export async function probeEndpoint(id: string, label: string, url: string, timeoutMs = 8000): Promise<Pulse> {
  const t0 = typeof performance !== "undefined" ? performance.now() : Date.now();
  const elapsed = () => Math.round((typeof performance !== "undefined" ? performance.now() : Date.now()) - t0);

  try {
    const res = await fetch(url, {
      method: "GET",
      cache: "no-store",
      mode: "cors",
      signal: AbortSignal.timeout(timeoutMs),
    });
    return {
      id,
      label,
      url,
      honesty: "MEASURED",
      ms: elapsed(),
      status: res.status,
      detail: `HTTP ${res.status}. Status is reachability of this origin, not a production certificate.`,
    };
  } catch {
    try {
      await fetch(url, {
        method: "GET",
        cache: "no-store",
        mode: "no-cors",
        signal: AbortSignal.timeout(timeoutMs),
      });
      return {
        id,
        label,
        url,
        honesty: "UNKNOWN",
        ms: elapsed(),
        status: null,
        detail: "Opaque or CORS-blocked transport. Not LIVE. Not a health stamp.",
      };
    } catch (err) {
      return {
        id,
        label,
        url,
        honesty: "UNAVAILABLE",
        ms: elapsed(),
        status: null,
        detail: err instanceof Error ? err.message : "UNAVAILABLE",
      };
    }
  }
}
