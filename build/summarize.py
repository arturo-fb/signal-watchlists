"""
summarize.py — Which tickers need a combined thesis, and how to store one.

Deliberately contains no model call. The syntheses are written by the
`ticker-thesis-summaries` scheduled task, which runs on Arturo's machine under
his Claude subscription. Two reasons that beats calling the API from the build:
the published site needs no API key at all (nothing secret in GitHub Secrets,
nothing to rotate), and rebuilds happen every 20 minutes during market hours —
metering a paid call on that loop would be paying repeatedly for work that only
changes when a new recommendation lands.

So the flow is:

    build (GitHub Actions)  reads thesis_summaries, renders whatever is there
    scheduled task (Mac)    finds what is stale, writes the synthesis
    bot.py                  pushes the ledger, next build picks it up

A ticker with no summary yet renders its individual theses instead, which is
the same graceful fallback as before — the page is never blocked on this.

Cache key: a hash of the exact thesis set the summary was built from. It goes
stale only when a genuinely new thesis is added, so nothing is regenerated on
a schedule.
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# Below this, a single thesis is shown as posted — there is nothing to combine.
MIN_RECS_FOR_SUMMARY = 2


def source_hash(history: list[dict]) -> str:
    """Fingerprint the thesis set — changes only when the content does."""
    parts = [f"{h['date']}|{h.get('price')}|{h.get('thesis', '')}" for h in history]
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]


def load_cached(db_path) -> dict[tuple[str, str], dict]:
    """Every stored summary, keyed by (profile_id, ticker)."""
    if not Path(db_path).exists():
        return {}
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM thesis_summaries").fetchall()
        conn.close()
        return {(r["profile_id"], r["ticker"]): dict(r) for r in rows}
    except sqlite3.OperationalError:
        return {}


def resolve(views: dict, db_path, verbose: bool = True) -> dict[tuple[str, str], str]:
    """
    Summaries to render on this build: {(profile_id, ticker): text}.

    Only returns entries whose stored hash still matches the current thesis set.
    A stale entry is withheld rather than shown, because a summary that no
    longer reflects the latest recommendation is worse than no summary — it
    reads as current and quietly isn't.
    """
    cached = load_cached(db_path)
    out: dict[tuple[str, str], str] = {}
    stale = 0

    for profile_id, view in views.items():
        for row in view.get("rows", []):
            if row["rec_count"] < MIN_RECS_FOR_SUMMARY:
                continue
            key = (profile_id, row["ticker"])
            hit = cached.get(key)
            if not hit or not hit.get("summary"):
                stale += 1
            elif hit.get("source_hash") != source_hash(row["history"]):
                stale += 1
            else:
                out[key] = hit["summary"]

    if verbose:
        msg = f"[summary] {len(out)} rendered"
        if stale:
            msg += (f" · {stale} awaiting the ticker-thesis-summaries task "
                    f"(those pages show their individual theses meanwhile)")
        print(msg)
    return out


def pending(views: dict, db_path) -> list[dict]:
    """
    Work list for the scheduled task: every ticker needing a fresh synthesis.

    Each entry carries everything needed to write one, so the task does not have
    to re-derive prices or split adjustments from the raw ledger.
    """
    cached = load_cached(db_path)
    todo = []

    for profile_id, view in views.items():
        profile = view["profile"]
        for row in view.get("rows", []):
            if row["rec_count"] < MIN_RECS_FOR_SUMMARY:
                continue
            digest = source_hash(row["history"])
            hit = cached.get((profile_id, row["ticker"]))
            if hit and hit.get("source_hash") == digest and hit.get("summary"):
                continue

            todo.append({
                "profile_id": profile_id,
                "profile_name": profile["name"],
                "profile_description": profile["description"],
                "risk_tolerance": profile["risk_tolerance"],
                "horizon_months": profile["investment_horizon_months"],
                "ticker": row["ticker"],
                "name": row["name"],
                "currency": row["currency"],
                "rec_count": row["rec_count"],
                "source_hash": digest,
                "reason": "new" if not hit else "theses changed since last summary",
                "recommendations": [
                    {
                        "n": i + 1,
                        "date": h["date"],
                        "price": h["price"],
                        "confidence": h["confidence"],
                        "horizon": h["horizon"],
                        "risk": h["risk"],
                        "thesis": h["thesis"],
                    }
                    for i, h in enumerate(row["history"])
                ],
            })
    return todo


def store(db_path, profile_id: str, ticker: str, source_hash_value: str,
          summary: str) -> None:
    """Write one synthesis back to the ledger."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS thesis_summaries (
                profile_id TEXT NOT NULL, ticker TEXT NOT NULL,
                source_hash TEXT NOT NULL, summary TEXT, generated_at TEXT,
                PRIMARY KEY (profile_id, ticker))""")
        conn.execute("""
            INSERT INTO thesis_summaries
                (profile_id, ticker, source_hash, summary, generated_at)
            VALUES (?,?,?,?,?)
            ON CONFLICT(profile_id, ticker) DO UPDATE SET
                source_hash  = excluded.source_hash,
                summary      = excluded.summary,
                generated_at = excluded.generated_at""",
            (profile_id, ticker.upper(), source_hash_value, summary,
             datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    finally:
        conn.close()
