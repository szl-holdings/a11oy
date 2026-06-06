# Contributing to SZL

Thanks for your interest in building on and improving the SZL substrate. Doctrine v11 · Apache-2.0.

## Ground rules (the SZL way)

1. **Honest by default.** Never claim a capability that isn't on disk. If something is partial,
   planned, or simulated, label it. (See how every flagship labels SIMULATED data and the Λ
   Conjecture status.)
2. **Additive, not destructive.** Extend behavior; don't remove or weaken existing routes, proofs,
   or receipts. Mobile/UX layers are `OR` branches over desktop behavior.
3. **Everything is signed.** New governed actions must emit a DSSE receipt that chains into the
   Khipu DAG.
4. **Doctrine numbers are LOCKED.** Do not change `749 / 14 / 163` unless the underlying Lean proof
   corpus changes and is re-verified.

## How to contribute

1. Fork the relevant repo (`platform`, `hatun-mcp`, `developers`, etc.).
2. Create a feature branch: `feat/<short-description>`.
3. Make changes with tests. Run the existing CI gates (CodeQL, Dependabot, lint).
4. **Sign your commits.** We use:
   - Author: your name + email.
   - Trailer: `Co-Authored-By:` for AI-assisted work, per our provenance norms.
5. Open a PR with a clear description and link any related receipts/proofs.

## Reporting security issues

Do **not** open a public issue for vulnerabilities. Follow the coordinated-disclosure process in
`SECURITY.md` (org `.github` repo): email `stephen@szlholdings.com`. See also the
[compliance-posture](https://github.com/szl-holdings/compliance-posture) repo.

## Code of conduct

Be respectful, be rigorous, cite your evidence. Claims ship only when provable.

## License

By contributing you agree your contributions are licensed under **Apache-2.0**.

*Signed Yachay `<yachay@szlholdings.dev>` · Co-Authored-By: Perplexity Computer Agent · Apache-2.0*
