"""
Fetches PTON weekly price history 2020-01-01 through 2024-12-31 via yfinance, and
saves it as both a CSV (data/pton_price_history.csv) and a markdown document
(data/peloton_price_history_weekly.md) formatted for ingestion into HydraDB
alongside the other Knowledge documents.

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

    # Also build a markdown doc, same style as the other Knowledge documents, so
    # it can be ingested the same way (one row per week is too granular for prose;
    # this instead calls out notable moves + a compact table).
    lines = [
        "# Peloton Interactive (PTON) — Weekly Stock Price History (2020-2024)",
        "",
        f"Source: yfinance, ticker {TICKER}, interval={INTERVAL}, "
        f"{START} to {END}. Fetched locally (sandbox network can't reach "
        "Yahoo Finance directly).",
        "",
        "| Date | Open | High | Low | Close | Volume |",
        "|------|------|------|-----|-------|--------|",
    ]
    for _, row in hist.iterrows():
        date_str = row["Date"].strftime("%Y-%m-%d")
        lines.append(
            f"| {date_str} | {row['Open']:.2f} | {row['High']:.2f} | "
            f"{row['Low']:.2f} | {row['Close']:.2f} | {int(row['Volume'])} |"
        )
    md_path = DATA_DIR / "peloton_price_history_weekly.md"
    md_path.write_text("\n".join(lines) + "\n")
    print(f"Saved markdown doc to {md_path}")


if __name__ == "__main__":
    main()
