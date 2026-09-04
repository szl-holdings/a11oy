# Cloudflare Windows authorization

This is the supported owner-laptop path for connecting Cloudflare to the existing bounded A11oy production controller. It never asks for a token in chat and never commits one to Git.

## What is installed

`ops/windows/install-cloudflare-tools.ps1` installs:

- `cloudflared` **2026.8.3**, using Cloudflare's official Windows amd64 executable and the release-published SHA-256;
- Wrangler **4.128.0** under `%LOCALAPPDATA%\SZL\Cloudflare\wrangler`;
- no Windows service, tunnel route, DNS record, Worker, token, or GitHub secret during installation.

Both tools are installed for the current Windows user. The installer can optionally open the Wrangler and Cloudflare Tunnel browser authorization flows.

## Run from a cloned `szl-holdings/a11oy` repository

Open PowerShell and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\ops\windows\install-cloudflare-tools.ps1 -AuthorizeWorkers -AuthorizeTunnel
.\ops\windows\authorize-cloudflare-production.ps1
```

The first command installs and verifies the tools. The second opens Cloudflare's token page, accepts the token through a hidden local prompt, validates both SZL zones, stores it as the `CLOUDFLARE_API_TOKEN` secret in the GitHub `production` environment, and dispatches the already-reviewed production workflow.

## Token contract

Create a custom **user API token**, not a Global API Key, with:

| Scope | Permission | Resources |
|---|---|---|
| Account | Workers Scripts — Edit | the SZL account |
| Zone | Workers Routes — Edit | `a-11-oy.com`, `a11oy.net` |
| Zone | DNS — Edit | `a-11-oy.com`, `a11oy.net` |
| Zone | Zone — Read | `a-11-oy.com`, `a11oy.net` |

The current controller calls the user-token verification endpoint, uploads one named Worker, manages exactly two known routes on `a-11-oy.com`, and changes only the `proxied` field on existing apex/www DNS records. It does not create or delete DNS records. If public proof fails after a DNS proxy change, it attempts to restore the prior DNS-only state.

## Authorization boundaries

Interactive authorization must happen on the owner laptop:

- `wrangler login` authorizes local Wrangler through Cloudflare's browser flow;
- `cloudflared tunnel login` authorizes local tunnel administration and stores Cloudflare-managed credentials under the user's profile;
- the custom API token authorizes non-interactive GitHub Actions;
- a protected GitHub `production` environment may still require an explicit run approval.

Do not paste a Cloudflare token into chat, a GitHub issue, a command argument, a repository file, or a PowerShell transcript. The authorization script sends it to `gh secret set` through standard input and writes only a secret-free receipt.

## Tunnel boundary

Installing and authorizing `cloudflared` does not select an origin, tunnel UUID, service account, or Windows-service configuration. The script inventories accessible tunnels but deliberately does not attach `gdw.a-11-oy.com` to an unknown local process. That route should be repaired only after the existing tunnel and intended origin are identified.
