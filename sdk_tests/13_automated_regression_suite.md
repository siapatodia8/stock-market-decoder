# Topic 13 — Automated Regression Suite

---

**Test ID**: T13.1
**Title**: Re-test of finding #12 — is `mode="thinking"`'s reranking instability near the `max_results` boundary still present on a fresh database?
**Date/Time**: 2026-07-13
**Topic**: 13 — Automated regression suite
**Already Handled?**: Yes — finding #12 already documented this on the original `stock-market-decoder` tenant (2/8 present at `thinking`/`max_results=10`, 8/8 at `max_results=20`, 8/8 at `fast`/`max_results=10`). Re-testing on a fresh database + fresh ingestion to check whether this is systematic or a one-off artifact of the original corpus/timing.
**Claim Reference**: `HydraDB_claims.md` — `max_results` / retrieval ranking stability.
**Environment**: `hydradb-sdk`, Python (venv), macOS, database `stock-decoder`, sub-tenant `default`.
**Preconditions**: All 13 documents ingested and `completed`.
**Action / Command**:
```
python ../tests/test_chunk_retrieval_stability.py
```
Full results saved to `outputs/_chunk_retrieval_stability_results.json`.
**Expected Result**: Per finding #12, expect the correct source document (`peloton_2022-02-05_8k.md`) to be present in only a minority of 8 identical repeated `thinking`/`max_results=10` calls, fully stable (8/8) at `max_results=20`, and fully stable (8/8) under `mode="fast"` at `max_results=10`.
**Actual Result**: Matches exactly. `thinking_max10`: 3/8 present (target relevancy scores swung 0.044–0.885 across the runs where it appeared — a ~20x spread, same as the original finding). `thinking_max20`: 8/8 present, scores tightly banded (~0.8470, varying only in the 5th decimal). `fast_max10`: 8/8 present, with the *identical* relevancy score every single run (`1.4847047328948975`) — even more deterministic than the original run's own fast-mode result.
**Status**: Fail (reproduces finding #12; confirms it as systematic, not a one-off)
**Error Details**: n/a — not an error, a reranking non-determinism gap
**Diagnosis / Root Cause**: Same as finding #12 — `mode="thinking"`'s internal reranking step is unstable near a small `max_results` boundary; the underlying retrieval/embedding step itself is deterministic (confirmed again by `fast` mode's identical score every run).
**Files Changed**: none
**Fix / Workaround Applied**: n/a — this project already works around it via `max_results=20` for `timeline.py`'s per-date queries (unchanged from the original build).
**Retest Result**: n/a
**Reproducibility**: Reproduces cleanly on a completely fresh database/ingestion — strengthens finding #12's credibility as a systematic HydraDB behavior rather than an artifact of the original corpus's specific timing/state.
**Severity**: Significant (unchanged from finding #12)
**Category**: HydraDB-SDK-bug
**Cross-references**: `hydradb_findings_log.md` finding #12
**Follow-up / Open Questions**: none — this confirms finding #12 rather than opening anything new.

---

**Test ID**: T13.2
**Title**: Re-test of finding #12's production-impact scenario — does `mode="thinking"`'s rerank instability still cause a real document to vanish via the actual `hydradb_client.query()`/`synthesis.py` code path (not just the isolated diagnostic script)?
**Date/Time**: 2026-07-13
**Topic**: 13 — Automated regression suite
**Already Handled?**: Partially — finding #12 documented the underlying instability via a dedicated diagnostic script (`test_chunk_retrieval_stability.py`, T13.1 above) and noted it once caused a real wrong-date-attribution bug in `timeline.py`'s output. This script (`test_retrieval_determinism.py`) is a different, closer-to-production check written specifically to chase that same class of bug through the real code path (`hydradb_client.query()` → `synthesis.get_context_snippets()`), for the two dates that showed inconsistent evidence across two prior `timeline.py` runs.
**Claim Reference**: `HydraDB_claims.md` — retrieval determinism / consistent results for identical queries.
**Environment**: `hydradb-sdk`, Python (venv), macOS, database `stock-decoder`, sub-tenant `default`. `hydradb_client.query()`'s default `max_results=10` (unchanged, not overridden by this script) — the same value finding #12 identified as unstable under `mode="thinking"`.
**Preconditions**: All 13 documents ingested and `completed`.
**Action / Command**:
```
python ../tests/test_retrieval_determinism.py
```
Two identical back-to-back `mode="thinking"` calls per date, `metadata_filters={"filing_date": date}` unchanged between calls, for `2021-08-26` and `2022-02-05`. Full results saved to `outputs/_retrieval_determinism_test_results.json`.
**Expected Result**: Uncertain going in (diagnostic, not a fixed-expectation check) — but per finding #12, a real vanishing-document event on at least one of these two specific dates (chosen because they'd shown this exact symptom before) would not be surprising.
**Actual Result**: `2021-08-26`: stable — identical chunk count, source titles, and snippets both runs (`peloton_2021-08-26_8k.md` + `..._shareholder-letter_v2.md` both times). `2022-02-05`: NOT stable — run 1 returned only 1 source (`peloton_2022-02-05_board-pr.md`), run 2 returned 2 sources (`peloton_2022-02-05_8k.md` + `..._board-pr.md`). The document that vanished in run 1, `peloton_2022-02-05_8k.md`, is the filing containing the actual CEO transition announcement (Barry McCarthy appointed CEO/President succeeding John Foley, effective Feb 9 2022) plus 6 more relation-derived snippets (board appointments, Foley's co-founder/former-CEO status, McCarthy's compensation terms, Hisao Kushi's title) — a substantial, narratively-important chunk of evidence entirely missing from run 1, present in run 2, no code or query change between calls.
**Status**: Fail (reproduces finding #12's real production-impact scenario, on a fresh database, via the actual production code path)
**Error Details**: n/a — not an error, a retrieval-instability gap
**Diagnosis / Root Cause**: Same root cause as finding #12 — `mode="thinking"`'s internal reranking is unstable near `max_results=10`, and this client wrapper doesn't override that default. This is the closest re-test yet to what finding #12 described as its real consequence ("two consecutive `timeline.py` runs mislabeled Feb 5–7 disclosures as 'February 8'") — confirms the exact same class of production-visible symptom still occurs today, through the exact code path the app uses, not just the standalone diagnostic's synthetic repeated-call setup.
**Files Changed**: none
**Fix / Workaround Applied**: n/a — `timeline.py` itself already uses `max_results=20` for its own per-date queries (per finding #12's existing workaround); this diagnostic script and `hydradb_client.query()`'s bare default do not, which is exactly why it's still able to catch this. Worth noting for future maintainers: any new code calling `hydradb_client.query()` directly without overriding `max_results` inherits this same risk.
**Retest Result**: n/a
**Reproducibility**: 1/2 tested dates reproduced instability in a single pair of back-to-back calls (no repeated-run averaging attempted here, since this script's design is a single A/B pair per date, not N repeats) — consistent with finding #12's own data showing instability is real but not universal across all filter values.
**Severity**: Significant (unchanged from finding #12 — same reasoning, and this is arguably a stronger demonstration since it's the real code path, not an isolated diagnostic)
**Category**: HydraDB-SDK-bug
**Cross-references**: `hydradb_findings_log.md` finding #12; T13.1 above (same root cause, different test surface)
**Follow-up / Open Questions**: Any current code path that calls `hydradb_client.query()` without explicitly setting `max_results=20` (or higher) is still exposed to this — worth an audit before relying on any single-call retrieval result for anything narratively load-bearing.
