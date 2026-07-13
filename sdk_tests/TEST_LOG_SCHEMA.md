# SDK Rerun Test Log — Schema

Defines how every test in the end-to-end SDK rerun (`00_rerun_plan.md`, topics 1–14) gets
logged in this folder. Distinct from `docs/hydradb_findings_log.md` (confirmed HydraDB
defects, promoted from here once confirmed) — this log captures the **full rerun
experience**: every command run, what happened, and any file changed to make it work.

Scope reminder: this folder is the **SDK / developer-experience** pass (rerunning the build
exactly as a new developer would, via the SDK, against a fresh database — `stock-decoder`,
not the original `stock-market-decoder` tenant). Raw-API backend-breaking tests belong to
the separate test_suite in the other chat, not here.

---

## Logging policy — what actually gets a test entry

The purpose of this pass is to help HydraDB by testing and deliberately trying to break
their system — not to produce a record of our own setup mistakes. Be selective:

**Log it** (gets a full test entry, below):
- Real code errors traceable to HydraDB — SDK behavior, backend/API responses, generated
  outputs — that don't match what a reasonable developer would expect from the docs.
- Documentation/output mismatches — docs say X, the SDK/API does Y.
- Claim-verification tests — see below.

**Don't log it** (fix it, move on, one line in `_RUN_LOG.md` at most):
- Mistakes on our side (typo'd param, wrong env var, forgot to poll status, etc.). If it
  turns out to *not* be our mistake once debugged, it graduates into a real log entry.
- Pure local environment/network friction (missing package, blocked port) — unless it
  reveals something HydraDB's docs should have warned about.

**Claim-verification tests**: where practical, design a small, targeted test around one
specific row in `HydraDB_claims.md` (e.g. "entity resolution merges same-entity mentions
across documents," "`metadata_filters` is exact-match only") and log the result either way —
a confirmed-true claim is as useful to report as a broken one. Keep these tests narrow: one
claim, one small fixture, a few calls — not a sprawling script. We already have a
same-shaped example of this in the original build: `tests/test_knowledge_graph_relations.py`
against the entity-resolution claim (see finding #14).

**Keep tests short.** A test proving a point in 5 lines and 2 API calls is better than one
that re-proves it 20 times. Reserve repeated runs for the reproducibility protocol below,
not general thoroughness.

---

## Pre-check protocol — do this before testing or logging anything

Before running or logging a test for a given step/file, check whether it's already been
handled during the original build:

1. Search `docs/hydradb_findings_log.md` (finding titles + "Where" fields) and
   `docs/CONTEXT_UPDATES.md` for the same endpoint/method/behavior.
2. If a matching finding exists:
   - If it was resolved with a workaround already baked into the current code (e.g. explicit
     `sub_tenant_id`, `max_results=20`, the metadata-shape fix), don't re-log it as new —
     just note **Already Handled** in the test entry, citing the finding #, and confirm
     it still holds under `stock-decoder` in one quick run rather than a full investigation.
   - If it's still open/unresolved, this is a legitimate re-test — proceed normally, and
     cross-reference the original finding.
3. If nothing matches, it's genuinely new — proceed and log fully if it meets the logging
   policy above.

**Confirmed 2026-07-13**: when a previously-fixed finding just keeps working silently during
a step — no reproduction, nothing new — that does **not** get its own `Txx.x` test entry.
Note it in `_RUN_LOG.md` only (one line: "still holding, confirmed on `stock-decoder`," citing
the finding #). A full test entry is reserved for (a) something genuinely new, or (b) an old,
already-handled finding that actually resurfaces/reproduces during the rerun (e.g. T02.1's
deprecation notice) — not for routine passes where the existing fix just keeps working.

---

## File organization

- One file per rerun-plan topic, matching `00_rerun_plan.md`'s numbering: `NN_topic_slug.md`
  (e.g. `02_create_database.md`, `05_ingest_documents.md`).
- Each topic file holds one or more **test entries**, in run order, using the schema below.
- `_index.csv` — one row per test entry, appended as tests are logged, for an at-a-glance
  pass/fail view across the whole rerun without opening every file.
- `_RUN_LOG.md` — chronological, append-only line per command actually run this session
  (including the "don't log" cases above) — the running memory of the rerun, and the raw
  material for the reproducibility README afterward.
- `TEMPLATE.md` — blank copy-paste starting point for a new test entry.

## Test ID convention

`T<topic-number>.<sequence>` — e.g. `T02.1`, `T02.2` for the first and second tests logged
under topic 2 (Create Database). Sequence numbers are per-topic, not global, and never
reused even if a test is later deleted/superseded.

---

## Required fields per test entry

| Field | Purpose | Format / allowed values |
|---|---|---|
| **Test ID** | Unique reference for cross-linking | `T<topic>.<seq>` |
| **Title** | One-line description of what's being tested | Free text |
| **Date/Time** | When it was actually run | ISO date, local time zone noted |
| **Topic** | Which of the 14 rerun-plan topics | Name + number from `00_rerun_plan.md` |
| **Already Handled?** | Result of the pre-check protocol above | "No — new" / "Yes — see finding #N, reconfirming only" |
| **Claim Reference** | If this is a claim-verification test | `HydraDB_claims.md` table + row, or "n/a" |
| **Environment** | Exact conditions, so a failure can be reproduced later | SDK package + version, Python/Node version, OS, target database `stock-decoder`, relevant `.env` keys (names only, never values) |
| **Preconditions** | State assumed true before running this test | e.g. "database created and ready", "all 13 docs ingested and `completed`" |
| **Action / Command** | Exact command or code executed | Verbatim, copy-pasteable |
| **Expected Result** | What should happen per docs or `HydraDB_claims.md` | Include the specific doc page or claims-table row cited |
| **Actual Result** | Full raw output/response | Verbatim (truncate only if very large, say so, and link the full payload under `outputs/` or `sdk_tests/artifacts/`) |
| **Status** | Pass / Fail / Partial / Flaky / Blocked / Skipped | See status definitions below |
| **Error Details** | Exact error code, message, stack trace | Verbatim, not paraphrased |
| **Diagnosis / Root Cause** | Our analysis of *why* | Only logged entries reach this point — by definition, not "our mistake" |
| **Files Changed** | Any project file touched to make this step work | Path + one-line reason per file |
| **Fix / Workaround Applied** | What was actually changed/done to move forward | Free text; "none — logged as-is" is valid |
| **Retest Result** | Outcome after the fix, if re-run | Same Status vocabulary; "not retested" is valid |
| **Reproducibility** | How many times run, and consistency observed | e.g. "3/3 consistent" or "2/8 pass" |
| **Severity** | Only set when Status ≠ Pass | Critical / Significant / Moderate / Minor / Cosmetic |
| **Category** | HydraDB-SDK-bug / HydraDB-Docs-mismatch / Non-issue-as-expected (claim confirmed true) | Our-code-bug / Environment-Setup are not logged here per the policy above — fix and note in `_RUN_LOG.md` only |
| **Cross-references** | Links to related entries elsewhere | `hydradb_findings_log.md` finding #, `HydraDB_claims.md` table row, docs URL, prior Test ID |
| **Follow-up / Open Questions** | Anything unresolved | Free text; "none" is valid |

---

## Status definitions

- **Pass** — matched expected result exactly.
- **Fail** — did not match expected result, confirmed not our own mistake.
- **Partial** — some sub-parts passed, some didn't (e.g. 11/13 documents ingested cleanly).
- **Flaky** — inconsistent across repeated runs (see reproducibility protocol).
- **Blocked** — couldn't run at all (e.g. network restriction, missing credential).
- **Skipped** — intentionally not run this pass, with a stated reason.

## Severity definitions (only when Status ≠ Pass)

- **Critical** — blocks the entire rerun from proceeding, no workaround found.
- **Significant** — real defect/gap with production impact, workaround exists.
- **Moderate** — real defect/gap, low production impact or easily worked around.
- **Minor** — cosmetic, naming, or doc-accuracy issue only.
- **Cosmetic** — no functional effect at all.

## Category definitions

- **HydraDB-SDK-bug** — the SDK itself behaved incorrectly or inconsistently with its own docs.
- **HydraDB-Docs-mismatch** — the SDK behaved consistently, but docs describe it wrong.
- **Non-issue-as-expected** — a deliberate claim-verification test where the claim held true.

(Our-code-bug / Environment-Setup are deliberately not part of this list — see Logging
Policy above.)

## Reproducibility protocol

Per finding #12 in `hydradb_findings_log.md` (`mode="thinking"` reranking is measurably
non-deterministic near the `max_results` boundary), never log a single anomalous run as a
confirmed Fail. If a result looks surprising, inconsistent, or order-sensitive:

1. Re-run the exact same Action/Command at least **3 times** before logging anything but Pass.
2. If any run differs from the others, re-run up to **8 times total** and report the exact
   split (e.g. "2/8 pass") in **Reproducibility** — do not average or round.
3. Log the Status as **Flaky**, not Fail, when the majority of runs pass but not all.
4. Note any parameter that changes the split when varied (e.g. `max_results`, `mode`) under
   **Diagnosis / Root Cause**.
5. This is the one place repetition is warranted — don't over-apply it elsewhere, per the
   "keep tests short" rule above.

---

## `_index.csv` columns

`test_id, topic, title, status, severity, category, date, file_ref`

One row appended per test entry, in the same order they're logged, so the whole rerun's
pass/fail shape is visible without opening every topic file.

---

## Worked example

**Test ID**: T02.1
**Title**: Create `stock-decoder` database with metadata schema via SDK
**Date/Time**: 2026-07-13, 14:02 PDT
**Topic**: 2 — Create database
**Already Handled?**: Yes — finding #2 (deprecation notice on this same call points at
nonexistent fields); reconfirming it still happens on a fresh database, not re-investigating.
**Claim Reference**: n/a
**Environment**: `hydradb-sdk` 2.x (`pip show hydradb-sdk` output pasted here), Python 3.12.4, macOS, target database `stock-decoder`, `.env` keys used: `HYDRA_DB_API_KEY`, `HYDRA_DB_TENANT_ID`
**Preconditions**: No existing `stock-decoder` database (confirmed via dashboard first)
**Action / Command**:
```
python3 scripts/setup_and_ingest_sdk.py --step create
```
**Expected Result**: `202`-style accepted response per `api-reference/v2/endpoint/create-tenant.md`; per `HydraDB_claims.md` Table 2 §2, `client.databases.create()` is the current SDK method
**Actual Result**: *(full response pasted verbatim)*
**Status**: Pass
**Error Details**: n/a
**Diagnosis / Root Cause**: n/a
**Files Changed**: none
**Fix / Workaround Applied**: none — logged as-is
**Retest Result**: not retested (Pass on first run)
**Reproducibility**: 1/1 (creation is not the kind of call worth repeating — logged once)
**Severity**: n/a
**Category**: Non-issue-as-expected
**Cross-references**: `hydradb_findings_log.md` finding #2
**Follow-up / Open Questions**: none
