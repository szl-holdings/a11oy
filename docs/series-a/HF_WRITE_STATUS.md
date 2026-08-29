# Hugging Face write status

**State:** UNAVAILABLE  
**As of:** 2026-08-29  
**Reason:** No Hugging Face connector in the operator session that produced this pack.

Zero-Bandaid: do not mint a fake Hub commit, a synthetic Space, or a fabricated dataset revision.

## What was observed (read-only HTML scrape)

| Item | Value | State |
| --- | --- | --- |
| Org | https://huggingface.co/SZLHOLDINGS | SNAPSHOT |
| Models | 42 | SNAPSHOT |
| Datasets | 28 | SNAPSHOT |
| Spaces | 44 | SNAPSHOT — contradicts pin-five |
| SZL-Khipu-1.5B downloads | 502 | SNAPSHOT |

Canonical receipt lake remains the existing szl-lake dataset. Flight Recorder writes into that path when an ACK is possible. Until then, `lakeSync: PENDING_SYNC`.

## Pin-five remaining work

Relabel or redirect extra Spaces. Do not silently delete. Deletion breaks the receipt/provenance story.

This file is the honest placeholder until an authenticated HF write exists.
