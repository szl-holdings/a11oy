<!-- VENDORED FROM szl-holdings/platform@c11291e09702c86f3f8995fffcae6167155c7240 — .agents/skills/pre-flight-thinking/SKILL.md -->
<!-- DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync. -->
---
name: pre-flight-thinking
description: Structured thinking checklist to run before writing or modifying code. Use this before any non-trivial implementation to force problem restatement, assumption listing, smallest-change identification, and failure-mode enumeration. Adapted from the Superpowers "force structured thinking before coding" pattern.
---

# Pre-Flight Thinking

Run this checklist mentally (or explicitly in a scratchpad) before writing any code for a non-trivial task. It prevents common mistakes: solving the wrong problem, over-engineering, missing failure modes, and making irreversible changes when reversible ones exist.

## The Four-Step Checklist

### 1. Restate the Problem
In your own words, write one sentence that captures what needs to change and why. If you cannot do this clearly, stop and re-read the task.

> Example: "Add pagination to the audit log table so admins can browse beyond the first 50 rows."

### 2. List Assumptions
Enumerate what you are assuming to be true. Flag any assumption you have not verified.

- What does the existing code do today?
- What schema, API contract, or component interface are you depending on?
- Which other packages or artifacts consume this code?
- Is this behavior tested anywhere?

### 3. Identify the Smallest Reversible Change
Before reaching for a full rewrite, ask: what is the minimal edit that delivers the required outcome? Prefer additive changes (new functions, new props, new routes) over mutations of shared contracts. If you must mutate a shared interface, document the migration path.

- Can this be done in one file? In one function?
- Is there a feature flag or optional prop that limits blast radius?
- Will a revert be a one-line undo, or a multi-file rollback?

### 4. Name the Failure Modes
List at least two ways this change could break things at runtime.

- What happens if the data is empty, null, or malformed?
- What happens under concurrent access or rapid re-renders?
- What happens if a downstream consumer has not been updated yet?

## When to Skip
Skip this skill for trivial edits: fixing a typo, updating a string literal, or making a purely cosmetic CSS change.

## Integration with Other Skills
Reference this skill at the start of `typescript-refactor`, `monorepo-impact-analysis`, and `api-contract-review` tasks. It composes naturally as a preamble to those workflows.
