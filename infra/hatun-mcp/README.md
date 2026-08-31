# Removed — single source of truth lives in the canonical repo

The full hatun-mcp (MCP tool surface) sources that used to be vendored here have been removed.
Vendoring a complete copy of an external szl-holdings repo into a11oy created a
duplicate that silently drifted from canonical and re-introduced stale guidance
after the canonical repo was fixed.

**Canonical source: https://github.com/szl-holdings/hatun-mcp**

Do not re-vendor these files into a11oy. Reference the canonical repo above instead.
