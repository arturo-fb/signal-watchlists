# Publishing the watchlists

Everything is built. This is what's left to do once, by hand.

**Result:** `https://arturo-fb.github.io/signal-watchlists/`
**Passphrase:** `alpha-loop-2026`

---

## 0. Run the preflight first

```bash
cd ~/Documents/investment-signal-shared/watchlist-site
python3 doctor.py
```

It checks every link in the chain on **this** machine and prints the exact fix
for anything broken. Two of its checks exist specifically because they could not
be tested where this was built:

- **SQLite read/write + locking** — the ledger needs POSIX file locking. It works
  on a normal macOS volume and fails on iCloud Drive, network shares and FUSE
  mounts. The project folder was exposed as a FUSE mount during development, so
  this path was never exercised for real.
- **Yahoo Finance reachable** — resolves a US, a Spanish and a UK symbol, because
  suffix handling and the GBX/pence convention are where symbol problems
  actually appear. The build environment blocked Yahoo entirely.

Everything else was verified before delivery. Re-run `doctor.py` after each step
below; it's the fastest way to see what's still outstanding.

Flag: `--quick` skips the network calls.

---

## 1. Create the repo

On https://github.com/new — name `signal-watchlists`, **Public**, no README,
no .gitignore, no licence (this folder already has what it needs).

Public is required for free GitHub Pages. The passphrase gate keeps casual
visitors out of the pages; it is not real security, and anyone who reads the
repo can bypass it. Nothing sensitive is committed — see step 2.

## 2. Push this folder

```bash
cd ~/Documents/investment-signal-shared/watchlist-site

git init
git branch -M main

# Check what is about to be committed BEFORE the first push.
# There must be no .env, no *.txt key files, no tokens.
git add -A
git status --short

git commit -m "Per-channel signal watchlists"
git remote add origin https://github.com/arturo-fb/signal-watchlists.git
git push -u origin main
```

The `.gitignore` already excludes `.env`, `anthropic.txt`, `GMAIL.txt`,
`NewsAPI.txt`, `*.key` and `*.pem`. `data/recommendations.db` **is** committed
on purpose — it is what the build reads, and it holds only tickers, prices,
dates and theses. No keys, no Discord IDs, no member names.

## 3. Turn on Pages

Repo → **Settings** → **Pages** → Source: **GitHub Actions**.

Not "Deploy from a branch" — the workflow publishes the artifact directly.

## 4. No secrets needed

Nothing to configure here. The published build only needs prices.

The combined thesis summaries are written by the `ticker-thesis-summaries`
scheduled task on your machine, under your Claude subscription — no API key
lives in the repo, nothing to rotate, and rebuilding every 20 minutes costs
nothing extra. The summaries travel to the site inside the ledger like any
other data.

## 5. Scheduled task — already done

`shared-investment-signals` has been updated in place: STEP 5b now calls
`record_rec.py` after every post, so recommendations are recorded instead of
discarded. `doctor.py` confirms this under "Scheduled task patched".

`setup/SKILL-step5b-patch.md` is kept only as a record of what changed, in case
the task is ever rebuilt from scratch.

## 6. Restart the bot

```bash
cd ~/Documents/investment-signal-shared
pkill -f discord-bot/bot.py
python3 discord-bot/bot.py
```

Look for `ledger sync on` in the startup line. If it says
`idle (repo not set up yet)`, step 2 hasn't been done.

---

## How it stays current without you

```
shared-investment-signals posts to Discord   (5x per weekday)
        │
        ├─→ record_rec.py       writes data/recommendations.db  (live price captured here)
        │
ticker-thesis-summaries                      (weekdays 22:15)
        └─→ summaries.py write  combined theses, into the same ledger
        │
bot.py (every 2 min)
        └─→ git push            ledger lands in the repo
                │
GitHub Actions
        ├─ every 20 min, Mon–Fri 07:00–22:00 UTC   refresh prices, rebuild
        ├─ 21:30 UTC weekdays                      freeze each day's close
        └─ on every ledger push                    rebuild immediately
                │
                └─→ GitHub Pages
```

You never run `generate_watchlist.py`. New recommendations appear within a few
minutes; prices refresh on their own while markets are open.

---

## The pages

| Path | Profile | Type |
|---|---|---|
| `/` | landing — hero, then the ten channel cards | |
| `/conservative-lt/` | P01 Conservative Long-Term | investor |
| `/dividends/` | P02 Dividends & Income | investor |
| `/index-etf/` | P03 Index & ETFs | investor |
| `/growth/` | P04 Classic Growth | investor |
| `/aggressive/` | P05 Aggressive Growth | investor |
| `/europe-value/` | P06 Europe Value | investor |
| `/balanced/` | P07 Global Balanced | investor |
| `/swing/` | P08 Swing Trader | **day trading** |
| `/trader/` | P09 Momentum Trader | **day trading** |
| `/thematic/` | P10 Thematic & Innovation | investor |
| `/<channel>/<TICKER>/` | ticker detail — thesis, AI summary, all recommendations | |
| `/swing/m/2026-07/` | archived month | |

**Investor pages** carry the layout you already use — entry price, live price,
P&L, Recs badge with its hover breakdown — plus the recommendation-count filter
(`≥ > ≤ < =` against a number you type). Combining it with the date range
re-anchors each row to its first recommendation inside the window.

**Day-trading pages** show only today's board and clear at midnight ET.
"Performance by day" reveals every day of the month on hover; weekly cards break
the month down day by day; the banner carries month-to-date. Each day is
measured signal price → same-day close, averaged across that day's names, and
days are compounded into weeks and months. A day is excluded until its close is
frozen, so a half-finished session never moves the monthly number.

---

## Running it by hand

```bash
cd ~/Documents/investment-signal-shared/watchlist-site

python3 build_site.py                  # full build into docs/
python3 build_site.py --no-prices      # fast, no network
python3 snapshot_closes.py --dry-run   # show which closes are missing

# Thesis summaries (normally handled by the ticker-thesis-summaries task)
python3 summaries.py pending --pretty  # what still needs a synthesis
python3 summaries.py list              # what is already stored

# Demo data, to see the pages populated before real recommendations exist
python3 seed_demo.py --db /tmp/demo.db
python3 build_site.py --db /tmp/demo.db --no-prices --no-summaries
open docs/index.html
```

---

## If something looks wrong

**Site is empty** — the ledger has no rows. Check:
`sqlite3 data/recommendations.db "SELECT COUNT(*) FROM recommendations"`.
If it's 0, step 5 wasn't applied.

**Prices show `—`** — yfinance couldn't resolve the symbol. Check the ticker is
the Yahoo form (`SAN.MC`, not `SAN`). A single bad symbol never breaks the build.

**Day P/L stuck on "pending"** — no frozen close for that day yet. The 21:30 UTC
run fills it. Force it: `python3 snapshot_closes.py`.

**Ticker page missing its combined summary** — either the ticker has only one
recommendation (a single thesis is shown as posted; there is nothing to
combine), or the `ticker-thesis-summaries` task hasn't run since the latest
recommendation landed. Check with `python3 summaries.py pending --pretty`, and
click Run now on that task if you don't want to wait for 22:15.

A summary is also deliberately withheld once a *new* recommendation arrives for
that ticker — a synthesis that no longer covers the latest thesis reads as
current and quietly isn't, which is worse than showing the individual theses.
It reappears after the next summary run.

**Bot logs `push failed`** — usually credentials. Confirm `git push` works by
hand from `watchlist-site/`; a personal access token in the remote URL or a
configured credential helper will fix it.
