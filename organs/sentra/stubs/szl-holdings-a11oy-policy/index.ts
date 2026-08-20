// Local workspace type shim for @szl-holdings/a11oy-policy.
//
// Type-only mirror of the real package's public contract shapes so the web
// app and the a11oy orchestration stub type-check offline without resolving
// the @szl-holdings registry package. Shapes mirror a11oy main
// packages/policy/src/contracts/ (szl-holdings/a11oy @ e1a48fe).
// The cross-repo-handoff contract is exposed at the
// "@szl-holdings/a11oy-policy/contracts/cross-repo-handoff" subpath.

export type { CrossRepoHandoffReceiptInput } from './contracts/cross-repo-handoff';
