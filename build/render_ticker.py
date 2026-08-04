"""
render_ticker.py — The per-ticker detail page.

Reached by clicking a ticker on any watchlist. Shows, in order:

  1. current price and the position's P&L from the first recommendation
  2. the thesis — either the single thesis as posted to Discord, or, when the
     name has been recommended more than once, an AI synthesis of every thesis
     written about it, so you get one coherent story instead of five overlapping
     ones
  3. the individual theses on a timeline, each with its own price and P&L
  4. the full All Recommendations table

The AI summary is generated in the build (see summarize.py) and cached, so it
only costs an API call when a genuinely new thesis has been added.
"""

from __future__ import annotations

from .html_util import (esc, flag, markdown, money, money_signed, page,
                        pct_html, stat_pct)
from .theme import GATE_HTML, GATE_JS, TICKER_CSS, page_css

ORDINALS = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩",
            "⑪", "⑫", "⑬", "⑭", "⑮", "⑯", "⑰", "⑱", "⑲", "⑳"]


def _ordinal(i: int) -> str:
    return ORDINALS[i] if i < len(ORDINALS) else f"#{i + 1}"


def _timeline(row: dict) -> str:
    """Every individual thesis, oldest first, each with its own P&L."""
    items = []
    for i, h in enumerate(row["history"]):
        pnl = h["pnl"]
        pnl_cls = "up" if (pnl or 0) > 0 else ("dn" if (pnl or 0) < 0 else "neu")
        pnl_txt = f"{'+' if (pnl or 0) > 0 else ''}{pnl:.2f}%" if pnl is not None else "—"

        thesis_html = markdown(h["thesis"]) if h["thesis"] else (
            '<div class="no-thesis">No thesis text was captured for this '
            'recommendation.</div>')

        risk_html = ""
        if h["risk"]:
            risk_html = f'<div class="tl-risk"><b>Risk:</b> {esc(h["risk"])}</div>'

        meta = []
        if h["horizon"]:
            meta.append(f'<span class="chip">{esc(h["horizon"])}</span>')
        if h["slot"]:
            meta.append(f'<span class="chip">{esc(h["slot"])}</span>')
        if h["split_adjusted"]:
            meta.append('<span class="chip">split-adjusted</span>')
        meta_html = f'<div class="chips" style="margin:0 0 10px">{"".join(meta)}</div>' if meta else ""

        items.append(f"""
  <div class="tl-item">
    <div class="tl-head">
      <span class="tl-ord">{_ordinal(i)}</span>
      <span class="tl-date">{esc(h['date'])}</span>
      <span class="tl-time">🕑 {esc(h['time'])}</span>
      <span class="badge-{h['confidence']}">{h['confidence']}</span>
      <span class="tl-price">{money(h['price'], row['currency'])}</span>
      <span class="tl-pnl {pnl_cls}">{pnl_txt}</span>
    </div>
    {meta_html}
    <div class="tl-body thesis">{thesis_html}</div>
    {risk_html}
  </div>""")
    return "".join(items)


def _all_recs_table(row: dict) -> str:
    rows = []
    for i, h in enumerate(row["history"]):
        pnl = h["pnl"]
        cls = "up" if (pnl or 0) > 0 else ("dn" if (pnl or 0) < 0 else "neu")
        txt = f"{'+' if (pnl or 0) > 0 else ''}{pnl:.2f}%" if pnl is not None else "—"
        rows.append(f"""
    <tr>
      <td class="ord">{_ordinal(i)}</td>
      <td><div class="rec-date">{esc(h['date'])}</div>
          <div class="rec-time">🕑 {esc(h['time'])}</div></td>
      <td><b>{money(h['price'], row['currency'])}</b></td>
      <td><span class="badge-{h['confidence']}">{h['confidence']}</span></td>
      <td class="{cls}"><b>{txt}</b></td>
    </tr>""")

    return f"""
<table class="allrecs">
  <thead>
    <tr><th></th><th>Date</th><th>Price</th><th>Confidence</th><th>P&amp;L vs now</th></tr>
  </thead>
  <tbody>{''.join(rows)}</tbody>
</table>"""


def _thesis_panel(row: dict, summary: str | None) -> str:
    """
    One thesis → show it as posted. Several → show the AI synthesis, with the
    originals still available on the timeline below.
    """
    count = row["rec_count"]

    if count == 1:
        h = row["history"][0]
        content = markdown(h["thesis"]) if h["thesis"] else (
            '<div class="no-thesis">No thesis text was captured for this '
            'recommendation. Theses are stored from the moment the ledger went '
            'live — earlier alerts have only their price and date.</div>')
        risk = (f'<div class="tl-risk"><b>Risk:</b> {esc(h["risk"])}</div>'
                if h["risk"] else "")
        return f"""
<div class="panel">
  <div class="panel-head">
    <h2>📄 Thesis</h2>
    <span class="src-tag">As posted to Discord · {esc(h['date'])}</span>
  </div>
  <div class="thesis">{content}</div>
  {risk}
</div>"""

    if summary:
        body = markdown(summary)
        tag = '<span class="ai-tag">AI synthesis</span>'
        note = f'<span class="src-tag">Across {count} recommendations</span>'
    else:
        # No API key configured, or the call failed. The page still works —
        # the individual theses are right below — so this degrades rather than
        # blocking the build.
        body = ('<div class="no-thesis">The combined summary has not been '
                'generated yet. Each individual thesis is shown below.</div>')
        tag = ""
        note = f'<span class="src-tag">{count} recommendations</span>'

    return f"""
<div class="panel">
  <div class="panel-head">
    <h2>🧠 Why this keeps coming up {tag}</h2>
    {note}
  </div>
  <div class="thesis">{body}</div>
</div>"""


def render(row: dict, profile: dict, updated: str, summary: str | None,
           is_trader: bool) -> str:
    ccy = row["currency"]
    cur = row["current"]
    chg = row["day_chg"]

    chg_cls = "up" if (chg or 0) > 0 else ("dn" if (chg or 0) < 0 else "neu")
    chg_txt = (f"{'▲' if (chg or 0) > 0 else '▼'} {'+' if (chg or 0) >= 0 else ''}"
               f"{chg:.2f}%") if chg is not None else "—"

    range_52w = ""
    if row["low_52w"] and row["high_52w"]:
        range_52w = (f'<div class="stat"><div class="lbl">52-week range</div>'
                     f'<div class="val" style="font-size:.95rem">'
                     f'{money(row["low_52w"], ccy)} – {money(row["high_52w"], ccy)}'
                     f'</div></div>')

    entry_label = "First recommended" if not is_trader else "First signal"

    body = f"""
<div class="wrap">
  <a class="backlink" href="../">← {esc(profile['name'])}</a>

  <div class="tk-head">
    <div class="tk-id">
      <div class="tk-sym">{flag(row['region'])} {esc(row['ticker'])}</div>
      <div class="tk-name">{esc(row['name'])}</div>
      <div class="chips">
        {f'<span class="chip">{esc(row["sector"])}</span>' if row['sector'] else ''}
        {f'<span class="chip">{esc(row["exchange"])}</span>' if row['exchange'] else ''}
        <span class="chip">{esc(ccy)}</span>
        <span class="chip">#signals-{esc(profile['discord_role'])}</span>
      </div>
    </div>
    <div class="tk-price">
      <div class="p">{money(cur, ccy)}</div>
      <div class="c {chg_cls}">{chg_txt}</div>
      <div class="price-sub">as of {esc(updated)}</div>
    </div>
  </div>

  <div class="tk-stats">
    <div class="stat"><div class="lbl">Entry</div><div class="val" style="font-size:1.1rem">{money(row['entry'], ccy)}</div></div>
    <div class="stat"><div class="lbl">P&amp;L</div><div class="val">{stat_pct(row['pnl_pct'])}</div></div>
    <div class="stat"><div class="lbl">P&amp;L / share</div><div class="val" style="font-size:1.1rem">{money_signed(row['pnl_abs'], ccy)}</div></div>
    <div class="stat"><div class="lbl">Times recommended</div><div class="val blue">{row['rec_count']}</div></div>
    <div class="stat"><div class="lbl">{entry_label}</div><div class="val" style="font-size:.95rem">{esc(row['signal_date'])}</div></div>
    {range_52w}
  </div>

  {_thesis_panel(row, summary)}

  <div class="panel">
    <div class="panel-head">
      <h2>🔁 All recommendations</h2>
      <span class="src-tag">P&amp;L measured against the current price</span>
    </div>
    {_all_recs_table(row)}
  </div>

  {'<div class="panel"><div class="panel-head"><h2>🗒️ Every thesis, in order</h2>'
   '<span class="src-tag">Exactly as posted to Discord</span></div>'
   + _timeline(row) + '</div>' if row['rec_count'] > 1 else ''}

  <footer>
    Prices via Yahoo Finance · Recommendation prices captured live at the moment each alert fired
    <div class="disclaimer">This is not professional financial advice — always make your own decisions.</div>
  </footer>
</div>
"""
    return page(f"{row['ticker']} — {profile['name']}",
                page_css(TICKER_CSS), body, "", GATE_HTML, GATE_JS, depth=2)
