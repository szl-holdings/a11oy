# © 2026 Lutar, Stephen P. — SZL Holdings · Apache-2.0
# Replit Nix environment — SZL Holdings agentic workstation
# Pre-baked toolchain. Cold boot target: ≤ 12s.
{ pkgs }: {
  deps = [
    pkgs.nodejs_20
    pkgs.bun
    pkgs.nodePackages.pnpm
    pkgs.nodePackages.typescript
    pkgs.nodePackages.typescript-language-server
    pkgs.python311
    pkgs.git
    pkgs.gh
    pkgs.curl
    pkgs.jq
    pkgs.ripgrep
  ];
}
