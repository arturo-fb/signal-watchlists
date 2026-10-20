#!/usr/bin/env python3
"""
build_site.py — Build the whole site into docs/.

    python3 build_site.py                  # full build
    python3 build_site.py --no-prices      # skip yfinance (fast local preview)
    python3 build_site.py --no-summaries   # skip the Anthropic calls

Output layout (GitHub Pages serves docs/ as the site root). Since 2026-10-20
the site is ONE board — the Signals profile (ID P05) — at the root:

    docs/index.html                    Signals board: hero + Watchlist / Entries & exits tabs
    docs/<TICKER>/index.html           ticker detail page
    docs/<old-role>/...                redirects from the ten-profile layout, so old
                                       links (e.g. /aggressive/, /aggressive/NVDA/) still work

Ticker directories replace "." with "-" so SAN.MC becomes /SAN-MC/ — a dot in a
path segment makes some static hosts treat it as a file extension.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from build import render_investor, render_ticker  # noqa: E402
from build import summarize  # noqa: E402
from build import entry_exit_view  # noqa: E402
from build.model import (build_profile_view, build_trader_view,  # noqa: E402
                         fetch_market_data, is_day_trading, load_ledger,
                         load_profiles, today_et)

MADRID = ZoneInfo("Europe/Madrid")
ET = ZoneInfo("America/New_York")

# The ledger and profiles live in the parent project; the site is a git repo of
# its own nested inside it, so these are one level up.
SHARED = HERE.parent
DB_PATH = SHARED / "data" / "recommendations.db"
PROFILES_PATH = SHARED / "profiles" / "profiles.json"
DOCS = HERE / "docs"

# A local copy travels with the repo so the GitHub Action can build without the
# rest of the project checked out.
LOCAL_DB = HERE / "data" / "recommendations.db"
LOCAL_PROFILES = HERE / "data" / "profiles.json"


def resolve_inputs() -> tuple[Path, Path]:
    """Prefer the live project files; fall back to the copies inside the repo."""
    db = DB_PATH if DB_PATH.exists() else LOCAL_DB
    profiles = PROFILES_PATH if PROFILES_PATH.exists() else LOCAL_PROFILES
    if not profiles.exists():
        raise SystemExit(f"[build] profiles.json not found at {PROFILES_PATH} or {LOCAL_PROFILES}")
    return db, profiles


def market_is_open() -> bool:
    """True when either the US or the European session is trading."""
    now_et = datetime.now(ET)
    now_eu = datetime.now(MADRID)
    if now_et.weekday() > 4:
        return False
    us = (9, 30) <= (now_et.hour, now_et.minute) <= (16, 0)
    eu = 9 <= now_eu.hour < 18
    return us or eu


# discord_role of every profile in the old ten-profile layout.
OLD_ROLES = ["conservative-lt", "dividends", "index-etf", "growth", "aggressive",
             "europe-value", "balanced", "swing", "trader", "thematic"]


def _redirect(target: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"/>
<meta name="robots" content="noindex,nofollow"/>
<meta http-equiv="refresh" content="0; url={target}"/>
<title>Moved — Signals</title>
<script>location.replace({target!r} + location.hash);</script>
</head><body style="background:#0f1117;color:#9aa4b2;font-family:system-ui,sans-serif">
<p>This watchlist moved. <a href="{target}" style="color:#4f8ef7">Go to Signals →</a></p>
</body></html>
"""


def write(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-prices", action="store_true",
                    help="skip yfinance — renders with no live prices")
    ap.add_argument("--no-summaries", action="store_true",
                    help="render without the stored thesis syntheses")
    ap.add_argument("--db", help="override the ledger path")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    verbose = not args.quiet
    db_path, profiles_path = resolve_inputs()
    if args.db:
        db_path = Path(args.db)

    profiles = load_profiles(profiles_path)
    profiles_by_id = {p["id"]: p for p in profiles}
    recs, closes = load_ledger(db_path)
    # Only publish profiles that still exist (old P08/P09 rows stay in the
    # ledger untouched, they just aren't shown).
    recs = [r for r in recs if r["profile_id"] in profiles_by_id]

    if verbose:
        print(f"[build] ledger: {db_path}")
        print(f"[build] {len(recs)} recommendations across "
              f"{len({r['profile_id'] for r in recs})} profiles")

    tickers = sorted({r["ticker"] for r in recs})
    if args.no_prices or not tickers:
        prices = {t: None for t in tickers}
        splits = {t: [] for t in tickers}
    else:
        prices, splits = fetch_market_data(tickers, verbose)

    by_profile: dict[str, list[dict]] = defaultdict(list)
    for r in recs:
        by_profile[r["profile_id"]].append(r)

    # Entries & exits tab — read from the ee_* tables the bot writes. Every
    # position ticker is also a recommended ticker, so `prices` already has it.
    ee_data = entry_exit_view.load(db_path)
    if verbose:
        n_open = sum(1 for p in ee_data["positions"] if p["status"] == "open")
        print(f"[build] entries & exits: {len(ee_data['positions'])} positions "
              f"({n_open} open), {len(ee_data['slow'])} slow ×3")

    now = datetime.now(MADRID)
    updated = now.strftime("%b %d, %Y · %H:%M CET")
    today = today_et()
    is_open = market_is_open()

    # Build every profile's view first: the landing page needs the aggregate
    # numbers, and the summaries need the assembled ticker histories.
    investor_views: dict[str, dict] = {}
    trader_views: dict[str, dict] = {}
    card_views: dict[str, dict] = {}

    for profile in profiles:
        pid = profile["id"]
        p_recs = by_profile.get(pid, [])
        # Every profile gets an investor-shaped view: the trader pages don't
        # render it, but the ticker detail pages and summaries are built from
        # it, so the two page types share one set of numbers.
        view = build_profile_view(profile, p_recs, prices, splits)
        investor_views[pid] = view

        if is_day_trading(profile):
            tv = build_trader_view(profile, p_recs, prices, closes, today)
            trader_views[pid] = tv
            card_views[pid] = tv
        else:
            card_views[pid] = view

    # Thesis syntheses — read only. They are written by the
    # ticker-thesis-summaries scheduled task, never generated here, so the
    # build needs no API key and no network beyond the price fetch.
    summaries: dict = {}
    if not args.no_summaries:
        summaries = summarize.resolve(investor_views, db_path, verbose)

    # Render
    if DOCS.exists():
        shutil.rmtree(DOCS)
    DOCS.mkdir(parents=True)
    (DOCS / ".nojekyll").write_text("")  # stop Pages running Jekyll over docs/

    # One board. profiles.json holds a single profile since 2026-10-20; if it
    # ever holds more, only the first is published.
    profile = profiles[0]
    pid = profile["id"]
    view = investor_views[pid]
    ee = entry_exit_view.build(pid, ee_data, prices)
    st = ee["stats"]
    hero = {
        "avg": st["avg"],            # closed trades only, equal-weight
        "win": st["win"],
        "closed": st["n"],
        "open": len(ee["open"]),
        "recs": view["total_recs"],
        "tickers": view["total"],
    }
    max_recs = max((r["rec_count"] for r in view["rows"]), default=1)
    write(DOCS / "index.html",
          render_investor.render(view, updated, max_recs, ee=ee, hero=hero))
    n_pages = 1

    slugs = []
    for row in view["rows"]:
        slug = row["ticker"].replace(".", "-")
        slugs.append(slug)
        write(DOCS / slug / "index.html",
              render_ticker.render(row, profile, updated,
                                   summaries.get((pid, row["ticker"])), False, depth=1))
        n_pages += 1

    # Old ten-profile URLs → the new layout (hash kept, so /aggressive/#entries
    # lands on the Entries & exits tab).
    for role in OLD_ROLES:
        write(DOCS / role / "index.html", _redirect("../"))
    for slug in slugs:
        write(DOCS / "aggressive" / slug / "index.html", _redirect(f"../../{slug}/"))

    if verbose:
        print(f"[build]   /  Signals board · {view['total']} tickers · "
              f"{st['n']} closed trades · {len(ee['open'])} open")

    if verbose:
        print(f"[build] wrote {n_pages} pages to {DOCS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
