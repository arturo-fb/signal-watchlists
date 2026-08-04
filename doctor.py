#!/usr/bin/env python3
"""
doctor.py — Preflight the whole pipeline on the machine that actually runs it.

Two things could not be tested where this was built: SQLite writing to the real
ledger path, and Yahoo Finance reachability (the build sandbox blocks both).
Everything else was verified. This script closes that gap — run it once on the
Mac and it exercises the full chain end to end.

    python3 doctor.py              # everything
    python3 doctor.py --quick      # skip network calls

Exit code 0 = ready to publish. 1 = at least one blocking failure.
Every failure prints the specific command that fixes it.
"""

from __future__ import annotations

import argparse
import importlib
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHARED = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SHARED))

PASS, FAIL, WARN, SKIP = "PASS", "FAIL", "WARN", "SKIP"
ICON = {PASS: "\033[32m✓\033[0m", FAIL: "\033[31m✗\033[0m",
        WARN: "\033[33m!\033[0m", SKIP: "\033[90m–\033[0m"}

results: list[tuple[str, str, str, str]] = []   # (status, name, detail, fix)


def record(status, name, detail="", fix=""):
    results.append((status, name, detail, fix))
    line = f" {ICON[status]} {name}"
    if detail:
        line += f"\n     {detail}"
    print(line)
    if status == FAIL and fix:
        print(f"     \033[36m→ {fix}\033[0m")


def section(title):
    print(f"\n\033[1m{title}\033[0m")


# ── 1. Environment ───────────────────────────────────────────────────────────

def check_python():
    v = sys.version_info
    if v < (3, 9):
        record(FAIL, "Python version", f"{v.major}.{v.minor} — need 3.9+ (zoneinfo)",
               "brew install python@3.11")
    else:
        record(PASS, "Python version", f"{v.major}.{v.minor}.{v.micro}")


def check_deps():
    for mod, why, blocking in [
        ("yfinance", "live prices and daily closes", True),
        ("discord", "the bot that relays posts and pushes the ledger", False),
    ]:
        try:
            m = importlib.import_module(mod)
            ver = getattr(m, "__version__", "?")
            record(PASS, f"{mod} installed", f"v{ver} — {why}")
        except ImportError:
            record(FAIL if blocking else WARN, f"{mod} missing", why,
                   f"pip3 install {mod}")


# ── 2. SQLite on the real filesystem ─────────────────────────────────────────

def check_sqlite():
    """
    The one thing the build sandbox genuinely could not test.

    SQLite needs POSIX file locking. It works on a normal macOS volume and fails
    on some network/FUSE mounts — which is exactly how the project folder was
    exposed during development, so this path was never exercised for real.
    """
    data_dir = SHARED / "data"
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        record(FAIL, "Ledger directory writable", f"{data_dir}: {exc}",
               f"mkdir -p {data_dir}")
        return False

    probe = data_dir / ".doctor_probe.db"

    def sweep():
        """Remove the probe and any journal/WAL siblings SQLite left behind."""
        for suffix in ("", "-journal", "-wal", "-shm"):
            try:
                Path(str(probe) + suffix).unlink(missing_ok=True)
            except OSError:
                pass  # read-only or locked volume — the failure is the finding

    try:
        conn = sqlite3.connect(probe)
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        conn.execute("INSERT INTO t (v) VALUES ('x')")
        conn.commit()
        # Concurrent reader while the writer holds a transaction — this is the
        # locking behaviour that fails on a bad mount, not the plain write.
        conn2 = sqlite3.connect(probe)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("INSERT INTO t (v) VALUES ('y')")
        conn2.execute("SELECT COUNT(*) FROM t").fetchone()
        conn.commit()
        n = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
        conn.close(); conn2.close()
        sweep()
        record(PASS, "SQLite read/write + locking", f"{data_dir} ({n} rows round-tripped)")
        return True
    except Exception as exc:
        sweep()
        record(FAIL, "SQLite read/write + locking", f"{type(exc).__name__}: {exc}",
               "The ledger cannot live on this volume. Move the project to a "
               "local disk (not iCloud Drive, a network share, or an external "
               "FUSE mount).")
        return False


def check_ledger_roundtrip():
    """record_rec → read back → duplicate is ignored."""
    tmp = Path(tempfile.mkdtemp()) / "probe.db"
    try:
        from ledger.db import all_recommendations, record_rec

        a = record_rec("P05", "DOCTOR.TEST", price=100.0, name="Doctor Probe",
                       confidence="HIGH", thesis="probe", db_path=tmp)
        b = record_rec("P05", "DOCTOR.TEST", price=101.0, db_path=tmp)
        rows = all_recommendations(db_path=tmp)

        ok = (a["status"] == "recorded" and b["status"] == "duplicate"
              and len(rows) == 1 and rows[0]["price"] == 100.0)
        if ok:
            record(PASS, "Ledger write + same-day dedupe",
                   "1 row stored, repeat correctly ignored")
        else:
            record(FAIL, "Ledger write + same-day dedupe",
                   f"first={a['status']} second={b['status']} rows={len(rows)}",
                   "Unexpected — re-run with the traceback: "
                   "python3 -c \"from ledger.db import record_rec; print(record_rec('P01','X',price=1))\"")
    except Exception as exc:
        record(FAIL, "Ledger write + same-day dedupe", f"{type(exc).__name__}: {exc}",
               "Check ledger/db.py is present and importable from the project root")
    finally:
        shutil.rmtree(tmp.parent, ignore_errors=True)


# ── 3. Market data ───────────────────────────────────────────────────────────

def check_yahoo(quick: bool):
    """
    The other thing the sandbox blocked.

    Checks a US name, a Spanish name, and a UK name — the suffix handling and
    the GBX/pence convention are where symbol problems actually show up, not on
    plain US tickers.
    """
    if quick:
        record(SKIP, "Yahoo Finance reachable", "--quick")
        return

    try:
        import yfinance as yf
    except ImportError:
        record(SKIP, "Yahoo Finance reachable", "yfinance not installed")
        return

    probes = [("NVDA", "US"), ("SAN.MC", "Madrid / EUR"), ("SHEL.L", "London / GBX")]
    got, failed = [], []
    t0 = time.time()
    for sym, label in probes:
        try:
            price = float(yf.Ticker(sym).fast_info.last_price)
            if price > 0:
                got.append(f"{sym} {price:,.2f} ({label})")
            else:
                failed.append(f"{sym} returned {price}")
        except Exception as exc:
            failed.append(f"{sym}: {type(exc).__name__}")
    elapsed = time.time() - t0

    if len(got) == len(probes):
        record(PASS, "Yahoo Finance reachable",
               " · ".join(got) + f"  [{elapsed:.1f}s]")
    elif got:
        record(WARN, "Yahoo Finance partially reachable",
               f"ok: {', '.join(got)} | failed: {', '.join(failed)}")
    else:
        record(FAIL, "Yahoo Finance reachable", " | ".join(failed),
               "Check the network, then: pip3 install --upgrade yfinance")


def check_splits(quick: bool):
    if quick:
        record(SKIP, "Split history readable", "--quick")
        return
    try:
        import yfinance as yf
        splits = yf.Ticker("NVDA").splits
        record(PASS, "Split history readable",
               f"NVDA: {len(splits)} historical splits")
    except Exception as exc:
        record(WARN, "Split history readable", f"{type(exc).__name__}: {exc}",
               "Non-blocking — entries just won't be split-adjusted")


# ── 4. Config ────────────────────────────────────────────────────────────────

def check_profiles():
    import json
    for path in (SHARED / "profiles" / "profiles.json", HERE / "data" / "profiles.json"):
        try:
            data = json.loads(path.read_text())
            profiles = data["profiles"]
            roles = [p["discord_role"] for p in profiles]
            issues = []
            if len(profiles) != 10:
                issues.append(f"{len(profiles)} profiles, expected 10")
            if len(set(roles)) != len(roles):
                issues.append("duplicate discord_role — pages would overwrite each other")
            missing = [p["id"] for p in profiles
                       if not all(k in p for k in ("id", "name", "discord_role",
                                                   "risk_tolerance", "regions"))]
            if missing:
                issues.append(f"missing required fields: {missing}")

            label = "project" if "profiles" in path.parts else "repo copy"
            if issues:
                record(FAIL, f"profiles.json ({label})", "; ".join(issues),
                       f"Fix {path}")
            else:
                record(PASS, f"profiles.json ({label})",
                       f"10 profiles · {', '.join(roles[:4])} …")
        except FileNotFoundError:
            if "watchlist-site" in path.parts:
                record(FAIL, "profiles.json (repo copy)", f"missing at {path}",
                       f"cp {SHARED}/profiles/profiles.json {path}")
            else:
                record(FAIL, "profiles.json (project)", f"missing at {path}", "")
        except Exception as exc:
            record(FAIL, f"profiles.json ({path.name})", f"{type(exc).__name__}: {exc}", "")


def check_profiles_in_sync():
    import json
    a, b = SHARED / "profiles" / "profiles.json", HERE / "data" / "profiles.json"
    if not (a.exists() and b.exists()):
        return
    if json.loads(a.read_text()) == json.loads(b.read_text()):
        record(PASS, "Repo profiles copy in sync", "")
    else:
        record(WARN, "Repo profiles copy is stale",
               "the site would build against out-of-date profile settings",
               f"cp {a} {b}")


def check_summaries():
    """
    Thesis syntheses are written by the ticker-thesis-summaries scheduled task,
    not by an API call from the build — so there is no key to check. What
    matters is that the task exists and is keeping up with the backlog.
    """
    task = Path.home() / "Documents/Claude/Scheduled/ticker-thesis-summaries/SKILL.md"
    if not task.exists():
        record(FAIL, "Summary task installed", "ticker-thesis-summaries not found",
               "Multi-recommendation ticker pages will permanently show their "
               "individual theses instead of a combined summary.")
        return
    record(PASS, "Summary task installed", "ticker-thesis-summaries · weekdays 22:15")

    db = SHARED / "data" / "recommendations.db"
    if not db.exists():
        return
    try:
        proc = subprocess.run(
            [sys.executable, "summaries.py", "--db", str(db), "pending"],
            cwd=HERE, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            record(WARN, "Summary backlog", (proc.stderr or "").strip()[-160:],
                   "python3 summaries.py pending --pretty")
            return
        import json
        todo = json.loads(proc.stdout or "[]")
        stored = len(_stored_summaries(db))
        if not todo:
            record(PASS, "Summary backlog", f"nothing pending · {stored} stored")
        else:
            record(WARN, "Summary backlog",
                   f"{len(todo)} ticker(s) awaiting a synthesis · {stored} stored",
                   "Normal between runs. To do it now: open the "
                   "ticker-thesis-summaries task and click Run now.")
    except Exception as exc:
        record(WARN, "Summary backlog", f"{type(exc).__name__}: {exc}")


def _stored_summaries(db) -> list:
    try:
        conn = sqlite3.connect(str(db))
        rows = conn.execute("SELECT profile_id, ticker FROM thesis_summaries").fetchall()
        conn.close()
        return rows
    except Exception:
        return []


# ── 5. Build ─────────────────────────────────────────────────────────────────

def check_build(quick: bool):
    """Real build into a throwaway directory — never touches docs/."""
    db = SHARED / "data" / "recommendations.db"
    args = [sys.executable, "build_site.py", "--no-summaries", "--quiet"]
    if quick or not db.exists():
        args.append("--no-prices")
    if db.exists():
        args += ["--db", str(db)]

    tmp = Path(tempfile.mkdtemp())
    real_docs = HERE / "docs"
    stash = None
    try:
        if real_docs.exists():
            stash = tmp / "docs_backup"
            shutil.move(str(real_docs), str(stash))

        proc = subprocess.run(args, cwd=HERE, capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout).strip().splitlines()[-3:]
            record(FAIL, "Site build", " / ".join(tail),
                   "python3 build_site.py   (to see the full traceback)")
            return

        pages = list(real_docs.rglob("index.html")) if real_docs.exists() else []
        landing = real_docs / "index.html"
        if not landing.exists():
            record(FAIL, "Site build", "no landing page produced", "")
            return

        html = landing.read_text()
        checks = []
        if 'id="gate"' not in html:
            checks.append("passphrase gate missing")
        if "pcard" not in html:
            checks.append("no profile cards")
        if checks:
            record(FAIL, "Site build", "; ".join(checks), "")
        else:
            record(PASS, "Site build", f"{len(pages)} pages rendered")
    except subprocess.TimeoutExpired:
        record(FAIL, "Site build", "timed out after 10 min",
               "Usually Yahoo rate-limiting. Retry, or use --quick.")
    except Exception as exc:
        record(FAIL, "Site build", f"{type(exc).__name__}: {exc}", "")
    finally:
        if stash and stash.exists():
            shutil.rmtree(real_docs, ignore_errors=True)
            shutil.move(str(stash), str(real_docs))
        shutil.rmtree(tmp, ignore_errors=True)


def check_stale_journal():
    """
    A leftover -journal/-wal means the last write to the ledger was interrupted.

    Worth calling out on its own, because the symptom SQLite reports is
    "attempt to write a readonly database" — which reads like a permissions
    problem and sends you hunting in the wrong place entirely.
    """
    db = SHARED / "data" / "recommendations.db"
    leftovers = [p for p in (Path(str(db) + s) for s in ("-journal", "-wal"))
                 if p.exists()]
    if not leftovers:
        return

    names = ", ".join(p.name for p in leftovers)
    try:
        # A plain connection lets SQLite roll the journal back and clear it.
        conn = sqlite3.connect(str(db))
        conn.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone()
        conn.close()
        still = [p for p in leftovers if p.exists()]
        if still:
            record(WARN, "Unclean ledger shutdown", f"{names} still present",
                   f"rm {' '.join(str(p) for p in still)}")
        else:
            record(PASS, "Unclean ledger shutdown recovered",
                   f"rolled back and cleared {names}")
    except Exception as exc:
        record(FAIL, "Unclean ledger shutdown", f"{names} — {type(exc).__name__}: {exc}",
               f"The ledger is unrecoverable. If it has no real data yet, delete it:\n"
               f"       rm {db} {' '.join(str(p) for p in leftovers)}")


def check_ledger_contents():
    db = SHARED / "data" / "recommendations.db"
    if not db.exists():
        record(WARN, "Ledger has data", "no ledger yet — normal before the first "
               "scheduled run posts anything",
               "Confirm STEP 5b is in the scheduled task, then wait for a run.")
        return
    try:
        sys.path.insert(0, str(HERE))
        from build.model import open_ledger
        conn = open_ledger(db)
        n = conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0]
        profs = conn.execute("SELECT COUNT(DISTINCT profile_id) FROM recommendations").fetchone()[0]
        days = conn.execute("SELECT COUNT(DISTINCT created_date_et) FROM recommendations").fetchone()[0]
        closes = conn.execute("SELECT COUNT(*) FROM daily_closes").fetchone()[0]
        withthesis = conn.execute(
            "SELECT COUNT(*) FROM recommendations WHERE thesis IS NOT NULL AND thesis != ''"
        ).fetchone()[0]
        conn.close()

        if n == 0:
            record(WARN, "Ledger has data", "table exists but is empty",
                   "The scheduled task hasn't recorded anything yet.")
        else:
            record(PASS, "Ledger has data",
                   f"{n} recs · {profs} profiles · {days} days · {closes} closes")
            if withthesis < n:
                record(WARN, "Theses captured", f"{withthesis}/{n} have thesis text",
                       "Ticker detail pages need this. Check STEP 5b is sending "
                       "the full thesis, not a summary.")
    except Exception as exc:
        record(FAIL, "Ledger readable", f"{type(exc).__name__}: {exc}", "")


# ── 6. Publishing ────────────────────────────────────────────────────────────

def check_git():
    if not (HERE / ".git").exists():
        record(WARN, "Git repo initialised", "not a repo yet — nothing is published",
               "See SETUP.md step 2")
        return

    def git(*a):
        return subprocess.run(["git", "-C", str(HERE), *a],
                              capture_output=True, text=True, timeout=30)

    remote = git("remote", "get-url", "origin")
    if remote.returncode != 0:
        record(WARN, "Git remote configured", "no origin",
               "git remote add origin https://github.com/arturo-fb/signal-watchlists.git")
        return
    url = remote.stdout.strip()
    record(PASS, "Git remote configured", url)

    # Anything sensitive tracked?
    tracked = git("ls-files").stdout.split()
    danger = [f for f in tracked
              if f == ".env" or f.startswith(".env.")
              or f.endswith((".key", ".pem"))
              or f in ("anthropic.txt", "GMAIL.txt", "NewsAPI.txt", "credentials.json")]
    if danger:
        record(FAIL, "No secrets tracked", f"tracked: {', '.join(danger)}",
               f"git rm --cached {' '.join(danger)} && git commit -m 'Remove secrets'")
    else:
        record(PASS, "No secrets tracked", f"{len(tracked)} files tracked, none sensitive")

    if "data/recommendations.db" not in tracked and (SHARED / "data" / "recommendations.db").exists():
        record(WARN, "Ledger tracked in git", "the ledger exists but isn't committed — "
               "the Action would build an empty site",
               "It is copied in automatically by bot.py; or: "
               "cp ../data/recommendations.db data/ && git add -f data/recommendations.db")


def check_ledger_sync():
    try:
        sys.path.insert(0, str(SHARED / "discord-bot"))
        import ledger_sync
        if ledger_sync.is_configured():
            record(PASS, "bot.py ledger sync", "repo + remote found — pushes are armed")
        else:
            record(WARN, "bot.py ledger sync", "idle until the repo has a remote",
                   "See SETUP.md step 2, then restart bot.py")
    except Exception as exc:
        record(FAIL, "bot.py ledger sync", f"{type(exc).__name__}: {exc}",
               "Check discord-bot/ledger_sync.py is present")


def check_scheduled_task():
    """The single most common reason the site stays empty."""
    path = Path.home() / "Documents/Claude/Scheduled/shared-investment-signals/SKILL.md"
    if not path.exists():
        record(WARN, "Scheduled task patched", f"not found at {path}", "")
        return
    text = path.read_text()
    if "record_rec.py --batch" in text and "STEP 5b" in text:
        record(PASS, "Scheduled task patched", "STEP 5b present — recommendations "
               "will be recorded")
    else:
        record(FAIL, "Scheduled task patched", "STEP 5b missing — recommendations "
               "are posted to Discord and then lost, so the site stays empty forever",
               "Apply setup/SKILL-step5b-patch.md")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="skip network calls")
    args = ap.parse_args()

    print("\033[1mSignal Watchlists — preflight\033[0m")
    print(f"project: {SHARED}")

    section("Environment")
    check_python()
    check_deps()

    section("Storage")
    if check_sqlite():
        check_ledger_roundtrip()
    check_stale_journal()
    check_ledger_contents()

    section("Market data")
    check_yahoo(args.quick)
    check_splits(args.quick)

    section("Configuration")
    check_profiles()
    check_profiles_in_sync()
    check_summaries()

    section("Build")
    check_build(args.quick)

    section("Publishing")
    check_scheduled_task()
    check_git()
    check_ledger_sync()

    fails = [r for r in results if r[0] == FAIL]
    warns = [r for r in results if r[0] == WARN]
    passes = [r for r in results if r[0] == PASS]

    print(f"\n\033[1m{'─' * 58}\033[0m")
    print(f" {len(passes)} passed · {len(warns)} warnings · {len(fails)} failures")

    if fails:
        print("\n\033[31mBlocking:\033[0m")
        for _, name, detail, fix in fails:
            print(f"  • {name}" + (f" — {detail}" if detail else ""))
            if fix:
                print(f"    → {fix}")
        return 1

    if warns:
        print("\n\033[33mWorth a look (not blocking):\033[0m")
        for _, name, detail, _ in warns:
            print(f"  • {name}" + (f" — {detail}" if detail else ""))

    print("\n\033[32mReady to publish.\033[0m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
