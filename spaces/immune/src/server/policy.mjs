import { canonicalJson, sha256 } from "./canonical.mjs";

const SECRET_PATTERNS = [
  /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/iu,
  /\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]\s*[^\s,;]{8,}/iu,
  /\b(?:sk|hf)_[A-Za-z0-9_-]{20,}\b/u,
];
const SHELL_PATTERNS = [
  /\b(?:curl|wget)\b[^\n]*(?:\||&&|;)/iu,
  /\b(?:powershell|cmd\.exe|bash|sh)\b\s+(?:-c|-command|\/c)\b/iu,
  /\b(?:rm\s+-rf|format\s+[A-Z]:|Remove-Item\s+.+-Recurse)\b/iu,
];
const BYPASS_PATTERNS = [
  /\bignore (?:all |any )?(?:previous|prior|system) instructions?\b/iu,
  /\b(?:disable|bypass|override) (?:the )?(?:guard|policy|safety|approval|receipt)\b/iu,
  /\byou are now (?:developer|root|system|unrestricted)\b/iu,
];
const ROLE_PATTERNS = [
  /\b(?:system|developer)\s*:\s*you (?:must|will|are)\b/iu,
  /<\/?(?:system|developer|assistant)>/iu,
];
const ENCODED_PATTERNS = [
  /(?:[A-Za-z0-9+/]{80,}={0,2})/u,
  /(?:%[0-9A-Fa-f]{2}){20,}/u,
  /(?:\\u[0-9A-Fa-f]{4}){12,}/u,
];
const URL_PATTERN = /https?:\/\/[^\s<>"']+/giu;

export const POLICY_DOCUMENT = Object.freeze({
  schemaVersion: "szl.immune.policy/v1",
  deterministicFirst: true,
  classifierRequiredForToolAuthorization: true,
  signedReceiptRequiredForToolAuthorization: true,
  decisions: ["ALLOW", "REVIEW", "DENY", "UNAVAILABLE"],
  highestRiskWins: true,
});
export const POLICY_HASH = sha256(canonicalJson(POLICY_DOCUMENT));

function finding(code, severity, detail, channel = "innate") {
  return { code, severity, detail, channel };
}

function allowedHosts() {
  return new Set((process.env.IMMUNE_EGRESS_ALLOWLIST ?? "").split(",").map((host) => host.trim().toLowerCase()).filter(Boolean));
}

export function analyzeInnate(request, session) {
  const findings = [];
  const text = request.content;
  if (!text.trim()) findings.push(finding("EMPTY_CONTENT", "medium", "empty content requires review"));
  if (request.normalization.appliedNfkc) findings.push(finding("UNICODE_NFKC_CHANGED", "medium", "Unicode compatibility normalization changed the input"));
  if (request.normalization.removedZeroWidth) findings.push(finding("ZERO_WIDTH_REMOVED", "high", "zero-width control characters were removed"));
  if (request.source.trust !== "trusted") findings.push(finding("SOURCE_NOT_TRUSTED", "medium", `source trust is ${request.source.trust}`));
  if (["tool_response", "retrieval", "memory"].includes(request.source.kind) && request.source.trust !== "trusted") {
    findings.push(finding("INDIRECT_CONTENT_UNTRUSTED", "high", "external context is not trusted for instructions"));
  }
  if (!request.actor.id) findings.push(finding("ACTOR_ID_MISSING", request.tool ? "high" : "medium", "actor identity is absent"));
  if (SECRET_PATTERNS.some((pattern) => pattern.test(text))) findings.push(finding("SECRET_MATERIAL", "critical", "secret-like material detected; value withheld"));
  if (SHELL_PATTERNS.some((pattern) => pattern.test(text))) findings.push(finding("SHELL_CHAIN", "high", "command-chain syntax detected"));
  const bypassDetected = BYPASS_PATTERNS.some((pattern) => pattern.test(text));
  if (bypassDetected) findings.push(finding("POLICY_BYPASS", "critical", "policy-bypass language detected"));
  if (ROLE_PATTERNS.some((pattern) => pattern.test(text))) findings.push(finding("ROLE_HIJACK", "critical", "role-hijack syntax detected"));
  if (ENCODED_PATTERNS.some((pattern) => pattern.test(text))) findings.push(finding("ENCODED_PAYLOAD", "high", "long encoded payload detected"));

  const allow = allowedHosts();
  const hosts = [];
  for (const raw of text.match(URL_PATTERN) ?? []) {
    try { hosts.push(new URL(raw).hostname.toLowerCase()); } catch { findings.push(finding("MALFORMED_URL", "high", "URL could not be parsed")); }
  }
  const unapprovedHosts = [...new Set(hosts.filter((host) => !allow.has(host)))];
  if (unapprovedHosts.length) findings.push(finding("EGRESS_NOT_ALLOWED", request.tool ? "critical" : "high", `${unapprovedHosts.length} host(s) are outside the egress allowlist`));

  if (request.tool) {
    if (!request.actor.scopes.includes(request.tool.capability)) findings.push(finding("CAPABILITY_NOT_GRANTED", "critical", "requested tool capability is absent from actor scopes"));
    if (!session.strictMode) findings.push(finding("STRICT_MODE_DISABLED", "critical", "tool authorization requires strict mode"));
  }
  if (session.requestCount > 60) findings.push(finding("SESSION_RATE_EXCEEDED", "high", "session request count exceeded the bounded window"));

  return { findings, unapprovedHosts, bypassDetected };
}

export function decide({ findings, classifier, toolRequested, signerAvailable }) {
  const severities = new Set(findings.map((item) => item.severity));
  if (severities.has("critical")) return { decision: "DENY", reasons: ["deterministic_critical_finding"] };
  if (classifier.evaluated && classifier.label === "INJECTION") return { decision: "DENY", reasons: ["classifier_injection"] };
  if (toolRequested) {
    if (classifier.state !== "QUALIFIED" || !classifier.evaluated) return { decision: "UNAVAILABLE", reasons: ["qualified_classifier_required"] };
    if (!signerAvailable) return { decision: "UNAVAILABLE", reasons: ["receipt_signer_required"] };
    if (severities.has("high") || severities.has("medium")) return { decision: "DENY", reasons: ["tool_authorization_findings"] };
    return { decision: "ALLOW", reasons: ["deterministic_clear", "qualified_classifier_clear", "receipt_signer_ready"] };
  }
  if (severities.has("high")) return { decision: "DENY", reasons: ["deterministic_high_finding"] };
  if (severities.has("medium")) return { decision: "REVIEW", reasons: ["deterministic_review_finding"] };
  if (!classifier.evaluated) return { decision: "REVIEW", reasons: ["classifier_unavailable"] };
  return classifier.label === "SAFE"
    ? { decision: "ALLOW", reasons: ["deterministic_clear", "classifier_clear"] }
    : { decision: "DENY", reasons: ["classifier_injection"] };
}
