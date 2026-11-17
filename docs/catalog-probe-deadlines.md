<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Catalogue probe deadlines

The Frontier Index reads the registered GET callables selected by its existing
route rules. Each catalogue label still comes from a real response. A timeout,
exception, or unavailable worker slot does not manufacture a response label.

Previously, _invoke_route used a new ThreadPoolExecutor context for every probe.
When future.result(timeout=...) raised, leaving that context called
shutdown(wait=True). The caller therefore continued waiting for the endpoint,
despite the stated timeout. STATUS aggregation uses the same catalogue path.

## Resource and lifetime contract

A single lazy pool now serves the process:

- At most four catalogue worker threads exist.
- At most eight probes are admitted across running and queued work.
- Admission never waits for capacity. Saturation returns an unavailable result.
- Each admitted caller waits only for its remaining probe deadline.
- A queued probe is cancelled when its caller times out, when cancellation is
  still possible. Its slot remains accounted for until a worker dequeues it.
- A running probe is not killed or cancelled by a caller timeout. It retains its
  slot until completion, then releases capacity for later requests.
- Repeated requests during saturation create neither new workers nor an
  unbounded queue.

The pool is owned by the process. Importing the module creates no worker threads.
The first admitted probe starts the fixed daemon workers; subsequent requests
reuse them. Individual requests and ASGI startup/shutdown cycles do not tear down
or replace the pool while earlier work may still be running.

Daemon workers prevent a stuck read callable from causing ThreadPoolExecutor's
unbounded interpreter-exit join. This is not forced thread cancellation. Route
implementations retain their own internal resource behavior; the limit above is
the catalogue's worker/admission budget, not a limit on every thread in the app.
The bounded shutdown helper is used by tests after releasing synthetic blocked
work; it reports whether workers actually stopped.

The deadline applies to each selected endpoint probe. It is not a claim that an
entire catalogue traversal, startup sequence, or external dependency completes
within that same deadline.

## Honest diagnostics

An entry may include probe_failures, containing its public endpoint path and a
fixed state such as TIMEOUT, SATURATED, ERROR, or REQUIRED_ARGUMENT_UNAVAILABLE.
No request credentials, private URLs, or response bodies are included.

A TIMEOUT diagnostic distinguishes cancellation before start from work that may
still be running. running_work_cancelled remains false. Delayed completion does
not retroactively promote the timed-out catalogue response.

The existing route selection, synthetic unauthenticated GET request, required
argument handling, label vocabulary, and verbatim label extraction are preserved.
Failed probes continue to yield the existing UNAVAILABLE classification; the
diagnostics explain why no label was observed.

## Regression checks

~~~sh
python -m pytest -q \
  tests/test_frontier_probe_deadline.py \
  tests/test_frontier_index_cache.py \
  tests/test_frontier_index_label_resolution.py
~~~

The tests call the actual probe function with controlled callables. They cover
the caller deadline, retained running slots, immediate saturation, queued
cancellation, recovery after delayed completion, exception cleanup, fixed worker
count across repeated requests, synthetic GET semantics, unchanged label
selection, and locked lazy initialization. Every synthetic blocked worker is
released during fixture cleanup.
