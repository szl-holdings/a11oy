# Shared alert relay Worker

This Worker restores `ntfy.a11oy.net` as the receiving edge for the shared
receipt-failure channel. It forwards to the real `ntfy.sh` provider while
keeping the managed secret's opaque path at the controlled edge. A deterministic
240-bit SHA-256 prefix converts that path into an ntfy-safe topic; query behavior
is preserved, and the same mapping supports JSON, SSE, raw, and WebSocket
subscriptions through the custom domain.

The relay has no secret binding, does not persist invocation logs, and never
logs the inbound path. Native ntfy request bodies stream through unchanged.
Slack-compatible JSON with a non-empty `text` field is bounded to 64 KiB and
translated to `text/plain`, which keeps the older receipt and health workflows
compatible with the ntfy channel.

Safety properties:

- upstream origin is fixed to `https://ntfy.sh` and redirects are not followed;
- arbitrary legacy paths become one provider-safe, non-reversible topic;
- cookies and Cloudflare forwarding metadata are not sent upstream;
- write requests require a topic path;
- malformed or oversized JSON fails before delivery;
- the real upstream response status and body are preserved;
- transport errors return HTTP 502, never a synthetic 2xx.

Deploy only from a reviewed, merged commit:

```shell
npx wrangler deploy --config ops/alert-relay-worker/wrangler.jsonc
```

After the custom domain is active, run one protected `Alert Channel Watch`
canary. Source tests and CI do not constitute delivery evidence; only the
workflow's bounded POST returning 2xx may record `HEALTHY` and close issue 541.
