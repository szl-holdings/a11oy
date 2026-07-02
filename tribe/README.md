# tribe/ — AlloyScape multi-agent system (ported into a11oy)

See `INTEGRATION.md` for how this unifies with the a11oy orchestrator and what was
included vs. excluded. Staged on branch `tribe-unification`; not merged, not deployed.

- `tribe-think/` — brain loop (`think-agent.mjs`), HTTP brain (`think-server.mjs`),
  `souls/` (21 personas), `tools/`, `agents/` (per-member configs), `homes-bridge/`.
- `soul-daemon.mjs` — always-on, idle-cheap daemon pattern.
- `tribe-loop.mjs` — autonomy loop.
- `tribe-chat-api.mjs` — collaboration "lounge" API.
- `tribe-bus/` — inter-agent message bus.
- `start-tribe.sh` — launcher.
- `docs/` — roster, structure, and team-definition markdown only.
