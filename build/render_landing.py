"""
render_landing.py — The site's front door.

A full-height hero, then the ten channel cards below the fold. Each card links
to that profile's watchlist at /<discord_role>/, which mirrors the Discord
channel name so #signals-swing and /swing/ are obviously the same thing.
"""

from __future__ import annotations

from .html_util import esc, horizon_label, page, risk_class, stat_pct
from .theme import GATE_HTML, GATE_JS, LANDING_CSS, page_css


def _card(profile: dict, view: dict, is_trader: bool) -> str:
    role = profile["discord_role"]
    regions = " · ".join("🇪🇺 Europe" if r == "europe" else "🇺🇸 US"
                         for r in profile["regions"])

    if is_trader:
        tag = '<span class="daytag">Day trading</span>'
        count = view.get("total_recs", 0)
        count_html = (f'<span class="pc-count"><b>{count}</b> '
                      f'rec{"s" if count != 1 else ""} this month</span>')
        perf = view.get("mtd_pct")
        if perf is not None:
            count_html += f'&nbsp;&nbsp;{stat_pct(perf)}'
    else:
        tag = ""
        count = view.get("total", 0)
        count_html = (f'<span class="pc-count"><b>{count}</b> '
                      f'ticker{"s" if count != 1 else ""} tracked</span>')
        avg = view.get("avg_pnl")
        if avg is not None:
            count_html += f'&nbsp;&nbsp;{stat_pct(avg)}'

    return f"""
  <a class="pcard{' is-trader' if is_trader else ''}" href="{esc(role)}/">
    <div class="pc-top">
      <div>
        <div class="pc-id">{esc(profile['id'])}</div>
        <div class="pc-name">{esc(profile['name'])}</div>
        <div class="pc-handle">#signals-{esc(role)}</div>
      </div>
      {tag}
    </div>
    <div class="pc-desc">{esc(profile['description'])}</div>
    <div class="pc-meta">
      <span class="chip {risk_class(profile['risk_tolerance'])}">Risk {profile['risk_tolerance']}/10</span>
      <span class="chip">{esc(horizon_label(profile['investment_horizon_months']))}</span>
      <span class="chip">{regions}</span>
    </div>
    <div class="pc-foot">
      {count_html}
      <span class="pc-go">Open watchlist <span>→</span></span>
    </div>
  </a>"""


def render(profiles: list[dict], views: dict, updated: str,
           totals: dict, is_trader_fn) -> str:
    cards = "".join(
        _card(p, views.get(p["id"], {}), is_trader_fn(p)) for p in profiles
    )

    body = f"""
<section class="hero">
  <div class="hero-badge">● Live · updated automatically</div>
  <h1>Ten channels.<br><span class="grad">Ten watchlists.</span></h1>
  <p class="lede">
    Every recommendation posted to the Discord channels, tracked from the price
    it fired at. Each profile gets its own board — conservative long-term picks
    and intraday momentum calls are scored on completely different terms, so
    they're kept apart.
  </p>
  <div class="hero-stats">
    <div><div class="hs-val blue">{totals['profiles']}</div><div class="hs-lbl">Channels</div></div>
    <div><div class="hs-val">{totals['tickers']}</div><div class="hs-lbl">Tickers tracked</div></div>
    <div><div class="hs-val">{totals['recs']}</div><div class="hs-lbl">Recommendations</div></div>
    <div><div class="hs-val">{stat_pct(totals['avg_pnl'])}</div><div class="hs-lbl">Avg P&amp;L</div></div>
  </div>
  <div class="scroll-cue" onclick="document.getElementById('channels').scrollIntoView({{behavior:'smooth'}})">
    <span>Pick your channel</span>
    <span class="chev">⌄</span>
  </div>
</section>

<div class="wrap" id="channels">
  <div class="section-head">
    <h2>Channels</h2>
    <p>The same ten profiles as the Discord server. Open any one to see its
       recommendations, entry prices, and running performance.</p>
  </div>
  <div class="profiles-grid">{cards}</div>

  <footer>
    Updated automatically · Prices via Yahoo Finance · Last build {esc(updated)}
    <div class="disclaimer">This is not professional financial advice — always make your own decisions.</div>
  </footer>
</div>
"""
    return page("Signal Watchlists", page_css(LANDING_CSS), body, "",
                GATE_HTML, GATE_JS, depth=0)
