# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11 · Perplexity Computer Agent.
"""Comms connectors — Slack, Microsoft Teams (Graph).

REAL clients against documented endpoints. NO creds → READY + exact secret name.
Slack is WRITABLE (post message) — every write is Λ-gated + DSSE-receipted.

API refs (publicly documented shapes):
  Slack Web API    https://api.slack.com/methods/conversations.list
  MS Teams (Graph) https://learn.microsoft.com/graph/api/team-list
"""
from __future__ import annotations

import os

from ..base import State, Records, http_json
from ..ready import ReadyConnector, WritableReadyConnector
from ..registry import register


# ── Slack (api_key bot token; free workspace) — WRITABLE ──────────────────────
@register
class SlackConnector(WritableReadyConnector):
    id = "slack"
    label = "Slack"
    category = "comms"
    auth_kind = "oauth2"  # bot token via OAuth install
    free_tier = True
    env_vars = ["SZL_SLACK_BOT_TOKEN"]
    _primary_secret = "SZL_SLACK_BOT_TOKEN"
    provider_base = "https://slack.com/api"
    docs_url = "https://api.slack.com/methods/conversations.list"
    schema_preview = ["id", "name", "is_channel", "num_members"]
    _read_path = "conversations.list?limit=10"
    _record_path = "channels"
    _write_path = "chat.postMessage"

    def _auth_header(self):
        tok = os.environ.get("SZL_SLACK_BOT_TOKEN")
        return {"Authorization": f"Bearer {tok}"} if tok else {}

    def read(self, query=None):
        if self._primary_missing():
            return self._ready_records(
                "provide credentials to activate — set SZL_SLACK_BOT_TOKEN "
                "(scopes channels:read,chat:write). Hits conversations.list.")
        url = self._base_url() + "/conversations.list?limit=10"
        st, raw = http_json(url, headers={"Accept": "application/json", **self._auth_header()})
        if st == 200 and isinstance(raw, dict) and raw.get("ok"):
            rows = raw.get("channels", []) or []
            proj = [{k: r.get(k) for k in self.schema_preview if k in r} for r in rows[:10]]
            return Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                           records=proj, source="Slack conversations.list", live=True,
                           note=f"live · {len(rows)} channels", schema_preview=self.schema_preview)
        err = raw.get("error") if isinstance(raw, dict) else st
        return Records(connector_id=self.id, category=self.category, state=State.ERROR,
                       records=[], source=self.provider_base, live=False,
                       note=f"credentials present but Slack returned {err}",
                       schema_preview=self.schema_preview)


# ── Microsoft Teams (Graph; oauth2) ───────────────────────────────────────────
@register
class TeamsConnector(ReadyConnector):
    id = "teams"
    label = "Microsoft Teams"
    category = "comms"
    auth_kind = "oauth2"
    free_tier = True
    env_vars = ["SZL_TEAMS_ACCESS_TOKEN", "SZL_TEAMS_TENANT_ID"]
    _primary_secret = "SZL_TEAMS_ACCESS_TOKEN"
    provider_base = "https://graph.microsoft.com/v1.0"
    docs_url = "https://learn.microsoft.com/graph/api/team-list"
    schema_preview = ["id", "displayName", "description"]
    _read_path = "me/joinedTeams"
    _record_path = "value"

    def _auth_header(self):
        tok = os.environ.get("SZL_TEAMS_ACCESS_TOKEN")
        return {"Authorization": f"Bearer {tok}"} if tok else {}


__all__ = ["SlackConnector", "TeamsConnector"]
