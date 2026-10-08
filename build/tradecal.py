"""
tradecal.py — Trading-day calendar for the entry/exit watch.

Shared by the bot (entry/exit logic) and the site build (countdowns). The site
repo keeps an identical copy at watchlist-site/build/tradecal.py because the
GitHub Action only checks out that repo; tests/test_entry_exit.py fails if the
two drift apart.

Holidays are hard-coded per year. US = NYSE. Europe = the days Xetra and
Euronext are both shut (London has extra bank holidays this ignores; for a
London name that can make a countdown one day early, never late).
Extend the lists before the year runs out — `holidays_known_through()` lets a
test catch it.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
CET = ZoneInfo("Europe/Madrid")

HOLIDAYS = {
    "us": {
        "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
        "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
        "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31",
        "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
    },
    "europe": {
        "2026-01-01", "2026-04-03", "2026-04-06", "2026-05-01", "2026-12-24",
        "2026-12-25", "2026-12-31",
        "2027-01-01", "2027-03-26", "2027-03-29", "2027-12-24", "2027-12-31",
    },
}

# Regular session, in each market's own clock.
SESSION = {
    "us": (ET, time(9, 30), time(16, 0)),
    "europe": (CET, time(9, 0), time(17, 30)),
}


_EU_SUFFIXES = (".MC", ".PA", ".DE", ".F", ".MI", ".AS", ".BR", ".LS", ".L",
                ".SW", ".VI", ".OL", ".ST", ".CO", ".HE", ".IR", ".WA", ".PR",
                ".AT", ".BD", ".LU")


def market_of(ticker: str) -> str:
    """'europe' or 'us', from the Yahoo suffix (the ledger's region column has
    mislabelled rows, so it is never trusted for this)."""
    t = (ticker or "").upper()
    return "europe" if any(t.endswith(s) for s in _EU_SUFFIXES) else "us"


def holidays_known_through() -> str:
    return max(max(v) for v in HOLIDAYS.values())


def _d(x) -> date:
    if isinstance(x, date) and not isinstance(x, datetime):
        return x
    return datetime.strptime(str(x)[:10], "%Y-%m-%d").date()


def is_trading_day(d, region: str) -> bool:
    d = _d(d)
    return d.weekday() < 5 and d.isoformat() not in HOLIDAYS[region]


def next_trading_day(d, region: str) -> date:
    d = _d(d) + timedelta(days=1)
    while not is_trading_day(d, region):
        d += timedelta(days=1)
    return d


def add_trading_days(d, n: int, region: str) -> date:
    """The n-th trading day after d (d itself not counted)."""
    d = _d(d)
    for _ in range(n):
        d = next_trading_day(d, region)
    return d


def trading_days_between(a, b, region: str) -> int:
    """Trading days in (a, b] — 0 when b <= a. Negative when b < a."""
    a, b = _d(a), _d(b)
    if a == b:
        return 0
    sign = 1
    if b < a:
        a, b, sign = b, a, -1
    n, d = 0, a
    while d < b:
        d += timedelta(days=1)
        if is_trading_day(d, region):
            n += 1
    return n * sign


def entry_session(created_at_utc: str, region: str) -> tuple[date, bool]:
    """
    (session date the signal could first be acted on, during_session).

    A signal stamped during the regular session is actionable that day at the
    signal price. One stamped before the open is actionable at that day's open;
    one after the close, on a weekend or a holiday rolls to the next session's
    open. during_session=False means the entry price should be that open, not
    the price recorded with the signal.
    """
    dt = datetime.strptime(str(created_at_utc)[:19], "%Y-%m-%d %H:%M:%S")
    dt = dt.replace(tzinfo=timezone.utc)
    tz, open_t, close_t = SESSION[region]
    local = dt.astimezone(tz)
    day = local.date()
    if is_trading_day(day, region):
        if open_t <= local.time() <= close_t:
            return day, True
        if local.time() < open_t:
            return day, False
    return next_trading_day(day, region), False


def today(region: str) -> date:
    tz = SESSION[region][0]
    return datetime.now(timezone.utc).astimezone(tz).date()


def session_state(region: str, now_utc: datetime | None = None) -> str:
    """'pre', 'open', 'post' or 'closed' (non-trading day) for the market now."""
    now_utc = now_utc or datetime.now(timezone.utc)
    tz, open_t, close_t = SESSION[region]
    local = now_utc.astimezone(tz)
    if not is_trading_day(local.date(), region):
        return "closed"
    t = local.time()
    if t < open_t:
        return "pre"
    if t <= close_t:
        return "open"
    return "post"
