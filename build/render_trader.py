"""
render_trader.py — The day-trading page for P08 (Swing) and P09 (Momentum).

These two profiles are judged differently from the investing profiles. A name
recommended to a momentum trader is not an open position to be marked to market
months later — it is a call that either worked that day or didn't. So the page:

  * shows only today's recommendations, and resets when the ET date rolls over
  * has a performance button that reveals every day of the month on hover
  * breaks the month into weeks, showing each day's % P/L inside the week
  * carries a month-to-date figure at the top

Return convention: signal price → that same day's close, equal-weighted across
the day's recommendations. Days are chained (compounded) into weeks and months,
because the question being answered is "what if I backed each day's calls, day
after day" — and that rolls yesterday's result into today's stake.

Today is deliberately excluded from the compounded figures until its close is
frozen. A day that is still moving would otherwise keep rewriting the month's
number every time the build ran.
"""

from __future__ import annotations

from datetime import datetime

from .html_util import (esc, flag, horizon_label, money, page, pct_html,
                        risk_class, stat_pct)
from .theme import GATE_HTML, GATE_JS, TRADER_CSS, page_css


def _pct_span(value, big: bool = False) -> str:
    if value is None:
        return '<span class="neu">—</span>'
    cls = "up" if value > 0 else ("dn" if value < 0 else "neu")
    sign = "+" if value > 0 else ""
    return f'<span class="{cls}">{sign}{value:.2f}%</span>'


def _month_nav(months: list[str], active: str, is_archive: bool) -> str:
    """
    Pills linking to every month the profile has history for.

    Without this the page would silently drop a whole month's track record at
    midnight on the 1st, which is exactly when you most want to look back at it.
    """
    if len(months) < 2:
        return ""
    prefix = "../../" if is_archive else ""
    current = months[-1]
    out = []
    for m in reversed(months):
        label = datetime.strptime(m + "-01", "%Y-%m-%d").strftime("%b %Y")
        href = prefix if m == current else f"{prefix}m/{m}/"
        cls = "sort-btn active" if m == active else "sort-btn"
        out.append(f'<a class="{cls}" href="{href}">{label}</a>')
    return f'<div class="sort-bar"><span>Month:</span>{"".join(out)}</div>'


def _today_rows(view: dict, ticker_base: str) -> str:
    rows = view["today_rows"]
    if not rows:
        return ('<tr class="empty-row"><td colspan="7">'
                'No recommendations yet today. They appear here the moment they '
                'are posted to Discord, and the board clears again tomorrow.'
                '</td></tr>')

    out = []
    for r in rows:
        ccy = r["currency"]
        cur = r["current"]
        chg = r["day_chg"]

        if cur is None:
            cur_cell = '<span class="err">—</span>'
        else:
            arrow = "▲" if (chg or 0) > 0 else ("▼" if (chg or 0) < 0 else "")
            cls = "up" if (chg or 0) > 0 else ("dn" if (chg or 0) < 0 else "neu")
            txt = f"{'+' if chg >= 0 else ''}{chg:.2f}%" if chg is not None else ""
            cur_cell = (f'<span class="price-main">{money(cur, ccy)}</span>'
                        f'<div class="price-sub {cls}">{arrow} {txt}</div>')

        # Once the close is frozen the day's result is final; until then the
        # live number is shown but labelled as still open.
        if r["close"] is not None:
            settle = (f'<div class="price-main">{_pct_span(r["close_pnl"])}</div>'
                      f'<div class="price-sub">vs close {money(r["close"], ccy)}</div>')
        else:
            settle = ('<span class="neu">—</span>'
                      '<div class="price-sub">settles at close</div>')

        entry_range = ""
        if r["buy_low"] and r["buy_high"]:
            entry_range = (f'<div class="price-sub">buy {money(r["buy_low"], ccy)}'
                           f'–{money(r["buy_high"], ccy)}</div>')

        out.append(f"""
    <tr>
      <td>
        <a class="ticker-link" href="{ticker_base}{r['ticker'].replace('.', '-')}/">
          <div class="ticker-sym">{esc(r['ticker'])}<span class="go">↗</span></div>
          <div class="ticker-name">{esc(r['name'])}</div>
        </a>
      </td>
      <td><span class="sig-date">🕑 {esc(r['time'])}</span></td>
      <td><span class="badge-{r['confidence']}">{r['confidence']}</span></td>
      <td><span class="price-main">{money(r['signal_price'], ccy)}</span>{entry_range}</td>
      <td>{cur_cell}</td>
      <td class="pnl-col">{_pct_span(r['live_pnl'])}</td>
      <td>{settle}</td>
    </tr>""")
    return "".join(out)


def _archive_rows(view: dict) -> str:
    """Full daily table for a past month, newest first."""
    if not view["daily"]:
        return ('<tr class="empty-row"><td colspan="6">'
                'No recommendations recorded this month.</td></tr>')
    out = []
    for d in reversed(view["daily"]):
        tickers = ", ".join(sorted(set(d["tickers"])))
        out.append(f"""
    <tr>
      <td><span class="sig-date">{d['weekday']} {esc(d['date'])}</span></td>
      <td>{d['n_recs']}</td>
      <td><span class="ticker-name" style="font-size:.8rem">{esc(tickers)}</span></td>
      <td>{_pct_span(d['best'])}</td>
      <td>{_pct_span(d['worst'])}</td>
      <td class="pnl-col">{_pct_span(d['pct'])}</td>
    </tr>""")
    return "".join(out)


def _month_panel_rows(daily: list[dict]) -> str:
    """Per-day rows for the hover panel, newest first."""
    if not daily:
        return '<div class="mp-row"><div class="mp-date neu">No data yet this month</div></div>'

    settled = [abs(d["pct"]) for d in daily if d["pct"] is not None]
    scale = max(settled) if settled else 1.0

    out = []
    for d in reversed(daily):
        pct = d["pct"]
        if pct is None:
            bar = '<div class="mp-bar"></div>'
            pct_html_ = '<div class="mp-pct neu">pending</div>'
        else:
            width = min(abs(pct) / scale * 48, 48) if scale else 0
            colour = "var(--green)" if pct > 0 else "var(--red)"
            side = f"left:50%;width:{width}%" if pct > 0 else f"right:50%;left:auto;width:{width}%"
            bar = f'<div class="mp-bar"><i style="{side};background:{colour}"></i></div>'
            cls = "up" if pct > 0 else ("dn" if pct < 0 else "neu")
            pct_html_ = f'<div class="mp-pct {cls}">{"+" if pct > 0 else ""}{pct:.2f}%</div>'

        out.append(f"""
  <div class="mp-row">
    <div>
      <div class="mp-date">{d['weekday']} {d['date'][8:]}/{d['date'][5:7]}</div>
      <div class="mp-n">{d['n_recs']} rec{'s' if d['n_recs'] != 1 else ''}</div>
    </div>
    {bar}
    {pct_html_}
  </div>""")
    return "".join(out)


def _week_blocks(weeks: list[dict]) -> str:
    if not weeks:
        return ('<div class="week"><div class="week-empty">'
                'No trading days recorded this month yet.</div></div>')

    out = []
    for w in weeks:
        day_rows = []
        for d in w["days"]:
            pct = d["pct"]
            if pct is None:
                cls, txt, row_cls = "neu", "pending", " no-data"
            else:
                cls = "up" if pct > 0 else ("dn" if pct < 0 else "neu")
                txt = f"{'+' if pct > 0 else ''}{pct:.2f}%"
                row_cls = ""
            day_rows.append(f"""
      <div class="day-row{row_cls}">
        <div class="day-name">{d['weekday']} {d['date'][8:]}/{d['date'][5:7]}</div>
        <div class="day-n">×{d['n_recs']}</div>
        <div></div>
        <div class="day-pct {cls}">{txt}</div>
      </div>""")

        total = w["pct"]
        tcls = "up" if (total or 0) > 0 else ("dn" if (total or 0) < 0 else "neu")
        ttxt = f"{'+' if (total or 0) > 0 else ''}{total:.2f}%" if total is not None else "—"
        pending = (f'<span class="pending">{w["pending"]} pending</span>'
                   if w["pending"] else "")

        out.append(f"""
  <div class="week">
    <div class="week-head">
      <div>
        <div class="week-name">{w['label']}{pending}</div>
        <div class="week-range">{w['range']}</div>
      </div>
      <div>
        <div class="week-total {tcls}">{ttxt}</div>
        <div class="week-total-lbl">{w['n_days']} day{'s' if w['n_days'] != 1 else ''} · {w['green']}W / {w['red']}L</div>
      </div>
    </div>
    {''.join(day_rows)}
  </div>""")
    return "".join(out)


SCRIPT = r"""
// The month panel is fixed-positioned and JS-placed so it is never clipped by
// a scrolling ancestor. It stays open on click, which makes it readable on
// touch devices where there is no hover.
var monthPinned = false;

function _placePanel(event){
  var p = document.getElementById('month-panel');
  var w = p.offsetWidth, h = p.offsetHeight;
  var x = event.clientX + 14, y = event.clientY + 14;
  if (x + w > window.innerWidth  - 12) x = Math.max(12, event.clientX - w - 14);
  if (y + h > window.innerHeight - 12) y = Math.max(12, window.innerHeight - h - 12);
  p.style.left = x + 'px';
  p.style.top  = y + 'px';
}

function showMonth(event){
  if (monthPinned) return;
  var p = document.getElementById('month-panel');
  p.style.display = 'block';
  _placePanel(event);
}

function hideMonth(){
  if (monthPinned) return;
  document.getElementById('month-panel').style.display = 'none';
}

function toggleMonth(event){
  event.stopPropagation();
  monthPinned = !monthPinned;
  var p = document.getElementById('month-panel');
  if (monthPinned){ p.style.display = 'block'; _placePanel(event); }
  else { p.style.display = 'none'; }
}

document.addEventListener('click', function(){
  if (monthPinned){
    monthPinned = false;
    document.getElementById('month-panel').style.display = 'none';
  }
});

// The board is scoped to a single ET trading day. If a tab is left open
// overnight the page would keep showing yesterday's names as "today", so it
// reloads once the date rolls over.
(function(){
  var PAGE_DAY = '__TRADING_DAY__';
  setInterval(function(){
    var nowET = new Date().toLocaleDateString('en-CA', {timeZone: 'America/New_York'});
    if (nowET !== PAGE_DAY) location.reload();
  }, 60000);
})();
"""


def render(view: dict, updated: str, market_open: bool,
           months: list[str] | None = None, is_archive: bool = False) -> str:
    p = view["profile"]
    months = months or [view["month"]]
    # An archive page sits two levels deeper (/role/m/YYYY-MM/), so its links
    # back to the channel and out to ticker pages need to climb further.
    back = "../../../" if is_archive else "../"
    ticker_base = "../../" if is_archive else ""
    mtd = view["mtd_pct"]
    mtd_cls = "up" if (mtd or 0) > 0 else ("dn" if (mtd or 0) < 0 else "neu")
    mtd_txt = f"{'+' if (mtd or 0) > 0 else ''}{mtd:.2f}%" if mtd is not None else "—"

    dot = "live-dot" if market_open else "live-dot closed"
    dot_label = "Market open" if market_open else "Market closed"

    pending_note = (f'<span class="pending">{view["pending"]} awaiting close</span>'
                    if view["pending"] else "")

    # The live board belongs to today only. On an archive month there is no
    # "today", so the section is replaced by the month's full daily table —
    # otherwise the page would show an empty board next to real history and
    # look broken.
    if is_archive:
        today_section = f"""
  <div class="section">
    <div class="section-title">
      <h2>📓 Every day in {esc(view['month_label'])}</h2>
      <span class="hint">Signal price → same-day close, averaged across that day's names</span>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Date</th><th>Recs</th><th>Tickers</th><th>Best</th><th>Worst</th><th>Day P/L</th></tr></thead>
        <tbody>{_archive_rows(view)}</tbody>
      </table>
    </div>
  </div>"""
    else:
        today_section = f"""
  <div class="section">
    <div class="section-title">
      <h2><span class="{dot}"></span> Today · {esc(view['today'])}</h2>
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
        <span class="hint">{dot_label} · board clears at midnight ET</span>
        <button class="perf-btn"
                onmouseenter="showMonth(event)" onmousemove="_placePanel(event)"
                onmouseleave="hideMonth()" onclick="toggleMonth(event)">
          📊 Performance by day
        </button>
      </div>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Ticker</th><th>Time</th><th>Conf</th><th>Signal Price</th>
            <th>Current</th><th>Live P/L</th><th>Day result</th>
          </tr>
        </thead>
        <tbody>{_today_rows(view, ticker_base)}</tbody>
      </table>
    </div>
  </div>"""

    body = f"""
<div id="month-panel">
  <div class="mp-title">
    <span>{esc(view['month_label'])} — daily P/L</span>
    <span>{view['mtd_days']} day{'s' if view['mtd_days'] != 1 else ''}</span>
  </div>
  {_month_panel_rows(view['daily'])}
</div>

<div class="wrap">
  <a class="backlink" href="{back}">← All channels</a>
  <header>
    <div>
      <h1>{esc(p['name'])}</h1>
      <p>{esc(p['description'])}</p>
      <div class="chips">
        <span class="chip">{esc(p['id'])}</span>
        <span class="chip">#signals-{esc(p['discord_role'])}</span>
        <span class="chip {risk_class(p['risk_tolerance'])}">Risk {p['risk_tolerance']}/10</span>
        <span class="chip">{esc(horizon_label(p['investment_horizon_months']))}</span>
        <span class="chip">Max {p['max_recs_per_day']}/day</span>
      </div>
    </div>
    <div class="updated">⏱ Prices as of {esc(updated)}</div>
  </header>

  {_month_nav(months, view['month'], is_archive)}

  <div class="mtd section">
    <div class="mtd-left">
      <div class="mtd-lbl">Month to date · {esc(view['month_label'])}</div>
      <div class="mtd-val {mtd_cls}">{mtd_txt}</div>
      <div class="mtd-sub">Compounded across {view['mtd_days']} settled trading day{'s' if view['mtd_days'] != 1 else ''}
        · {view['total_recs']} recommendation{'s' if view['total_recs'] != 1 else ''}{pending_note}</div>
    </div>
    <div class="mtd-right">
      <div class="mtd-stat"><div class="v green">{view['mtd_green']}</div><div class="l">Green days</div></div>
      <div class="mtd-stat"><div class="v red">{view['mtd_red']}</div><div class="l">Red days</div></div>
      <div class="mtd-stat"><div class="v">{_pct_span(view['mtd_best'])}</div><div class="l">Best day</div></div>
      <div class="mtd-stat"><div class="v">{_pct_span(view['mtd_worst'])}</div><div class="l">Worst day</div></div>
    </div>
  </div>

  {today_section}

  <div class="section">
    <div class="section-title">
      <h2>📅 Weekly breakdown</h2>
      <span class="hint">Each day = average across that day's recommendations, signal price → same-day close</span>
    </div>
    <div class="weeks">{_week_blocks(view['weeks'])}</div>
  </div>

  <footer>
    Every recommendation posted to <code>#signals-{esc(p['discord_role'])}</code> ·
    Prices via Yahoo Finance · Daily results settle on the official close and are then frozen
    <div class="disclaimer">This is not professional financial advice — always make your own decisions.</div>
  </footer>
</div>
"""
    return page(f"{p['name']} — Signal Watchlist",
                page_css(TRADER_CSS), body,
                SCRIPT.replace("__TRADING_DAY__", view["today"]),
                GATE_HTML, GATE_JS, depth=1)
