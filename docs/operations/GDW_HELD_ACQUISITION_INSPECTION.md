# Held acquisition: fixed read-only inspection

The first canonical acquisition at source `d61a838e8763f560ddbd113bfa398f4bb64f2342`, run `37244394814`, attempt `1`, job `111559424879` ended with HELD/exit 2 and a generic diagnostic. Its private bootstrap outcome is unknown. A later public observation showed the same legacy Space revision paused; this does not establish which boundary completed or whether private objects were committed.

This source checkpoint deliberately selects inspection only in the existing canonical workflow. Source admission remains mandatory. The manual preservation/qualification job has a literal false condition, so it cannot create fresh private copies or assert fresh qualification. The existing acquisition job evaluates only after successful current-source admission and a skipped manual job. Its fixed CLI has no artifact, prior-source, path, publisher or run override. The pair configuration step also has a literal false condition. All resume, deployment, runtime proof and secondary publisher gates retain their prerequisite conditions; they cannot proceed with the manual job skipped and inspection failed.

The child has a hard 120-second parent deadline, private temporary directories and suppressed native stdout/stderr. It reads only bounded HEAD, operation history and admission metadata from the existing private dataset, using immutable revisions and the fixed d61 source/run/job and already-observed native artifact hashes. It does not read original databases, bucket objects or candidate bytes, and exposes no provider mutation methods.

The exact report has one of four classifications:

- `ABSENT`: HEAD was absent at the same observed immutable dataset revision. This does not establish that previously uploaded orphan objects are absent.
- `ACKNOWLEDGED`: HEAD, history and admission metadata bind the fixed first attempt. Provider object bytes and runtime health remain unverified.
- `INVALID`: observed metadata fails the fixed contract.
- `UNAVAILABLE`: inspection could not establish either result.

Every classification remains HELD/exit 2 with retry, restore and deployment admission false. `provider_writes_performed: false` describes this read-only inspection, never the uncertain first attempt. A future recovery source change requires review of the actual native result and preserves existing captures and private objects.

The acquisition failure decoder separately preserves only closed source-owned stage/code values and distinguishes entering a boundary from observing its completion. It always reports prior provider effects as not established. Malformed, oversized, noncanonical, unrecognized or privately shaped worker output cannot become public diagnostics. Generic command execution still raises on nonzero exit; only the fixed acquisition parent can inspect bounded exit-2 stdout, and it validates that output before returning any report.
