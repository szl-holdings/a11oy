# A11oy

  > Governed agentic execution fabric for the SZL Holdings platform.

  A11oy is the execution layer that sits between enterprise data and enterprise decisions. It routes every AI recommendation through policy gates, manages approval queues, executes confirmed actions as auditable workflows, and seals cryptographic proof records.

  ## What A11oy Does

  - Routes every recommended action through Covenant Policy before execution
  - Manages approval queues: who must approve, in what order, under what conditions
  - Executes confirmed actions as audited, durable workflows with failure recovery
  - Writes immutable Proof Chain entries linking signal → recommendation → approval → execution → outcome

  ## Architecture

  ```
  Sense → Structure → Correlate → Explain → Recommend → Approve → Execute
  ```

  The seven-layer fabric runs across every domain pack from a single shared infrastructure.

  ## Status

  **Alpha** — Phase 1 complete, Phase 2 workcell engine in progress. This is a product module within the [SZL Holdings platform monorepo](https://github.com/szl-holdings/szl-holdings-platform).

  ## Tech Stack

  TypeScript · React · Vite · Express · PostgreSQL · Drizzle ORM

  ---

  **[SZL Holdings](https://szlholdings.com)** · [Platform Repository](https://github.com/szl-holdings/szl-holdings-platform) · [inquiries@szlholdings.com](mailto:inquiries@szlholdings.com)

  (c) 2024–2026 SZL Holdings. All rights reserved.
  