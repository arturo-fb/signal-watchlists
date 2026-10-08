"""
entry_exit_view.py — Data for the "Entries & exits" tab on each profile page.

Reads the ee_* tables the Discord bot writes (entry_exit/store.py) — read
only, like the rest of the build. If the tables aren't there yet (bot not
restarted since the feature shipped) every profile simply gets an empty tab.

Performance here is ACTIONABLE performance: only positions you marked Sold
count, each trade equal-weighted, measured from the entry price to the exit
price you entered. Nothing is closed automatically at day 5 — an open
position stays open (and unrealized) until you press Sold.
"""

from __future__ import annotations

import json
import sqlite3
import statistics
from pathlib import Path

from . import tradecal

QUIET_FLAG = 4
BENCH_MAIN = {"us": "SPY", "europe": "^STOXX"}
BENCH_LABEL = {"SPY": "S&P 500", "QQQ": "Nasdaq 100", "^STOXX": "STOXX 600"}


def _pct(a, b):
    if a is None or b in (None, 0):
        return None
    return round((a - b) / b * 100, 2)


def load(db_path) -> dict:
    """{'positions': [...], 'slow': [...], 'recs': [(profile, ticker, date_et)]}"""
    out = {"positions": [], "slow": [], "recs": []}
    if not Path(db_path).exists():
        return out
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.execute("SELECT 1 FROM sqlite_master").fetchone()
    except sqlite3.OperationalError:
        conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        out["recs"] = [(r[0], r[1], r[2]) for r in conn.execute(
            "SELECT profile_id, ticker, created_date_et FROM recommendations")]
        try:
            out["positions"] = [dict(r) for r in conn.execute(
                "SELECT * FROM ee_positions ORDER BY signal_at")]
            out["slow"] = [dict(r) for r in conn.execute(
                "SELECT * FROM ee_slow ORDER BY created_at")]
        except sqlite3.OperationalError:
            pass
    finally:
        conn.close()
    return out


def build(profile_id: str, data: dict, prices: dict) -> dict:
    scan_days: dict[str, set] = {"us": set(), "europe": set()}
    last_rec: dict[str, str] = {}
    for pid, tk, d in data["recs"]:
        scan_days[tradecal.market_of(tk)].add(d)
        if pid == profile_id and d > last_rec.get(tk, ""):
            last_rec[tk] = d
    scan_sorted = {m: sorted(v) for m, v in scan_days.items()}

    open_rows, closed_rows, skipped_rows = [], [], []
    for p in data["positions"]:
        if p["profile_id"] != profile_id:
            continue
        mkt = p["market"]
        today = tradecal.today(mkt).isoformat()
        live = (prices.get(p["ticker"]) or {}) if prices else {}
        row = dict(p)
        row["rec_dates_list"] = json.loads(p.get("rec_dates") or "[]")
        row["sector"] = p.get("sector") or "—"
        if p["status"] == "open":
            cur = live.get("price")
            held = max(0, tradecal.trading_days_between(p["entry_date"], today, mkt))
            left = tradecal.trading_days_between(today, p["sell_by"], mkt)
            lr = last_rec.get(p["ticker"])
            days = scan_sorted.get(mkt, [])
            quiet = sum(1 for d in days if lr and lr < d <= today)
            warnings = []
            if p.get("entry_price_source") == "pending_open" and today < p["entry_date"]:
                state = "pending"
            elif today == p["sell_by"]:
                state = "sell_today"
            elif today > p["sell_by"]:
                state = "overdue"
            else:
                state = "holding"
            if state == "sell_today":
                warnings.append(("sell", "Sell today"))
            if state == "overdue":
                warnings.append(("over", f"{-left} day{'s' if -left != 1 else ''} past sell day"))
            if quiet >= QUIET_FLAG:
                warnings.append(("quiet", f"No rec for {quiet} scan days"))
            if cur and p.get("stop_price") and cur <= p["stop_price"]:
                warnings.append(("stop", "Below −15% stop"))
            row.update(current=cur, day_chg=live.get("day_chg"), unreal=_pct(cur, p["entry_price"]),
                       days_held=held, days_left=left, quiet=quiet, last_rec=lr,
                       state=state, warnings=warnings)
            open_rows.append(row)
        elif p["status"] == "sold":
            ret = _pct(p["exit_price"], p["entry_price"])
            be = json.loads(p.get("bench_entry") or "{}")
            bx = json.loads(p.get("bench_exit") or "{}")
            bench = {s: _pct(bx.get(s), be.get(s)) for s in be if bx.get(s) is not None}
            main = BENCH_MAIN[mkt]
            excess = (round(ret - bench[main], 2)
                      if ret is not None and bench.get(main) is not None else None)
            row.update(ret=ret, bench=bench, excess=excess, bench_main=main,
                       days_held=max(0, tradecal.trading_days_between(
                           p["entry_date"], p["exit_date"], mkt)))
            closed_rows.append(row)
        else:
            cur = live.get("price")
            row.update(current=cur, would_be=_pct(cur, p["entry_price"]))
            skipped_rows.append(row)

    slow_rows = []
    for s in data["slow"]:
        if s["profile_id"] != profile_id:
            continue
        r = dict(s)
        r["rec_dates_list"] = json.loads(s.get("rec_dates") or "[]")
        live = (prices.get(s["ticker"]) or {}) if prices else {}
        r["since"] = _pct(live.get("price"), s.get("price"))
        slow_rows.append(r)

    closed_rows.sort(key=lambda r: r["exit_date"] or "", reverse=True)
    open_rows.sort(key=lambda r: (r["sell_by"], r["ticker"]))
    sectors = sorted({r["sector"] for r in open_rows + closed_rows + skipped_rows if r["sector"]})
    return {"open": open_rows, "closed": closed_rows, "skipped": skipped_rows,
            "slow": slow_rows, "sectors": sectors, "stats": stats(closed_rows),
            "has_any": bool(open_rows or closed_rows or skipped_rows or slow_rows)}


def stats(closed: list[dict]) -> dict:
    rets = [r["ret"] for r in closed if r.get("ret") is not None]
    exc = [r["excess"] for r in closed if r.get("excess") is not None]
    days = [r["days_held"] for r in closed if r.get("days_held") is not None]
    return {
        "n": len(rets),
        "avg": round(sum(rets) / len(rets), 2) if rets else None,
        "median": round(statistics.median(rets), 2) if rets else None,
        "win": round(100 * sum(1 for x in rets if x > 0) / len(rets)) if rets else None,
        "avg_days": round(sum(days) / len(days), 1) if days else None,
        "avg_excess": round(sum(exc) / len(exc), 2) if exc else None,
        "best": max(rets) if rets else None,
        "worst": min(rets) if rets else None,
    }
