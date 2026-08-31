# Shared-source synchronization receipt

- Source repository: `szl-holdings/killinchu`
- Source pull request: `#363`
- Source commit: `437eed3e98d70ebda73ad0552f6e7b647e951e77`
- Bootstrap workflow run: `33444565352`
- Mirrored shared files: `40`
- Drift allowlist changed: `no`
- Branch protection weakened: `no`

The synchronization commit copied and byte-compared the exact 40 paths reported as newly divergent by the fail-closed shared-source drift guard. The one-time bootstrap workflow removed itself after producing the synchronization commit.
