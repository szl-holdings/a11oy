# Removed — single source of truth lives in the canonical repo

The full szl-build-env (shared build environment) sources that used to be vendored here have been removed.
Vendoring a complete copy of an external szl-holdings repo into a11oy created a
duplicate that silently drifted from canonical and re-introduced stale guidance
after the canonical repo was fixed.

**Canonical source: https://github.com/szl-holdings/szl-build-env**

Do not re-vendor these files into a11oy. Reference the canonical repo above instead.
