# Stock Market Decoder - Limitations & Future Considerations

What this build doesn't do today, and where it could grow next. HydraDB-specific gaps and behavior are covered separately under Testing & Findings - this doc is about our own data scope and system design choices.

---

## Data Limitations

- **One company only.** The dataset covers Peloton exclusively - nothing about cross-company patterns or sector-wide behavior can be tested or shown.
- **Five key events, not a complete timeline.** Even for Peloton, the dataset covers 5 curated inflection points (2020-2024), not every disclosure the company has ever made - the story between those points is intentionally not filled in.

## Design & System Choices

- **Company is hardcoded, not user-selectable.** The company name, industry, and document set are fixed constants in the code - using this for another company today means editing source, not choosing one in the UI.
- **No user accounts or session persistence.** Every session starts fresh - no saved chat history, and no adaptation to a returning user's level of financial knowledge.
- **Monthly granularity.** Price movements and events are aligned at the month level, not daily or intraday, which can blur precise timing between a disclosure and the market's reaction to it.

---

## Future Considerations

- **Personalization via HydraDB Memory.** This build only uses HydraDB's Knowledge layer for filings; Memory (built for behavioral/preference signals, not documents) was intentionally out of scope for a 3-day build. A learning platform is a natural fit for it - tracking a user's learning level or style across sessions and adapting explanations accordingly.
- **Expand the dataset.** More events per company, and more companies, addressing both data limitations above.
- **Let users choose their own company.** Type a ticker or company name, route to SEC filings and yfinance, extract, clean, and load into HydraDB - the same ingestion pipeline this build already has, made dynamic instead of hardcoded to one company.
- **Cross-company comparison.** Once multiple companies are ingested, compare how similar event types played out across companies (e.g. leadership transitions, restructurings) - this leans directly on HydraDB's knowledge graph, which already surfaced cross-entity relationships (like a person's prior company) within a single company's filings in this build.
- **Sector-level rollups.** Aggregate multiple companies in the same sector to explain sector-wide movements, extending the core "how markets and stocks move together" mission from one company to a whole industry.
- **A comprehension layer.** Light quizzes or recall checks tied to each event, reinforcing the Duolingo-style learning framing from the Overview with active practice, not just reading - and personalizing over time via the same Memory-based tracking above.
- **Continuous ingestion.** Instead of a one-time historical batch load, watch for new filings as they're published and auto-ingest them, keeping the dashboard current instead of historical-only.

---
