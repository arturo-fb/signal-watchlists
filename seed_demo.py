#!/usr/bin/env python3
"""
seed_demo.py — Fill a throwaway ledger with realistic data.

Used to exercise the site generator without waiting for real recommendations to
accumulate. Writes to a separate DB file; it will refuse to touch the real one.

    python3 seed_demo.py --db /tmp/demo.db
    python3 build_site.py --db /tmp/demo.db --no-prices
"""

from __future__ import annotations

import argparse
import random
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ledger.db import SCHEMA  # noqa: E402

US = [
    ("NVDA", "NVIDIA Corp", "Technology", 178.0),
    ("AVGO", "Broadcom Inc", "Technology", 455.0),
    ("DAVE", "Dave Inc", "Technology", 283.0),
    ("SEZL", "Sezzle Inc", "Financial Services", 117.5),
    ("ENVA", "Enova International", "Financial Services", 170.6),
    ("CXW", "CoreCivic Inc", "Industrials", 24.2),
    ("PANW", "Palo Alto Networks", "Technology", 288.7),
    ("VCTR", "Victory Capital", "Financial Services", 88.9),
    ("AAMI", "Acadian Asset Mgmt", "Financial Services", 77.1),
    ("KO", "Coca-Cola Co", "Consumer Staples", 62.4),
    ("JNJ", "Johnson & Johnson", "Healthcare", 158.2),
    ("NEE", "NextEra Energy", "Utilities", 71.9),
    ("VOO", "Vanguard S&P 500 ETF", "ETF", 512.0),
]
EU = [
    ("SAN.MC", "Banco Santander", "Financials", 6.12, "EUR", "Madrid"),
    ("IBE.MC", "Iberdrola", "Utilities", 13.45, "EUR", "Madrid"),
    ("MC.PA", "LVMH", "Consumer Cyclical", 612.0, "EUR", "Paris"),
    ("SAP.DE", "SAP SE", "Technology", 218.4, "EUR", "Frankfurt"),
    ("ENI.MI", "Eni SpA", "Energy", 14.8, "EUR", "Milan"),
    ("SHEL.L", "Shell plc", "Energy", 2740.0, "GBX", "London"),
]

THESIS = """**What it does:** {name} operates in {sector}, and the setup here is \
about {angle}.

**Why now:** {catalyst} The most recent quarter came in ahead of consensus, and \
management guided the next two quarters higher — the kind of revision that \
tends to precede estimate upgrades rather than follow them.

**Entry idea:** Accumulate between {low} and {high}. Above {high} you are paying \
up for momentum; below {low} the technical structure is broken and the thesis \
needs revisiting.

**Time horizon:** {horizon}."""

ANGLES = ["operating leverage finally showing up in margins",
          "a balance sheet that is far cleaner than the multiple implies",
          "share gains in a market everyone had written off as mature",
          "a product cycle that is only two quarters into a four-quarter ramp",
          "pricing power that survived the last two cost shocks"]
CATALYSTS = ["A large contract win landed last week and is not yet in numbers.",
             "Insider buying picked up materially over the last month.",
             "The sector rotated hard this week and this name lagged the move.",
             "A regulatory overhang cleared, removing the main bear argument.",
             "Volume broke out of a six-month base on three times average."]
RISKS = ["Valuation leaves no room for a miss; a soft quarter takes 20% off.",
         "Customer concentration is high — the top three are most of revenue.",
         "Rate-sensitive; a hawkish surprise compresses the multiple fast.",
         "Execution risk on the integration is the main thing to watch.",
         "Thin liquidity means slippage on the way out if sentiment turns."]

PROFILE_UNIVERSE = {
    "P01": ["KO", "JNJ", "NEE", "IBE.MC"],
    "P02": ["SAN.MC", "ENI.MI", "SHEL.L", "NEE", "KO"],
    "P03": ["VOO"],
    "P04": ["NVDA", "PANW", "SAP.DE", "MC.PA", "AVGO"],
    "P05": ["NVDA", "DAVE", "SEZL", "ENVA", "AVGO", "CXW", "VCTR"],
    "P06": ["SAN.MC", "IBE.MC", "MC.PA", "SAP.DE", "ENI.MI"],
    "P07": ["NVDA", "SAP.DE", "KO", "MC.PA", "VOO"],
    "P08": ["DAVE", "SEZL", "ENVA", "CXW", "PANW", "AAMI", "VCTR", "NVDA"],
    "P09": ["DAVE", "SEZL", "CXW", "AAMI", "VCTR", "ENVA", "NVDA", "AVGO"],
    "P10": ["NVDA", "AVGO", "NEE", "SAP.DE", "PANW"],
}

META = {}
for t, n, s, p in US:
    META[t] = {"name": n, "sector": s, "price": p, "currency": "USD",
               "region": "us", "exchange": "Nasdaq"}
for t, n, s, p, c, e in EU:
    META[t] = {"name": n, "sector": s, "price": p, "currency": c,
               "region": "europe", "exchange": e}


def trading_days(back: int) -> list[datetime]:
    out, d = [], datetime.now(timezone.utc)
    while len(out) < back:
        if d.weekday() < 5:
            out.append(d)
        d -= timedelta(days=1)
    return sorted(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--days", type=int, default=24)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    db = Path(args.db)
    if db.name == "recommendations.db" and "data" in db.parts and "tmp" not in str(db):
        raise SystemExit("[seed] refusing to write to what looks like the real ledger")

    random.seed(args.seed)
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)

    days = trading_days(args.days)
    n_recs = n_closes = 0

    for day in days:
        date_et = day.strftime("%Y-%m-%d")
        is_today = day.date() == datetime.now(timezone.utc).date()

        for pid, universe in PROFILE_UNIVERSE.items():
            # Day traders fire most days; conservative profiles rarely.
            odds = {"P01": .18, "P02": .22, "P03": .10, "P04": .40, "P05": .55,
                    "P06": .35, "P07": .35, "P08": .80, "P09": .90, "P10": .30}[pid]
            if random.random() > odds:
                continue
            k = random.randint(1, min(3 if pid in ("P08", "P09") else 2, len(universe)))
            for ticker in random.sample(universe, k):
                m = META[ticker]
                drift = random.uniform(-0.12, 0.16)
                price = round(m["price"] * (1 + drift), 2)
                low, high = round(price * 0.985, 2), round(price * 1.02, 2)
                ts = day.replace(hour=random.choice([14, 17, 19]),
                                 minute=random.randint(0, 59),
                                 second=0, microsecond=0)

                conn.execute("""
                    INSERT OR IGNORE INTO recommendations
                      (profile_id,ticker,name,sector,region,exchange,currency,
                       price,buy_low,buy_high,confidence,horizon,thesis,risk,
                       slot,created_at,created_date_et)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (pid, ticker, m["name"], m["sector"], m["region"],
                     m["exchange"], m["currency"], price, low, high,
                     random.choice(["HIGH", "MEDIUM", "MEDIUM"]),
                     random.choice(["2-4 weeks", "6-12 months", "12-18 months"]),
                     THESIS.format(name=m["name"], sector=m["sector"],
                                   angle=random.choice(ANGLES),
                                   catalyst=random.choice(CATALYSTS),
                                   low=low, high=high,
                                   horizon=random.choice(["2-4 weeks", "12-18 months"])),
                     random.choice(RISKS), "16:30 CET / 10:30 ET",
                     ts.strftime("%Y-%m-%d %H:%M:%S"), date_et))
                n_recs += conn.total_changes and 1 or 0

                # Freeze a close for every finished day. Today stays unsettled
                # so the "pending" path gets exercised too.
                if not is_today:
                    close = round(price * (1 + random.gauss(0.002, 0.021)), 2)
                    conn.execute("""INSERT OR REPLACE INTO daily_closes
                                    (ticker,date,close,captured_at)
                                    VALUES (?,?,?,?)""",
                                 (ticker, date_et, close,
                                  ts.strftime("%Y-%m-%d %H:%M:%S")))
                    n_closes += 1

    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0]
    closes = conn.execute("SELECT COUNT(*) FROM daily_closes").fetchone()[0]
    days_n = conn.execute("SELECT COUNT(DISTINCT created_date_et) FROM recommendations").fetchone()[0]
    conn.close()

    print(f"[seed] {total} recommendations · {closes} closes · {days_n} trading days → {db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
