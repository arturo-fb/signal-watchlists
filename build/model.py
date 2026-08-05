"""
model.py — Turns the ledger into everything the pages need to render.

Responsibilities:
  * load profiles + recommendations
  * fetch live prices and split history once for the whole build (never per page)
  * split-adjust recorded prices so old entries stay comparable to today's quote
  * compute per-ticker P&L for the investor pages
  * compute the daily / weekly / month-to-date return series for the trader pages

Nothing here writes HTML. Keeping the arithmetic in one place means the investor
and trader pages can never disagree about what a given ticker returned.
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
MADRID = ZoneInfo("Europe/Madrid")

# Profiles that get the day-trading treatment: recommendations are judged on the
# day they fire, the page resets daily, and performance is a time series rather
# than an open-position table.
DAY_TRADING_PROFILES = {"P08", "P09"}


# ── Loading ──────────────────────────────────────────────────────────────────

def load_profiles(profiles_path: Path) -> list[dict]:
    data = json.loads(Path(profiles_path).read_text())
    return data["profiles"]


def open_ledger(db_path: Path) -> sqlite3.Connection:
    """
    Open the ledger for reading, tolerating an unclean shutdown.

    Read-only is the right default — a build should never mutate the ledger.
    But if a previous write was interrupted (crash, power loss, a killed
    process) SQLite leaves a hot journal behind, and opening the database then
    requires *write* access so the journal can be rolled back. Under `mode=ro`
    that surfaces as "attempt to write a readonly database", which points at
    permissions and sends you looking in entirely the wrong place.

    So: try read-only, and on failure reopen normally to let SQLite recover.
    """
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone()
    except sqlite3.OperationalError:
        # Read-write, so the rollback can happen. Recovery is the only write.
        conn = sqlite3.connect(str(db_path))
        conn.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone()
        print("[build] recovered an unclean ledger shutdown (rolled back a stale journal)")
    conn.row_factory = sqlite3.Row
    return conn


def load_ledger(db_path: Path) -> tuple[list[dict], dict[str, dict[str, float]]]:
    """(recommendations, {ticker: {date: close}}). Empty if the DB doesn't exist
    or was left mid-write — a file that opens fine but has no tables yet (e.g. an
    interrupted first write) is treated the same as "no data" rather than failing
    the whole build. ledger_sync.py already refuses to publish a ledger in this
    state, but this is a second, independent guard: the build must never go red
    over a transient source-side write hiccup."""
    if not Path(db_path).exists():
        return [], {}
    conn = open_ledger(db_path)
    try:
        try:
            recs = [dict(r) for r in conn.execute(
                "SELECT * FROM recommendations ORDER BY profile_id, ticker, id"
            )]
        except sqlite3.OperationalError as e:
            print(f"[build] ledger has no recommendations table yet ({e}) — treating as empty")
            recs = []
        closes: dict[str, dict[str, float]] = defaultdict(dict)
        try:
            for r in conn.execute("SELECT ticker, date, close FROM daily_closes"):
                if r["close"] is not None:
                    closes[r["ticker"]][r["date"]] = r["close"]
        except sqlite3.OperationalError:
            pass
        return recs, dict(closes)
    finally:
        conn.close()


def load_summaries(db_path: Path) -> dict[tuple[str, str], dict]:
    if not Path(db_path).exists():
        return {}
    conn = open_ledger(db_path)
    try:
        out = {}
        for r in conn.execute("SELECT * FROM thesis_summaries"):
            out[(r["profile_id"], r["ticker"])] = dict(r)
        return out
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()


# ── Market data ──────────────────────────────────────────────────────────────

def fetch_market_data(tickers: list[str], verbose: bool = True) -> tuple[dict, dict]:
    """
    (prices, splits) for every ticker in one pass.

    prices: {TICKER: {price, prev_close, day_chg, high_52w, low_52w} | None}
    splits: {TICKER: [(iso_date, ratio), ...]}

    Failures degrade to None / [] per ticker rather than aborting the build — a
    single delisted or renamed symbol must not take the whole site down.
    """
    if not tickers:
        return {}, {}
    try:
        import yfinance as yf
    except ImportError:
        print("[build] yfinance not installed — pages will render without live prices")
        return {t: None for t in tickers}, {t: [] for t in tickers}

    if verbose:
        print(f"[build] fetching market data for {len(tickers)} tickers …")

    tobj = yf.Tickers(" ".join(tickers))
    prices: dict = {}
    splits: dict = {}

    for sym in tickers:
        # Price
        try:
            t = tobj.tickers[sym]
            fi = t.fast_info
            curr = round(float(fi.last_price), 4)

            # 2-day history gives the same previous close Yahoo shows, without
            # extended-hours contamination.
            prev = None
            try:
                hist = t.history(period="2d", interval="1d")
                if len(hist) >= 2:
                    prev = round(float(hist["Close"].iloc[-2]), 4)
                elif len(hist) == 1:
                    prev = round(float(hist["Close"].iloc[-1]), 4)
            except Exception:
                pass
            if prev is None:
                try:
                    prev = round(float(fi.previous_close), 4)
                except Exception:
                    prev = None

            prices[sym] = {
                "price": curr,
                "prev_close": prev,
                "day_chg": round((curr - prev) / prev * 100, 2) if prev else None,
                "high_52w": _safe_attr(fi, "year_high", "fifty_two_week_high"),
                "low_52w": _safe_attr(fi, "year_low", "fifty_two_week_low"),
            }
        except Exception as exc:
            if verbose:
                print(f"[build]   {sym:<12} price unavailable: {exc}")
            prices[sym] = None

        # Splits
        events = []
        try:
            for idx, val in tobj.tickers[sym].splits.items():
                try:
                    d = idx.date().isoformat()
                except Exception:
                    d = str(idx)[:10]
                v = float(val)
                if v > 0:
                    events.append((d, v))
        except Exception:
            pass
        splits[sym] = events

    return prices, splits


def _safe_attr(fi, *names):
    for n in names:
        try:
            v = getattr(fi, n)
            if v is not None:
                return round(float(v), 2)
        except Exception:
            pass
    return None


def split_factor_since(events, since_date: str | None) -> float:
    """
    Cumulative split ratio for events strictly after `since_date`.

    Divide a price recorded on that date by this factor to put it on today's
    post-split basis. Without it a 4-for-1 split turns a flat position into a
    fake -75%. ISO dates compare correctly as strings.
    """
    if not events or not since_date:
        return 1.0
    cutoff = str(since_date)[:10]
    factor = 1.0
    for d, ratio in events:
        if str(d)[:10] > cutoff:
            factor *= ratio
    return factor


def fetch_closes(pairs: list[tuple[str, str]], verbose: bool = True) -> dict:
    """
    Official close for each (ticker, date) that doesn't have one yet.

    Used by the snapshot job. Only returns dates that are genuinely finished —
    asking for today's close mid-session would freeze an intraday price as if it
    were final, which then silently becomes permanent history.
    """
    if not pairs:
        return {}
    try:
        import yfinance as yf
    except ImportError:
        return {}

    by_ticker: dict[str, list[str]] = defaultdict(list)
    for tk, d in pairs:
        by_ticker[tk].append(d)

    out: dict[tuple[str, str], float] = {}
    for tk, dates in by_ticker.items():
        try:
            start = min(dates)
            end = (datetime.strptime(max(dates), "%Y-%m-%d") + timedelta(days=4)).strftime("%Y-%m-%d")
            hist = yf.Ticker(tk).history(start=start, end=end, interval="1d")
            if hist is None or hist.empty:
                continue
            closes = {}
            for idx, row in hist.iterrows():
                try:
                    closes[idx.date().isoformat()] = float(row["Close"])
                except Exception:
                    continue
            for d in dates:
                if d in closes:
                    out[(tk, d)] = round(closes[d], 4)
                    if verbose:
                        print(f"[snapshot] {tk:<12} {d}  close {closes[d]:.2f}")
        except Exception as exc:
            if verbose:
                print(f"[snapshot] {tk:<12} failed: {exc}")
    return out


# ── Per-profile assembly ─────────────────────────────────────────────────────

def build_profile_view(profile: dict, recs: list[dict], prices: dict,
                       splits: dict) -> dict:
    """
    Collapse one profile's recommendations into per-ticker rows.

    The row is anchored on the FIRST recommendation — entry price, signal date
    and headline P&L are always measured from the first time the profile was
    told about the name. Later recommendations appear in `history` with their
    own P&L, which is what the Recs tooltip and the detail page show.
    """
    by_ticker: dict[str, list[dict]] = defaultdict(list)
    for r in recs:
        by_ticker[r["ticker"]].append(r)

    rows = []
    for ticker, group in by_ticker.items():
        group = sorted(group, key=lambda r: r["id"])
        first = group[0]
        events = splits.get(ticker, [])
        live = prices.get(ticker)
        current = live["price"] if live else None

        history = []
        for r in group:
            raw = r.get("price")
            factor = split_factor_since(events, r["created_date_et"])
            adj = (raw / factor) if (raw and factor and factor != 1.0) else raw
            local_date, local_time = _local_parts(r["created_at"])
            history.append({
                "id": r["id"],
                "date": local_date,
                "time": local_time,
                "date_et": r["created_date_et"],
                "raw_price": raw,
                "price": adj,
                "confidence": (r.get("confidence") or "MEDIUM").upper(),
                "thesis": r.get("thesis") or "",
                "risk": r.get("risk") or "",
                "horizon": r.get("horizon") or "",
                "slot": r.get("slot") or "",
                "pnl": _pct(current, adj),
                "split_adjusted": factor != 1.0,
            })

        entry = history[0]["price"]
        rows.append({
            "ticker": ticker,
            "name": first.get("name") or ticker,
            "sector": first.get("sector") or "",
            "region": first.get("region") or "us",
            "exchange": first.get("exchange") or "",
            "currency": first.get("currency") or "USD",
            "confidence": history[0]["confidence"],
            "entry": entry,
            "signal_date": history[0]["date"],
            "signal_time": history[0]["time"],
            "buy_low": first.get("buy_low"),
            "buy_high": first.get("buy_high"),
            "current": current,
            "day_chg": live["day_chg"] if live else None,
            "high_52w": live["high_52w"] if live else None,
            "low_52w": live["low_52w"] if live else None,
            "pnl_pct": _pct(current, entry),
            "pnl_abs": round(current - entry, 4) if (current and entry) else None,
            "rec_count": len(history),
            "history": history,
            "rec_dates": sorted({h["date"] for h in history}),
            "split_adjusted": split_factor_since(events, history[0]["date_et"]) != 1.0,
        })

    rows.sort(key=lambda r: (r["pnl_pct"] is None, -(r["pnl_pct"] or 0)))

    pnls = [r["pnl_pct"] for r in rows if r["pnl_pct"] is not None]
    return {
        "profile": profile,
        "rows": rows,
        "total": len(rows),
        "total_recs": sum(r["rec_count"] for r in rows),
        "avg_pnl": round(sum(pnls) / len(pnls), 2) if pnls else None,
        "winners": sum(1 for p in pnls if p > 0),
        "losers": sum(1 for p in pnls if p <= 0),
        "measured": len(pnls),
    }


# ── Day-trading performance series ───────────────────────────────────────────

def build_trader_view(profile: dict, recs: list[dict], prices: dict,
                      closes: dict, today_et: str, month: str | None = None) -> dict:
    """
    Day-trading view: today's board plus the month's daily return series.

    Each recommendation's return is measured from its signal price to that same
    day's close — the rule you picked, and the only one that needs no exit logic
    or intraday data. A day's return is the equal-weighted mean across that
    day's recommendations, i.e. what you'd get putting the same stake behind
    every name that fired that day.

    Days still awaiting their close (today, mid-session) are marked pending and
    excluded from the weekly and month-to-date compounding, so a half-finished
    day never quietly drags the month's number around.
    """
    month = month or today_et[:7]

    by_day: dict[str, list[dict]] = defaultdict(list)
    for r in recs:
        by_day[r["created_date_et"]].append(r)

    # Today's board — live, still open
    today_rows = []
    for r in sorted(by_day.get(today_et, []), key=lambda r: r["id"]):
        live = prices.get(r["ticker"])
        current = live["price"] if live else None
        sig = r.get("price")
        _, local_time = _local_parts(r["created_at"])
        close = closes.get(r["ticker"], {}).get(today_et)
        today_rows.append({
            "ticker": r["ticker"],
            "name": r.get("name") or r["ticker"],
            "sector": r.get("sector") or "",
            "currency": r.get("currency") or "USD",
            "confidence": (r.get("confidence") or "MEDIUM").upper(),
            "time": local_time,
            "signal_price": sig,
            "current": current,
            "day_chg": live["day_chg"] if live else None,
            "live_pnl": _pct(current, sig),
            "close": close,
            "close_pnl": _pct(close, sig),
            "buy_low": r.get("buy_low"),
            "buy_high": r.get("buy_high"),
        })

    # Daily series for the selected month
    daily = []
    for day in sorted(d for d in by_day if d.startswith(month)):
        day_recs = by_day[day]
        returns, pending = [], 0
        for r in day_recs:
            sig = r.get("price")
            close = closes.get(r["ticker"], {}).get(day)
            if sig and close:
                returns.append((close - sig) / sig * 100)
            else:
                pending += 1
        daily.append({
            "date": day,
            "weekday": datetime.strptime(day, "%Y-%m-%d").strftime("%a"),
            "n_recs": len(day_recs),
            "n_measured": len(returns),
            "n_pending": pending,
            "pct": round(sum(returns) / len(returns), 2) if returns else None,
            "best": round(max(returns), 2) if returns else None,
            "worst": round(min(returns), 2) if returns else None,
            "winners": sum(1 for r in returns if r > 0),
            "tickers": [r["ticker"] for r in day_recs],
        })

    weeks = _group_into_weeks(daily, month)

    settled = [d["pct"] for d in daily if d["pct"] is not None]
    mtd = _compound(settled)
    all_pending = sum(d["n_pending"] for d in daily)

    return {
        "profile": profile,
        "month": month,
        "month_label": datetime.strptime(month + "-01", "%Y-%m-%d").strftime("%B %Y"),
        "today": today_et,
        "today_rows": today_rows,
        "daily": daily,
        "weeks": weeks,
        "mtd_pct": mtd,
        "mtd_days": len(settled),
        "mtd_green": sum(1 for p in settled if p > 0),
        "mtd_red": sum(1 for p in settled if p <= 0),
        "mtd_best": round(max(settled), 2) if settled else None,
        "mtd_worst": round(min(settled), 2) if settled else None,
        "total_recs": sum(d["n_recs"] for d in daily),
        "pending": all_pending,
    }


def _group_into_weeks(daily: list[dict], month: str) -> list[dict]:
    """
    Split the month's trading days into calendar weeks (Mon–Fri).

    Weeks are keyed by their Monday so a week straddling a month boundary still
    groups correctly; only the days belonging to this month are included, which
    is why week 1 and the last week are often short.
    """
    if not daily:
        return []
    by_week: dict[date, list[dict]] = defaultdict(list)
    for d in daily:
        dt = datetime.strptime(d["date"], "%Y-%m-%d").date()
        by_week[dt - timedelta(days=dt.weekday())].append(d)

    weeks = []
    for i, monday in enumerate(sorted(by_week), start=1):
        days = sorted(by_week[monday], key=lambda x: x["date"])
        settled = [d["pct"] for d in days if d["pct"] is not None]
        friday = monday + timedelta(days=4)
        weeks.append({
            "index": i,
            "label": f"Week {i}",
            "monday": monday.isoformat(),
            "range": f"{monday.strftime('%b %d')} – {friday.strftime('%b %d')}",
            "days": days,
            "pct": _compound(settled),
            "n_days": len(settled),
            "n_recs": sum(d["n_recs"] for d in days),
            "pending": sum(d["n_pending"] for d in days),
            "green": sum(1 for p in settled if p > 0),
            "red": sum(1 for p in settled if p <= 0),
        })
    return weeks


def _compound(pcts: list[float]) -> float | None:
    """
    Chain daily percentage returns.

    Compounding, not summing: the question is "what if I invested in each day's
    recommendations, day after day", and that rolls the previous day's result
    into the next day's stake. Summing would overstate gains and understate
    losses at the tails.
    """
    if not pcts:
        return None
    total = 1.0
    for p in pcts:
        total *= (1 + p / 100)
    return round((total - 1) * 100, 2)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _pct(current, entry) -> float | None:
    if current is None or entry in (None, 0):
        return None
    return round((current - entry) / entry * 100, 2)


def _local_parts(created_at: str) -> tuple[str, str]:
    """UTC timestamp → (local date, local HH:MM) in Madrid, Arturo's home clock."""
    try:
        dt = datetime.strptime(str(created_at)[:19], "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(tzinfo=timezone.utc).astimezone(MADRID)
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
    except Exception:
        s = str(created_at)
        return s[:10], (s[11:16] if len(s) >= 16 else "")


def today_et() -> str:
    return datetime.now(timezone.utc).astimezone(ET).strftime("%Y-%m-%d")


def is_day_trading(profile: dict) -> bool:
    return profile["id"] in DAY_TRADING_PROFILES
