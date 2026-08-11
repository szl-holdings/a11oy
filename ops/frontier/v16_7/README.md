# Frontier v16.7 protected solo qualification

This directory contains the trusted, protected-base materials used by the
`platform-solo-qualification` check. The workflow reads candidate files as inert
bytes and compares them with the deterministic output of the repair oracle in
this directory. It never checks candidate code out, imports it, executes it,
submits a review, calls the pull-request merge endpoint, or accesses project
secrets.

The protected workflow covers both `pull_request` and `merge_group` events. A
merge-queue run identifies the exact managed PR, requires a successful
qualification on that PR head, and replays the deterministic repair against the
synthetic queue commit built on the current protected base.

Formal A11oy Doctrine v11 remains LOCKED. Frontier v16.7 is a release controller,
not a doctrine revision.

When a merge queue is active, repository policy must require either the
`platform-solo-qualification` status context or this workflow by path. The
merge-group proof binds the exact managed PR file set, rejects overwritten
managed Frontier paths, and rejects changes by other queued PRs to unmanaged
Frontier paths.
