"""
Fetches PTON weekly price history 2020-01-01 through 2024-12-31 via yfinance, and
saves it as a CSV (data/pton_price_history.csv) — the only price source the app
actually reads (see backend/price_data.py). This used to also write a markdown
copy (data/peloton_price_history_weekly.md) for ingestion into HydraDB, but that
was never actually ingested by either setup_and_ingest*.py script and was never
cited by any event, so it was removed as dead output rather than kept around
unused.

Must be run LOCALLY, not in the sandbox — same network restriction we hit with
HydraDB (see CONTEXT_UPDATES.md "Blocker" section): the sandbox's proxy can't
reach pypi.org to install yfinance, and Yahoo Finance's JSON chart API returns
nothing over a plain HTML fetch tool. This mirrors that workaround.

Usage:
    pip install yfinance --break-system-packages   # or just `pip install yfinance`
    python3 scripts/fetch_price_history.py
"""
import sys
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    sys.exit("yfinance not installed. Run: pip install yfinance")

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

TICKER = "PTON"
START = "2020-01-01"
END = "2024-12-31"
INTERVAL = "1wk"  # weekly — enough resolution to see moves around each filing date
                   # without being an unwieldy number of rows. Change to "1mo" for
                   # coarser, or "1d" for daily if the graph testing (task #11)
                   # wants finer granularity.


def main():
    t = yf.Ticker(TICKER)
    hist = t.history(start=START, end=END, interval=INTERVAL)
    if hist.empty:
        sys.exit("yfinance returned no data — check ticker/date range/network.")

    hist = hist.reset_index()
    csv_path = DATA_DIR / "pton_price_history.csv"
    hist.to_csv(csv_path, index=False)
    print(f"Saved {len(hist)} rows to {csv_path}")


if __name__ == "__main__":
    main()
