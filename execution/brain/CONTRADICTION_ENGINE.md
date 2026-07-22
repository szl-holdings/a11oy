# Contradiction engine

Status: MODELED

A contradiction is a first-class relationship between claims that share a subject
and predicate but disagree in value, time, scope, or source authority.

The engine normalizes candidate claims, finds comparable statements, calculates
scope and time overlap, records `CONTRADICTS` edges, and assigns a review state.
It never silently deletes the losing claim. Resolution may mark a claim supported,
disputed, superseded, or retracted and must preserve the deciding evidence and actor.

Automatic resolution is limited to deterministic freshness rules such as immutable
revision pins. Policy, scientific, safety, and identity disputes require human review.
