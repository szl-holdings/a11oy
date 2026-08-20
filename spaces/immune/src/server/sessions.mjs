import { validateSessionId } from "./canonical.mjs";

export const SESSION_TTL_MS = 30 * 60 * 1000;
export const SESSION_RATE_WINDOW_MS = 60 * 1000;
const MAX_SESSIONS = 2_048;
const sessions = new Map();

function prune(now = Date.now()) {
  for (const [id, session] of sessions) {
    if (session.expiresAtMs <= now) sessions.delete(id);
  }
  while (sessions.size > MAX_SESSIONS) sessions.delete(sessions.keys().next().value);
}

function publicState(state) {
  return {
    schemaVersion: "szl.immune.session/v1",
    sessionId: state.sessionId,
    strictMode: state.strictMode,
    requestCount: state.requestCount,
    windowStartedAt: new Date(state.windowStartedAtMs).toISOString(),
    windowExpiresAt: new Date(state.windowStartedAtMs + SESSION_RATE_WINDOW_MS).toISOString(),
    expiresAt: new Date(state.expiresAtMs).toISOString(),
  };
}

export function getSession(sessionId, { increment = false, now = Date.now() } = {}) {
  validateSessionId(sessionId);
  prune(now);
  const current = sessions.get(sessionId) ?? {
    sessionId,
    strictMode: true,
    requestCount: 0,
    windowStartedAtMs: now,
    expiresAtMs: now + SESSION_TTL_MS,
  };
  if (now - current.windowStartedAtMs >= SESSION_RATE_WINDOW_MS) {
    current.requestCount = 0;
    current.windowStartedAtMs = now;
  }
  if (increment) current.requestCount += 1;
  current.expiresAtMs = now + SESSION_TTL_MS;
  sessions.set(sessionId, current);
  while (sessions.size > MAX_SESSIONS) sessions.delete(sessions.keys().next().value);
  return current;
}

export function getPublicSession(sessionId) {
  return publicState(getSession(sessionId));
}

export function updateSession(sessionId, patch) {
  const state = getSession(sessionId);
  if (!patch || typeof patch !== "object" || Array.isArray(patch)) throw new TypeError("session patch must be an object");
  for (const key of Object.keys(patch)) {
    if (key !== "strictMode") throw new TypeError(`unsupported session field: ${key}`);
  }
  if (patch.strictMode !== undefined) {
    if (typeof patch.strictMode !== "boolean") throw new TypeError("strictMode must be boolean");
    state.strictMode = patch.strictMode;
  }
  return publicState(state);
}

export function resetSessionsForTest() {
  sessions.clear();
}
