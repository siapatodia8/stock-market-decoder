"""
Price statistics over a date window — the non-narrative half of a chat answer.

Volatility, total return, and drawdown are NOT in any filing ("no 8-K says the
stock was 40% volatile"), so they can't come from HydraDB. They're computed
here directly from data/pton_price_history.csv (weekly closes). The chat
pipeline pairs this with HydraDB's narrative evidence for questions like "how
volatile was the stock before the CFO transition".

This module is deliberately window-based (compute_stats(start, end)) rather than
event-based: deciding WHICH window a question implies is the caller's job (it
comes from the orchestrator's scoped filing_dates). This module only does the
arithmetic over whatever window it's given.

Framing rule, baked into describe(): price is reported as nearby CONTEXT, never
as something the events are proven to have caused. Attributing a price move to a
single cause is unreliable even for professionals; the demo does not claim it.
"""
from pathlib import Path
from typing import Optional

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = REPO_ROOT / "data" / "pton_price_history.csv"

_weekly_close = None  # Series indexed by naive date -> weekly Close


def _load():
    """Loads the weekly close series once. Dates are made tz-naive so callers
    can pass plain 'YYYY-MM-DD' strings without timezone bookkeeping."""
    global _weekly_close
    if _weekly_close is not None:
        return
    df = pd.read_csv(CSV_PATH)
    df["Date"] = pd.to_datetime(df["Date"], utc=True).dt.tz_localize(None)
    df = df.sort_values("Date")
    _weekly_close = df.set_index("Date")["Close"]


def derive_price_window(query_type: str, event_ids: list, catalog: list) -> Optional[tuple]:
    """Turns the orchestrator's discrete event scope into a continuous price
    window (start_date, end_date), applying the boundary-neighbor rule.

    The narrative scope excludes the boundary event ("before X" drops X), but a
    volatility window should run right up to X. Since a range scope is a
    contiguous slice of the chronological catalog, the excluded neighbour on
    each open side IS the boundary — so we extend the window to it:
      - "before X"  (prefix slice):  extend END to the next excluded event.
      - "after X"   (suffix slice):  extend START back to the prior excluded event.
      - "between X,Y" (middle slice): extend BOTH sides to the neighbours.
      - whole-story / single / multi / comparative: no boundary — window is just
        min..max of the scoped events' own dates.

    Deterministic: no LLM, no new orchestrator output — the neighbour falls out
    of catalog order. Falls back to plain min..max if a range scope is somehow
    non-contiguous. Returns None if nothing is scoped. Dates are 'YYYY-MM-DD'
    strings, so lexical min/max is chronological."""
    ordered = sorted(catalog, key=lambda e: e["event_id"])
    ids = [e["event_id"] for e in ordered]
    id_to_dates = {e["event_id"]: list(e["dates"]) for e in ordered}

    scoped_ids = [i for i in ids if i in set(event_ids)]
    scoped_dates = sorted(d for i in scoped_ids for d in id_to_dates[i])
    if not scoped_dates:
        return None

    start, end = scoped_dates[0], scoped_dates[-1]

    if query_type == "range":
        idx = [ids.index(i) for i in scoped_ids]
        contiguous = idx == list(range(idx[0], idx[-1] + 1))
        if contiguous:
            first, last = idx[0], idx[-1]
            if first > 0:  # excluded neighbour before -> "after X": extend start back
                start = min([start] + id_to_dates[ids[first - 1]])
            if last < len(ids) - 1:  # excluded neighbour after -> "before X": extend end
                end = max([end] + id_to_dates[ids[last + 1]])

    return (start, end)


def compute_stats(start_date: str, end_date: str) -> Optional[dict]:
    """Computes price stats over [start_date, end_date] inclusive (both
    'YYYY-MM-DD'). Returns None if fewer than 2 weekly closes fall in the
    window (nothing meaningful to measure — e.g. a single-filing window).

    Returns:
        {
          "start_date", "end_date": actual first/last close dates used,
          "weeks": int,
          "start_close", "end_close": float,
          "total_return_pct": float,     # end vs start
          "volatility_pct": float,       # std dev of weekly % returns
          "max_drawdown_pct": float,     # worst peak-to-trough decline (<= 0)
        }
    """
    _load()
    window = _weekly_close[(_weekly_close.index >= pd.Timestamp(start_date))
                           & (_weekly_close.index <= pd.Timestamp(end_date))]
    if len(window) < 2:
        return None

    weekly_returns = window.pct_change().dropna()
    running_max = window.cummax()
    drawdown = (window / running_max - 1.0) * 100

    return {
        "start_date": window.index[0].strftime("%Y-%m-%d"),
        "end_date": window.index[-1].strftime("%Y-%m-%d"),
        "weeks": int(len(window)),
        "start_close": round(float(window.iloc[0]), 2),
        "end_close": round(float(window.iloc[-1]), 2),
        "total_return_pct": round(float((window.iloc[-1] / window.iloc[0] - 1.0) * 100), 1),
        "volatility_pct": round(float(weekly_returns.std() * 100), 1),
        "max_drawdown_pct": round(float(drawdown.min()), 1),
    }


def describe(stats: Optional[dict]) -> Optional[str]:
    """Renders stats into one plain-language sentence for the synthesis context.
    Returns None if stats is None. The wording is deliberately non-causal —
    it states what the price did NEAR the period, not that any event caused it."""
    if not stats:
        return None
    direction = "rose" if stats["total_return_pct"] >= 0 else "fell"
    return (
        f"Price context (not asserted to be caused by these events): over "
        f"{stats['start_date']} to {stats['end_date']} ({stats['weeks']} weeks), "
        f"PTON {direction} {abs(stats['total_return_pct'])}% overall, with a "
        f"weekly-return volatility of {stats['volatility_pct']}% and a worst "
        f"peak-to-trough drawdown of {stats['max_drawdown_pct']}%."
    )


if __name__ == "__main__":
    for label, (s, e) in {
        "lead-up to CFO change (2020-12 .. 2022-02)": ("2020-12-21", "2022-02-08"),
        "full arc (2020-12 .. 2024-05)": ("2020-12-21", "2024-05-20"),
    }.items():
        print(label)
        print(" ", compute_stats(s, e))
        print(" ", describe(compute_stats(s, e)))
        print()
