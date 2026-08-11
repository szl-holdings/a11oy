import { observation } from "./terminal-state.js";

function section(payload, id) {
  return Array.isArray(payload?.sections)
    ? payload.sections.find((item) => item?.id === id) ?? {}
    : {};
}

const SHA_PATTERN = /^[0-9a-f]{40}$/;

function exactShaMatch(left, right) {
  return SHA_PATTERN.test(left ?? "") && left === right;
}

export function assessReadiness(payload, context = {}) {
  const reasons = [];
  const summary = payload?.summary ?? {};
  const reachable = Number(summary.endpoints_reachable ?? 0);
  const total = Number(summary.endpoints_total ?? 0);

  const deployment = section(payload, "deployment");
  const endpoints = Array.isArray(deployment?.endpoints)
    ? deployment.endpoints
    : [];
  const endpointsHealthy =
    endpoints.length === total &&
    endpoints.every(({ liveness }) => {
      const status = Number(liveness?.http_status);
      return (
        liveness?.mode === "live" &&
        liveness?.reachable === true &&
        Number.isInteger(status) &&
        status >= 200 &&
        status < 400
      );
    });

  if (
    payload?.warming === true ||
    payload?.stale === true ||
    !Number.isFinite(total) ||
    total <= 0 ||
    reachable !== total ||
    !endpointsHealthy
  ) {
    reasons.push({ id: "ENDPOINT_PARITY", detail: { reachable, total } });
  }

  const identitySection = section(payload, "identity");
  const identity = identitySection?.raw_version ?? {};
  const parity = section(payload, "parity") ?? {};
  const releaseState = identity.release_state;
  const assetState = identity?.verify?.release_assets_status;
  const buildState = parity?.build?.status;
  const hfState = parity?.hf_space?.status;

  if (
    identitySection?.healthz_mode !== "live" ||
    identitySection?.version_mode !== "live"
  ) {
    reasons.push({
      id: "IDENTITY_NOT_LIVE",
      detail: {
        healthzMode: identitySection?.healthz_mode ?? "UNAVAILABLE",
        versionMode: identitySection?.version_mode ?? "UNAVAILABLE",
      },
    });
  }
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
  const deployedSha = parity?.build?.deployed_git_sha;
  const repositorySha = parity?.build?.repo_head_sha;
  const buildLive =
    parity?.build?.deployed_mode === "live" &&
    parity?.build?.repo_mode === "live" &&
    [undefined, null, "live"].includes(parity?.build?.compare_mode);
  if (
    !["aligned", "current", "equal"].includes(buildState) ||
    !buildLive ||
    !exactShaMatch(deployedSha, repositorySha)
  ) {
    reasons.push({
      id: "DEPLOYED_SOURCE_DRIFT",
      detail: {
        status: buildState ?? "UNAVAILABLE",
        behindBy: parity?.build?.behind_by ?? null,
        deployedSha: deployedSha ?? null,
        repositorySha: repositorySha ?? null,
        deployedMode: parity?.build?.deployed_mode ?? null,
        repositoryMode: parity?.build?.repo_mode ?? null,
      },
    });
  }
  const deployedHfSha = parity?.hf_space?.deployed_hf_space_sha;
  const liveHfSha = parity?.hf_space?.live_hf_space_sha;
  if (
    hfState !== "match" ||
    parity?.hf_space?.mode !== "live" ||
    !exactShaMatch(deployedHfSha, liveHfSha)
  ) {
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
