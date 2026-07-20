const REGISTRY = Object.freeze([
  ["T01", "required identity", "IMPLEMENTED"],
  ["T02", "actor scope boundary", "IMPLEMENTED"],
  ["T03", "session request rate", "IMPLEMENTED"],
  ["T04", "bounded input", "IMPLEMENTED"],
  ["T05", "egress allowlist", "IMPLEMENTED"],
  ["T06", "receipt chain integrity", "IMPLEMENTED"],
  ["T07", "session deadman", "IMPLEMENTED"],
  ["T08", "bypass language", "IMPLEMENTED"],
  ["T09", "trusted clock skew", "NOT_IMPLEMENTED"],
  ["T10", "receipt sequence gap", "IMPLEMENTED"],
]);

export function evaluateTripwires(context = {}) {
  return REGISTRY.map(([id, name, implementationStatus]) => {
    if (implementationStatus === "NOT_IMPLEMENTED") {
      return { id, name, implementationStatus, evaluationState: "NOT_EVALUATED", evidence: ["required signal is not implemented"] };
    }
    const fired = [];
    if (id === "T01" && !context.actor?.id) fired.push("actor.id absent");
    if (id === "T02" && context.tool && !context.actor?.scopes?.includes(context.tool.capability)) fired.push("capability absent from actor scopes");
    if (id === "T03" && (context.session?.requestCount ?? 0) > 60) fired.push("session request count exceeded 60");
    if (id === "T04" && context.sizeViolation) fired.push("input bound exceeded");
    if (id === "T05" && (context.unapprovedHosts?.length ?? 0) > 0) fired.push("unapproved egress host present");
    if (id === "T06" && context.chainOk === false) fired.push("receipt chain verification failed");
    if (id === "T07" && context.session?.strictMode === false && context.tool) fired.push("tool authorization attempted with strict mode disabled");
    if (id === "T08" && context.bypassDetected) fired.push("bypass language detected");
    if (id === "T10" && context.sequenceGap === true) fired.push("receipt sequence gap detected");
    return {
      id,
      name,
      implementationStatus,
      evaluationState: fired.length ? "FIRED" : "CLEAR",
      evidence: fired.length ? fired : ["evaluated against available request-local evidence"],
    };
  });
}

export function tripwireRegistry() {
  return evaluateTripwires({}).map((item) => ({
    ...item,
    evaluationState: item.implementationStatus === "IMPLEMENTED" ? "NOT_EVALUATED" : item.evaluationState,
    evidence: ["no request supplied"],
  }));
}
