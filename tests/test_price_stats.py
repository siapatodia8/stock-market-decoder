"""
Test harness for price_stats.py.

All deterministic — pure CSV arithmetic, no network. Checks that stats over
known windows are sane and that describe() renders with the no-causation
framing. Also checks the too-small-window guard returns None.

Run:
    cd backend && python ../tests/test_price_stats.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import price_stats


# (label, start, end) windows spanning known parts of the story.
WINDOWS = [
    ("lead-up to CFO change", "2020-12-21", "2022-02-08"),
    ("full arc", "2020-12-21", "2024-05-20"),
    ("crash window (boom peak into decline)", "2021-01-01", "2022-06-06"),
]


def sane(stats: dict) -> list:
    """Returns a list of problems; empty means all sane."""
    problems = []
    if stats["weeks"] < 2:
        problems.append("weeks < 2")
    if stats["volatility_pct"] <= 0:
        problems.append("volatility not positive")
    if stats["max_drawdown_pct"] > 0:
        problems.append("max_drawdown should be <= 0")
    if not (stats["start_close"] > 0 and stats["end_close"] > 0):
        problems.append("non-positive close")
    return problems


# Boundary-neighbor window derivation. Catalog mirrors the real 5 events.
CATALOG = [
    {"event_id": "2020-12", "dates": ["2020-12-21"]},
    {"event_id": "2021-08", "dates": ["2021-08-26"]},
    {"event_id": "2022-02", "dates": ["2022-02-05", "2022-02-08"]},
    {"event_id": "2022-06", "dates": ["2022-06-06"]},
    {"event_id": "2024-05", "dates": ["2024-05-20"]},
]

WINDOW_CASES = [
    # (label, query_type, event_ids, expected (start, end))
    ("before X: extend end to boundary (2022-06)", "range",
     ["2020-12", "2021-08", "2022-02"], ("2020-12-21", "2022-06-06")),
    ("after X: extend start back to boundary (2022-02)", "range",
     ["2022-06", "2024-05"], ("2022-02-05", "2024-05-20")),
    ("between: extend both sides", "range",
     ["2021-08", "2022-02"], ("2020-12-21", "2022-06-06")),
    ("whole story: no extension", "range",
     ["2020-12", "2021-08", "2022-02", "2022-06", "2024-05"], ("2020-12-21", "2024-05-20")),
    ("multi: plain min..max, no extension", "multi",
     ["2022-06", "2024-05"], ("2022-06-06", "2024-05-20")),
    ("comparative: plain min..max", "comparative",
     ["2020-12", "2022-02"], ("2020-12-21", "2022-02-08")),
]


def window_checks() -> bool:
    print("=== Boundary-neighbor window derivation (no network) ===")
    ok = True
    for label, qt, ids, expected in WINDOW_CASES:
        got = price_stats.derive_price_window(qt, ids, CATALOG)
        passed = got == expected
        ok = ok and passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}: {got} (expected {expected})")
    print()
    return ok


def main() -> bool:
    all_ok = True

    win_ok = window_checks()
    all_ok = all_ok and win_ok

    print("=== Windowed stats ===")
    for label, start, end in WINDOWS:
        stats = price_stats.compute_stats(start, end)
        if stats is None:
            print(f"  [FAIL] {label}: got None for a multi-week window")
            all_ok = False
            continue
        problems = sane(stats)
        passed = not problems
        all_ok = all_ok and passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
        print(f"       {stats}")
        print(f"       {price_stats.describe(stats)}")
        if problems:
            print(f"       PROBLEMS: {problems}")

    print("\n=== Guard: too-small window returns None ===")
    tiny = price_stats.compute_stats("2020-12-21", "2020-12-21")
    guard_ok = tiny is None
    all_ok = all_ok and guard_ok
    print(f"  [{'PASS' if guard_ok else 'FAIL'}] single-day window -> {tiny}")

    print("\n=== Framing check: describe() is non-causal ===")
    stats = price_stats.compute_stats("2020-12-21", "2022-02-08")
    text = price_stats.describe(stats)
    framing_ok = text is not None and "not asserted to be caused" in text
    all_ok = all_ok and framing_ok
    print(f"  [{'PASS' if framing_ok else 'FAIL'}] framing present in describe()")

    print("\n=== Summary ===")
    print(f"  price_stats: {'PASS' if all_ok else 'FAIL'}")
    return all_ok


if __name__ == "__main__":
    main()
