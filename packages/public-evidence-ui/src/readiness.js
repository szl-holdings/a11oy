import { observation } from "./terminal-state.js";

function section(payload, id) {
  return Array.isArray(payload?.sections)
    ? payload.sections.find((item) => item?.id === id) ?? {}
    : {};
}

export function assessReadiness(payload, context = {}) {
  const reasons = [];
  const summary = payload?.summary ?? {};
  const reachable = Number(summary.endpoints_reachable ?? 0);
  const total = Number(summary.endpoints_total ?? 0);

  if (!Number.isFinite(total) || total <= 0 || reachable !== total) {
    reasons.push({ id: "ENDPOINT_PARITY", detail: { reachable, total } });
  }

  const identity = section(payload, "identity")?.raw_version ?? {};
  const parity = section(payload, "parity") ?? {};
  const releaseState = identity.release_state;
  const assetState = identity?.verify?.release_assets_status;
  const buildState = parity?.build?.status;
  const hfState = parity?.hf_space?.status;

  if (releaseState !== "VERIFIED") {
    reasons.push({
      id: "RELEASE_NOT_VERIFIED",
      detail: releaseState ?? "UNAVAILABLE",
    });
  }
  if (assetState !== "VERIFIED") {
    reasons.push({
      id: "RELEASE_ASSETS_NOT_VERIFIED",
      detail: assetState ?? "UNAVAILABLE",
    });
  }
  if (!["aligned", "current", "equal"].includes(buildState)) {
    reasons.push({
      id: "DEPLOYED_SOURCE_DRIFT",
      detail: {
        status: buildState ?? "UNAVAILABLE",
        behindBy: parity?.build?.behind_by ?? null,
        deployedSha: parity?.build?.deployed_git_sha ?? null,
        repositorySha: parity?.build?.repo_head_sha ?? null,
      },
    });
  }
  if (!["aligned", "current", "equal", "match"].includes(hfState)) {
    reasons.push({
      id: "HF_SERVED_SOURCE_DRIFT",
      detail: parity?.hf_space ?? null,
    });
  }

  if (reasons.length) {
    return observation(
      "BLOCKED",
      `${reasons.length} release/readiness gate(s) remain open.`,
      { ...context, value: payload, reasons },
    );
  }

  return observation(
    "VERIFIED",
    "Runtime, release assets, source parity, and served-source binding are verified.",
    { ...context, value: payload },
  );
}

export function assessHonesty(payload, context = {}) {
  const lambda = payload?.doctrine_lock?.lambda;
  const state = payload?.doctrine_lock?.state;

  if (state !== "LOCKED" || lambda !== "Conjecture 1") {
    return observation(
      "BLOCKED",
      "Doctrine or Lambda status does not match the public truth contract.",
      {
        ...context,
        value: payload,
        reasons: [
          { id: "HONESTY_CONTRACT_DRIFT", detail: { state, lambda } },
        ],
      },
    );
  }

  return observation(
    "VERIFIED",
    "Doctrine lock is reported and Lambda remains Conjecture 1.",
    { ...context, value: payload },
  );
}

export function assessReachability(payload, context = {}) {
  return observation(
    "REACHABLE",
    "Endpoint answered. Reachability does not imply readiness or authorization.",
    { ...context, value: payload },
  );
}
