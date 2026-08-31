# Shared alert relay Worker

This Worker restores `ntfy.a11oy.net` as the receiving edge for the shared
receipt-failure channel. It forwards to the real `ntfy.sh` provider while
preserving the managed secret's opaque path and query.

The relay has no secret binding and never records the topic path. Native ntfy
requests stream through unchanged. Slack-compatible JSON with a non-empty
`text` field is bounded to 64 KiB and translated to `text/plain`, which keeps
the older receipt and health workflows compatible with the ntfy channel.

Safety properties:

- upstream origin is fixed to `https://ntfy.sh` and redirects are not followed;
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
