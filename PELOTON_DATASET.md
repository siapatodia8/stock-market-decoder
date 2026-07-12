# Peloton Dataset — Finalized (Phase 1: SEC 8-Ks)

CIK 0001639825. Six 8-K filings (13 individual documents once split into bodies +
exhibits) spanning the full claim → reversal → resolution arc, all independently
verified against EDGAR full-text search and read in full this session.

## 1. Dec 21, 2020 — Precor acquisition
- Accession: `0001193125-20-323253`
- 8-K: https://www.sec.gov/Archives/edgar/data/1639825/000119312520323253/d38384d8k.htm
- Ex-99.1: https://www.sec.gov/Archives/edgar/data/1639825/000119312520323253/d38384dex991.htm
- Role: **claim** — CONFIRMED: $420M acquisition of Precor to build U.S. manufacturing
  capacity, an early sign of pandemic-boom growth confidence (not a generic "boom" filing
  as originally assumed — the actual content is this specific acquisition)

## 2. Aug 26, 2021 — Shareholder Letter
- Accession: `0001639825-21-000254`
- 8-K: https://www.sec.gov/Archives/edgar/data/1639825/000163982521000254/pton-20210826.htm
- Ex-99.1 (shareholder letter): https://www.sec.gov/Archives/edgar/data/1639825/000163982521000254/shareholderletter2021q4.htm
- Role: **the claim** — CONFIRMED: Q4 FY21 letter announces Peloton Output Park factory,
  sets FY2022 guidance at $5.4B revenue / 3.63M subscriptions, confident growth narrative
  right at the inflection point

## 3. Feb 5, 2022 — CEO change (Foley → McCarthy)
- Accession: `0001639825-22-000014`
- 8-K: https://www.sec.gov/Archives/edgar/data/1639825/000163982522000014/pton-20220205.htm
- Ex-99.1: https://www.sec.gov/Archives/edgar/data/1639825/000163982522000014/pressreleaseannouncingboar.htm
- Ex-99.2: https://www.sec.gov/Archives/edgar/data/1639825/000163982522000014/pressreleaseannouncinglead.htm
- Ex-10.1: https://www.sec.gov/Archives/edgar/data/1639825/000163982522000014/peloton-mccarthyemployment.htm
- Role: **reversal marker #1** — leadership change, new find not in original research

## 4. Feb 8, 2022 — Q2 FY22 earnings + restructuring
- Accession: `0001639825-22-000007`
- 8-K: https://www.sec.gov/Archives/edgar/data/1639825/000163982522000007/pton-20220208.htm
- Ex-99.1 (shareholder letter): https://www.sec.gov/Archives/edgar/data/1639825/000163982522000007/shareholderletter2022q2.htm
- Ex-99.2 (restructuring press release): https://www.sec.gov/Archives/edgar/data/1639825/000163982522000007/pressreleaseannouncingrest.htm
- Role: **reversal content** — CONFIRMED: announces $800M annual run-rate cost savings,
  ~2,800 position workforce reduction, winding down in-house manufacturing (POP plant),
  ~$150M CapEx cut. This is the demand-cooling/guidance-cut/restructuring language.

## 5. June 6, 2022 — CFO transition (Woodworth → Coddington)
- Accession: `0001193125-22-168349`
- 8-K: https://www.sec.gov/Archives/edgar/data/1639825/000119312522168349/d100730d8k.htm
- Ex-99.1: https://www.sec.gov/Archives/edgar/data/1639825/000119312522168349/d100730dex991.htm
- Role: **reversal marker #2** — confirms leadership upheaval was systemic, not isolated

## 6. May 20, 2024 — Refinancing
- Accession: `0001193125-24-142849`
- 8-K: https://www.sec.gov/Archives/edgar/data/1639825/000119312524142849/d819214d8k.htm
- Ex-99.1: https://www.sec.gov/Archives/edgar/data/1639825/000119312524142849/d819214dex991.htm
- Role: **resolution** — clean endpoint, $275M convertible notes + $1.0B term loan + $100M revolver

---

## Not yet finalized (next phases)
- Phase 2: yfinance price history (2020–2024)
- Phase 3: Wikipedia — Peloton Interactive page

## Still open before ingestion
- All 6 filings identified and content-verified. Documents 3 and 4 (Feb 2022) confirmed
  via direct fetch — content matches expected roles. No open questions on Phase 1 data.

---

## Ingestion schema (tenant_metadata_schema)

| Field | Type | Flags |
|---|---|---|
| `doc_type` | VARCHAR | `enable_match: true` |
| `narrative_role` | VARCHAR | `enable_match: true` |
| `filing_date` | VARCHAR | `enable_match: true` |
| `doc_summary` | VARCHAR | `enable_dense_embedding: true`, `enable_sparse_embedding: true` |

`narrative_role` values: `claim` / `reversal_marker` / `reversal_content` / `resolution`

## Per-document metadata (13 documents from 6 filings)

All 13 documents fetched and read in full this session. Every summary below is
**CONFIRMED** against actual content, not inferred from filenames/item codes.

| # | id | doc_type | narrative_role | filing_date | doc_summary |
|---|---|---|---|---|---|
| 1 | `peloton_2020-12-21_8k` | 8-K | claim | 2020-12-21 | Peloton announces agreement to acquire Precor for $420M to establish U.S. manufacturing capacity |
| 2 | `peloton_2020-12-21_pr` | press_release | claim | 2020-12-21 | Press release detailing the Precor acquisition — U.S. manufacturing, R&D, and commercial-market expansion plans |
| 3 | `peloton_2021-08-26_8k` | 8-K | claim | 2021-08-26 | 8-K cover filing referencing FY2021 Q4 results and attached shareholder letter |
| 4 | `peloton_2021-08-26_shareholder-letter` | shareholder_letter | claim | 2021-08-26 | Confident Q4 FY21 letter: announces new Peloton Output Park factory, sets aggressive FY2022 guidance ($5.4B revenue, 3.63M subscriptions), "incredibly excited about...global leadership" |
| 5 | `peloton_2022-02-05_8k` | 8-K | reversal_marker | 2022-02-05 | 8-K detailing board changes and CEO transition, Foley → McCarthy, effective Feb 9 2022 |
| 6 | `peloton_2022-02-05_board-pr` | press_release | reversal_marker | 2022-02-05 | Press release announcing new board directors; Barry McCarthy named CEO; John Foley becomes Executive Chair |
| 7 | `peloton_2022-02-08_8k` | 8-K | reversal_content | 2022-02-08 | 8-K cover referencing Q2 FY22 earnings and the restructuring press release |
| 8 | `peloton_2022-02-08_shareholder-letter` | shareholder_letter | reversal_content | 2022-02-08 | Q2 FY22 letter: net loss $439.4M, guidance cut from $5.4B to $3.7-3.8B, Foley announces his own CEO transition directly, restructuring detailed |
| 9 | `peloton_2022-02-08_restructuring-pr` | press_release | reversal_content | 2022-02-08 | $800M annual cost savings, ~2,800 job cuts, winding down in-house manufacturing (POP), $150M capex cut |
| 10 | `peloton_2022-06-06_8k` | 8-K | reversal_marker | 2022-06-06 | 8-K detailing CFO transition, Woodworth → Coddington |
| 11 | `peloton_2022-06-06_pr` | press_release | reversal_marker | 2022-06-06 | Press release announcing Liz Coddington as CFO, succeeding Jill Woodworth |
| 12 | `peloton_2024-05-20_8k` | 8-K | resolution | 2024-05-20 | 8-K announcing global refinancing: $275M convertible notes, $1.0B term loan, $100M revolver, repurchasing ~$800M existing notes |
| 13 | `peloton_2024-05-20_pr` | press_release | resolution | 2024-05-20 | Press release detailing the refinancing terms |
