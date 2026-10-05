# SZL parent identity: Orbit v2

The founder authorized matching SZL letters and the tilted space ring across the estate.
This projection copies the exact vector admitted by `szl-holdings/szl-brand` PR 142.

## Product favicon contract

`a11oy_landing.html` already declares `/social-preview-v5.svg` as its native SVG favicon.
At the reviewed base `0e63b001630b359f8efaa4cf2d744c08c32b70dc`, indexed references to that
filename are the homepage favicon and `tests/test_discovery_files.py`; the actual social
sharing PNG is separate. The prior SVG was a 1280x640 banner, unsuitable as a square icon.

- `console/szl-orbit.svg` is the new canonical product-local copy.
- `console/social-preview-v5.svg` preserves the existing public favicon URL as an exact
  byte-identical compatibility asset, without JavaScript, redirects or changes to page copy.
- `console/social-preview-v5-banner.svg` preserves every byte of the original banner
  (Git blob `b3ddb97637d6d4a055ac3b449b68223366bdc742`).
- The old discovery test still validates the banner dimensions and message at its preserved
  path. Every other discovery assertion stays unchanged. This is not a repair or waiver of
  unrelated discovery failures.
- `console/szl-orbit.source.json` binds the canonical source commit and SHA-256.

The existing Dockerfile console-directory copy carries these files into the static tree.
The existing protected image/Space publication path remains authoritative; no second writer,
new runtime route, permission change, provider upgrade, DNS change or publication bypass is
introduced. A held runtime remains held after this source change.

## Verification

```bash
python3 tests/test_orbit_identity.py
```

The read-only workflow runs these source checks on matching pull requests, main pushes and
merge groups. It validates the exact admitted hash, native favicon binding, byte-identical
alias, original banner preservation, square dimensions and passive accessible SVG content.
Existing required CI continues unchanged. These checks do not prove browser or deployed state.

After the normal publisher admits the revision, read the deployed build identity and both
`/szl-orbit.svg` and `/social-preview-v5.svg`, comparing their bytes to the source SHA-256.
Inspect 32px browser rendering and the homepage at mobile/desktop widths. A successful
commit or image build alone is not deployment or global rollout evidence.

This scope is the parent identity/favicon. A11oy navigation marks, vertical identities,
account avatars, existing social-preview PNGs, historical evidence and page content remain
unchanged. The legacy KANCHAY bundles retain their own versioned integrity manifests.
