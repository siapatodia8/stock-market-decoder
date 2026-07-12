"""
Reads data/pton_price_history.csv and computes month-over-month PTON price
% change for the timeline grid.
"""
from pathlib import Path
from typing import Optional

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = REPO_ROOT / "data" / "pton_price_history.csv"

_monthly_close = None  # Series: "YYYY-MM" -> last weekly close in that month


def _load():
    global _monthly_close
    if _monthly_close is not None:
        return
    df = pd.read_csv(CSV_PATH)
    df["Date"] = pd.to_datetime(df["Date"], utc=True)
    df = df.sort_values("Date")
    df["month"] = df["Date"].dt.strftime("%Y-%m")
    _monthly_close = df.groupby("month")["Close"].last()


def get_monthly_price_data() -> dict:
    """Returns {"YYYY-MM": {"close": float, "pct_change": float|None}} for
    every month present in the CSV. pct_change is month-end close vs prior
    month-end close; None for the first month (no prior month to compare)."""
    _load()
    pct_change = _monthly_close.pct_change() * 100
    return {
        month: {
            "close": round(float(_monthly_close[month]), 2),
            "pct_change": round(float(pct_change[month]), 2) if pd.notna(pct_change[month]) else None,
        }
        for month in _monthly_close.index
    }


def get_pct_change_for_month(month: str) -> Optional[float]:
    """month is 'YYYY-MM'. Returns None if that month has no CSV data."""
    data = get_monthly_price_data()
    entry = data.get(month)
    return entry["pct_change"] if entry else None


if __name__ == "__main__":
    data = get_monthly_price_data()
    for month in ["2020-12", "2021-08", "2022-02", "2022-06", "2024-05"]:
        print(month, data.get(month))
