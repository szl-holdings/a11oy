export type ImmuneDecision = {
  verdict: "allow" | "deny";
  reason: string;
  signals: string[];
  lambda: number;
};

const THREATS: { re: RegExp; signal: string }[] = [
  { re: /drop\s+table/i, signal: "threat-signature:DROP TABLE" },
  { re: /rm\s+-rf/i, signal: "threat-signature:rm -rf" },
  { re: /<script/i, signal: "threat-signature:<script" },
  { re: /eval\s*\(/i, signal: "threat-signature:eval(" },
  { re: /\.\.\/|etc\/passwd/i, signal: "threat-signature:path-traversal" },
  { re: /huawei|zte|kaspersky/i, signal: "section889" },
  { re: /weaponize|kill chain|strike people|targeting civilians/i, signal: "willay:strike" },
];

export const IMMUNE_PRESETS = [
  { label: "rm -rf", payload: '{"action":{"cmd":"rm -rf /"}}' },
  { label: "DROP TABLE", payload: '{"query":"DROP TABLE users; --"}' },
  { label: "XSS", payload: '{"html":"<script>alert(1)</script>"}' },
  { label: "path traversal", payload: '{"path":"../../etc/passwd"}' },
  { label: "echo hello (clean)", payload: '{"action":{"cmd":"echo hello"}}' },
  { label: "low Λ axis", payload: '{"axes":{"consent":0,"provenance":0.2}}' },
] as const;

export function evaluateImmune(payload: string): ImmuneDecision {
  const signals = THREATS.filter((t) => t.re.test(payload)).map((t) => t.signal);
  if (/consent["']?\s*:\s*0/.test(payload)) {
    return {
      verdict: "deny",
      reason: "Zero-pinned consent axis. Λ = 0. Fail-closed.",
      signals: ["lambda-zero-pin:consent"],
      lambda: 0,
    };
  }
  if (signals.length) {
    return {
      verdict: "deny",
      reason: `Hukulla deny-by-default. ${signals.join(", ")}. Hunt / isolate / deceive — never strike people.`,
      signals,
      lambda: 0,
    };
  }
  if (payload.length > 4000) {
    return {
      verdict: "deny",
      reason: "Size / DoS guard.",
      signals: ["size-guard"],
      lambda: 0,
    };
  }
  return {
    verdict: "allow",
    reason: "No threat signature. Admission is not a production certificate.",
    signals: [],
    lambda: 0.97,
  };
}
