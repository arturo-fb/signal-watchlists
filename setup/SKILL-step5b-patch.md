# Patch for `shared-investment-signals/SKILL.md`

Two edits to make the scheduled task feed the ledger. Open
`/Users/fraile/Documents/Claude/Scheduled/shared-investment-signals/SKILL.md`
and apply both.

Until this is done the site will build correctly but stay empty — recommendations
get posted to Discord and the structured facts are lost, exactly as before.

---

## Edit 1 — add a line to `## CONTEXT`

After the `discord-bot/poster.py` bullet, add:

```
- data/recommendations.db is the ledger every published watchlist is built from. `record_rec.py` writes to it. A name that gets posted but not recorded is invisible on the site permanently, because the price it fired at cannot be reconstructed after the fact. bot.py pushes the ledger to GitHub within ~2 minutes, and the site rebuilds itself from there.
```

---

## Edit 2 — insert a new `## STEP 5b` immediately after `## STEP 5 — POST`

```markdown
## STEP 5b — RECORD TO THE LEDGER (do this every time you post)
Immediately after poster.py succeeds for a profile, log that profile's names to
the ledger. This is what the public watchlists are built from.

Write a JSON file to `users/tmp/rec-<PROFILE_ID>.json`:

{
  "profile_id": "P05",
  "slot": "16:30 CET / 10:30 ET",
  "recs": [
    {"ticker": "NVDA", "confidence": "HIGH", "buy_low": 170.0, "buy_high": 178.0,
     "horizon": "12-18 months",
     "risk": "one-sentence version of the main risk you wrote",
     "thesis": "the full thesis for this name, exactly as it went into the digest"}
  ]
}

Then run, from the project root:
`python3 record_rec.py --batch users/tmp/rec-P05.json`

Rules:
- One call per profile, listing only the names you actually posted to that profile.
- Omit `price`. record_rec.py fetches the live quote at that moment, which is the
  price a member could actually have acted on. Pass `price` explicitly only when
  you quoted a specific figure in the digest and want the ledger to match it.
- `ticker` must be the Yahoo Finance symbol (`SAN.MC`, `SHEL.L`, `NVDA`). Region,
  currency and exchange are derived from the suffix; `name` and `sector` are
  looked up automatically.
- Copy the thesis in full. The site shows it on that ticker's detail page, and
  once a name has been recommended more than once it generates a combined AI
  summary from all of them — a thin thesis degrades that page permanently.
- Duplicates are safe. The ledger ignores a repeat of the same ticker to the same
  profile on the same ET day, matching STEP 6's no-repeat rule, so re-running the
  task never double-counts.
- If record_rec.py fails, note it in your output and carry on. A failed ledger
  write must not stop the remaining profiles from being posted.
```

---

## Edit 3 — extend the closing `Constraints:` line

The current line lists what the task is allowed to write. Add the ledger:

> ...only write the temp message files, `users/.posted_today.json`,
> `users/tmp/rec-*.json`, `data/recommendations.db` (via record_rec.py), and
> (via poster.py) `users/pending_posts/` queue files.

And extend the success criterion:

> Success = every due profile either had a quality digest queued for delivery
> **and its names recorded to the ledger**, or was deliberately skipped.
