// Generated from spaces/immune/openapi.json. Do not edit by hand.
export const CONTRACT_VERSION = "0.1.0";
export const API_BASE = "/api/immune/v1";
export const OPERATIONS = Object.freeze({
  "getImmuneStatus": {
    "method": "GET",
    "route": "/api/immune/v1/status"
  },
  "inspectImmuneInput": {
    "method": "POST",
    "route": "/api/immune/v1/inspect"
  },
  "authorizeImmuneTool": {
    "method": "POST",
    "route": "/api/immune/v1/tool-authorize"
  },
  "getImmuneReceipt": {
    "method": "GET",
    "route": "/api/immune/v1/receipts/{receiptId}"
  },
  "getImmuneTripwires": {
    "method": "GET",
    "route": "/api/immune/v1/tripwires"
  },
  "getImmuneSessionState": {
    "method": "GET",
    "route": "/api/immune/v1/session/state"
  },
  "updateImmuneSessionState": {
    "method": "POST",
    "route": "/api/immune/v1/session/state"
  }
});
export const DECISIONS = Object.freeze(["ALLOW", "REVIEW", "DENY", "UNAVAILABLE"]);
export const CLASSIFIER_STATES = Object.freeze(["UNAVAILABLE", "THIRD_PARTY_BASELINE", "SZL_TRAINED_CANDIDATE", "QUALIFIED"]);
export const TRIPWIRE_IMPLEMENTATION_STATES = Object.freeze(["IMPLEMENTED", "NOT_IMPLEMENTED"]);
export const TRIPWIRE_EVALUATION_STATES = Object.freeze(["FIRED", "CLEAR", "NOT_EVALUATED"]);
