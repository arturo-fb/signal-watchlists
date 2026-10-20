# Signal Watchlists

The Signals watchlist for the Discord group: one board that tracks every momentum signal from the price it fired at, plus an Entries & exits tab with the actionable trades. (Until 2026-10-20 the site had ten per-profile boards; their old links redirect here.)

Published with GitHub Pages. The pages are passphrase-gated — ask Arturo.

## How it works

Recommendations are posted to Discord by a scheduled task, which records each one to a SQLite ledger at data/recommendations.db together with the live price at that moment. The bot pushes that ledger here. A scheduled Action rebuilds the site every 20 minutes while markets are open, refreshing prices, and freezes each day's official close after the US session ends.

Nothing here needs an API key. Thesis summaries are written by a separate scheduled task and travel inside the ledger.

See SETUP.md for the full picture, and run doctor.py to check the pipeline end to end.

## Not financial advice

These are automated signals shared among family and friends. Always make your own decisions.
