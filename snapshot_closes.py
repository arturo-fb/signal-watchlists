#!/usr/bin/env python3
"""
snapshot_closes.py — Freeze the official close for every recommendation day.

The day-trading pages score each recommendation from its signal price to that
same day's close. That close has to be captured once and then never change:
recomputing it from a live feed on every build would let a finished day's result
drift, and a month-to-date "+5.1%" that quietly becomes "+4.7%" tomorrow is
worse than useless.

Run after each market close (the workflow does this automatically). Safe to run
repeatedly — it only fills in dates that are still missing, so a re-run after a
failed session costs one API round trip per genuinely missing day.

    python3 snapshot_closes.py
    python3 snapshot_closes.py --db /path/to/recommendations.db --dry-run
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from build.model import fetch_closes  # noqa: E402

ET = ZoneInfo("America/New_York")
SHARED = HERE.parent
DEFAULT_DB = SHARED / "data" / "recommendations.db"
LOCAL_DB = HERE / "data" / "recommendations.db"


def missing(conn) -> list[tuple[str, str]]:
    rows = conn.execute("""
        SELECT DISTINCT r.ticker, r.created_date_et
          FROM recommendations r
          LEFT JOIN daily_closes c
            ON c.ticker = r.ticker AND c.date = r.created_date_et
         WHERE c.close IS NULL
         ORDER BY r.created_date_et""").fetchall()
    return [(r[0], r[1]) for r in rows]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--include-today", action="store_true",
                    help="also snapshot today (only valid after the close)")
    args = ap.parse_args()

    db = Path(args.db) if args.db else (DEFAULT_DB if DEFAULT_DB.exists() else LOCAL_DB)
    if not db.exists():
        print(f"[snapshot] no ledger at {db} — nothing to do")
        return 0

    conn = sqlite3.connect(db)
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS daily_closes (
            ticker TEXT NOT NULL, date TEXT NOT NULL, close REAL,
            captured_at TEXT, PRIMARY KEY (ticker, date))""")

        pairs = missing(conn)
        today = datetime.now(timezone.utc).astimezone(ET).strftime("%Y-%m-%d")

        # Today is skipped unless explicitly asked for. Grabbing a close
        # mid-session would freeze an intraday quote as the day's final result,
        # and because the job never revisits a date it already has, that wrong
        # number would be permanent.
        if not args.include_today:
            skipped = sum(1 for _, d in pairs if d >= today)
            pairs = [(t, d) for t, d in pairs if d < today]
            if skipped:
                print(f"[snapshot] holding back {skipped} entries for {today} "
                      f"(session not finished)")

        if not pairs:
            print("[snapshot] every recommendation day already has a close")
            return 0

        print(f"[snapshot] fetching {len(pairs)} missing closes …")
        if args.dry_run:
            for t, d in pairs:
                print(f"  would fetch {t} {d}")
            return 0

        found = fetch_closes(pairs)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        for (ticker, date), close in found.items():
            conn.execute("""INSERT INTO daily_closes (ticker, date, close, captured_at)
                            VALUES (?,?,?,?)
                            ON CONFLICT(ticker, date) DO UPDATE SET
                              close = excluded.close,
                              captured_at = excluded.captured_at""",
                         (ticker, date, close, now))
        conn.commit()

        unresolved = len(pairs) - len(found)
        print(f"[snapshot] stored {len(found)} closes"
              + (f" · {unresolved} unresolved (holiday, halt, or bad ticker)"
                 if unresolved else ""))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
