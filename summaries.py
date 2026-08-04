#!/usr/bin/env python3
"""
summaries.py — The interface between the ledger and the summary task.

The `ticker-thesis-summaries` scheduled task uses exactly two commands:

    python3 summaries.py pending            what needs writing (JSON on stdout)
    python3 summaries.py write --file s.json   store the syntheses it wrote

No model is called here. Claude writes the prose in the scheduled task; this
script only decides what is stale and persists the result.

    python3 summaries.py pending --pretty   human-readable, for checking by hand
    python3 summaries.py list               what is already stored
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from build import summarize  # noqa: E402
from build.model import (build_profile_view, is_day_trading,  # noqa: E402
                         load_ledger, load_profiles)

SHARED = HERE.parent
DB = SHARED / "data" / "recommendations.db"
PROFILES = SHARED / "profiles" / "profiles.json"


def build_views(db_path: Path) -> dict:
    """
    Assemble per-profile views without touching the network.

    Prices are irrelevant here — a thesis synthesis is about what was argued,
    not what the position is worth today — so the yfinance call is skipped
    entirely and the task stays fast and offline.
    """
    profiles = load_profiles(PROFILES if PROFILES.exists() else HERE / "data" / "profiles.json")
    recs, _ = load_ledger(db_path)

    by_profile = defaultdict(list)
    for r in recs:
        by_profile[r["profile_id"]].append(r)

    return {
        p["id"]: build_profile_view(p, by_profile.get(p["id"], []), {}, {})
        for p in profiles
    }


def cmd_pending(args) -> int:
    views = build_views(Path(args.db))
    todo = summarize.pending(views, args.db)

    if args.pretty:
        if not todo:
            print("Nothing to summarise — every multi-recommendation ticker is current.")
            return 0
        print(f"{len(todo)} ticker(s) need a synthesis:\n")
        for item in todo:
            print(f"  {item['profile_id']} · {item['ticker']} ({item['name']}) "
                  f"— {item['rec_count']} recommendations — {item['reason']}")
        return 0

    print(json.dumps(todo, indent=2, ensure_ascii=False))
    return 0


def cmd_write(args) -> int:
    """
    Store syntheses. Input is a JSON list:

      [{"profile_id": "P05", "ticker": "NVDA",
        "source_hash": "<from pending>", "summary": "..."}]

    source_hash must be echoed back from `pending` unchanged. It records which
    thesis set the summary was written against; inventing one would mark a
    summary current when it isn't, and it would then never be refreshed.
    """
    payload = json.loads(Path(args.file).read_text())
    if isinstance(payload, dict):
        payload = [payload]

    written, skipped = 0, []
    for item in payload:
        try:
            summary = (item["summary"] or "").strip()
            if not summary:
                skipped.append(f"{item.get('ticker', '?')}: empty summary")
                continue
            summarize.store(args.db, item["profile_id"], item["ticker"],
                            item["source_hash"], summary)
            written += 1
            print(f"[summary] stored {item['profile_id']} {item['ticker']} "
                  f"({len(summary.split())} words)")
        except KeyError as exc:
            skipped.append(f"{item.get('ticker', '?')}: missing field {exc}")
        except Exception as exc:
            skipped.append(f"{item.get('ticker', '?')}: {type(exc).__name__}: {exc}")

    print(f"[summary] {written} stored" + (f", {len(skipped)} skipped" if skipped else ""))
    for s in skipped:
        print(f"  ! {s}")
    return 0 if written or not payload else 1


def cmd_list(args) -> int:
    cached = summarize.load_cached(args.db)
    if not cached:
        print("No summaries stored yet.")
        return 0
    print(f"{len(cached)} stored:\n")
    for (pid, ticker), row in sorted(cached.items()):
        words = len((row.get("summary") or "").split())
        print(f"  {pid} · {ticker:<10} {words:>4} words   {row.get('generated_at', '?')}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DB))
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("pending", help="what needs a synthesis")
    p.add_argument("--pretty", action="store_true")
    p.set_defaults(func=cmd_pending)

    w = sub.add_parser("write", help="store syntheses")
    w.add_argument("--file", required=True)
    w.set_defaults(func=cmd_write)

    l = sub.add_parser("list", help="what is already stored")
    l.set_defaults(func=cmd_list)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
