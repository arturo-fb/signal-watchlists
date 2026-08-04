#!/usr/bin/env python3
"""
build_site.py — Build the whole site into docs/.

    python3 build_site.py                  # full build
    python3 build_site.py --no-prices      # skip yfinance (fast local preview)
    python3 build_site.py --no-summaries   # skip the Anthropic calls

Output layout (GitHub Pages serves docs/ as the site root):

    docs/index.html                    landing page
    docs/<role>/index.html             that channel's watchlist
    docs/<role>/<TICKER>/index.html    ticker detail page

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

from build import render_investor, render_landing, render_ticker, render_trader  # noqa: E402
from build import summarize  # noqa: E402
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

    n_pages = 0
    for profile in profiles:
        pid = profile["id"]
        role = profile["discord_role"]
        view = investor_views[pid]
        trader = is_day_trading(profile)

        if trader:
            # Current month at /<role>/, every earlier month archived at
            # /<role>/m/<YYYY-MM>/ so a month's track record survives the 1st.
            months = sorted({r["created_date_et"][:7] for r in by_profile.get(pid, [])})
            if not months:
                months = [trader_views[pid]["month"]]
            html = render_trader.render(trader_views[pid], updated, is_open, months)

            for m in months[:-1]:
                arch = build_trader_view(profile, by_profile.get(pid, []),
                                         prices, closes, today, month=m)
                write(DOCS / role / "m" / m / "index.html",
                      render_trader.render(arch, updated, is_open, months,
                                           is_archive=True))
                n_pages += 1
        else:
            max_recs = max((r["rec_count"] for r in view["rows"]), default=1)
            html = render_investor.render(view, updated, max_recs)
        write(DOCS / role / "index.html", html)
        n_pages += 1

        for row in view["rows"]:
            slug = row["ticker"].replace(".", "-")
            html = render_ticker.render(
                row, profile, updated,
                summaries.get((pid, row["ticker"])), trader)
            write(DOCS / role / slug / "index.html", html)
            n_pages += 1

        if verbose:
            kind = "trader" if trader else "investor"
            print(f"[build]   /{role}/  {view['total']} tickers · {kind}")

    all_pnls = [r["pnl_pct"] for v in investor_views.values()
                for r in v["rows"] if r["pnl_pct"] is not None]
    totals = {
        "profiles": len(profiles),
        "tickers": sum(v["total"] for v in investor_views.values()),
        "recs": len(recs),
        "avg_pnl": round(sum(all_pnls) / len(all_pnls), 2) if all_pnls else None,
    }

    write(DOCS / "index.html",
          render_landing.render(profiles, card_views, updated, totals, is_day_trading))
    n_pages += 1

    if verbose:
        print(f"[build] wrote {n_pages} pages to {DOCS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
