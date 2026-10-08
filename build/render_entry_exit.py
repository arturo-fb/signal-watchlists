"""
render_entry_exit.py — The "Entries & exits" tab on every profile page.

The page is static (GitHub Pages), so nothing here can write: Skip and Sold
are pressed on the Discord alert (or /sold, /skip), the bot records it, and
the next build — within a few minutes — shows it here.
"""

from __future__ import annotations

from datetime import datetime

from .html_util import attr, esc, flag, money, pct_html, stat_pct

CSS = """
/* ── Tabs ──────────────────────────────────────────────────────────────── */
.tabs{display:flex;gap:8px;margin:0 0 18px;border-bottom:1px solid var(--border);flex-wrap:wrap}
.tab{background:none;border:none;border-bottom:2px solid transparent;color:var(--sub);
  font:600 .9rem/1 inherit;font-family:inherit;padding:10px 14px 12px;cursor:pointer;
  display:inline-flex;align-items:center;gap:8px;margin-bottom:-1px}
.tab:hover{color:var(--text)}
.tab.active{color:var(--text);border-bottom-color:var(--accent)}
.tab .count{font-size:.7rem;background:var(--surface2);border:1px solid var(--border);
  border-radius:99px;padding:2px 8px;color:var(--sub)}
.tab.active .count{color:var(--accent);border-color:rgba(79,142,247,.4)}
.tab .count.hot{color:var(--yellow);border-color:rgba(245,158,11,.45)}
.tabpane[hidden]{display:none}

/* ── Entries & exits ───────────────────────────────────────────────────── */
.ee-rules{font-size:.76rem;color:var(--sub);background:var(--surface);border:1px solid var(--border);
  border-radius:10px;padding:10px 14px;margin-bottom:14px;line-height:1.55}
.ee-rules b{color:var(--text);font-weight:600}
.seg{display:inline-flex;border:1px solid var(--border);border-radius:8px;overflow:hidden}
.seg button{background:var(--surface);border:none;color:var(--sub);font:600 .76rem inherit;
  font-family:inherit;padding:6px 12px;cursor:pointer;border-right:1px solid var(--border)}
.seg button:last-child{border-right:none}
.seg button.active{background:rgba(79,142,247,.12);color:var(--accent)}
.ee-h{font-size:.78rem;text-transform:uppercase;letter-spacing:.5px;color:var(--sub);
  margin:22px 0 10px;display:flex;align-items:baseline;gap:10px}
.ee-h .n{color:var(--text);font-weight:700}
.ee-h .hint{text-transform:none;letter-spacing:0;font-size:.74rem;color:var(--muted)}
.cd{font-weight:700;font-size:.92rem;font-variant-numeric:tabular-nums}
.cd-sub{font-size:.7rem;color:var(--sub);margin-top:2px}
.cd.sell{color:var(--yellow)} .cd.over{color:var(--red)} .cd.ok{color:var(--text)}
.bar{height:4px;border-radius:99px;background:var(--surface2);margin-top:6px;width:110px;overflow:hidden}
.bar i{display:block;height:100%;background:var(--accent);border-radius:99px}
.bar.sell i{background:var(--yellow)} .bar.over i{background:var(--red)}
.wb{display:inline-block;font-size:.66rem;font-weight:700;padding:2px 8px;border-radius:99px;
  margin:2px 4px 2px 0;white-space:nowrap}
.wb.sell{background:rgba(245,158,11,.12);border:1px solid rgba(245,158,11,.4);color:var(--yellow)}
.wb.over,.wb.stop{background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.4);color:var(--red)}
.wb.quiet{background:rgba(245,158,11,.08);border:1px dashed rgba(245,158,11,.5);color:var(--yellow)}
.wb.info{background:var(--surface2);border:1px solid var(--border);color:var(--sub)}
.wb.ok{background:rgba(34,197,94,.08);border:1px solid rgba(34,197,94,.3);color:var(--green)}
.ee-empty{color:var(--muted);font-size:.84rem;text-align:center;padding:28px 14px}
details.ee-more{margin-top:18px}
details.ee-more summary{cursor:pointer;color:var(--sub);font-size:.8rem;padding:6px 0}
details.ee-more summary:hover{color:var(--text)}
.ee-note{font-size:.74rem;color:var(--muted);margin-top:12px}
"""

SCRIPT = r"""
// ── Tabs (hash-routed so #entries is linkable) ──────────────────────────────
function showTab(name){
  document.querySelectorAll('.tab').forEach(function(t){
    t.classList.toggle('active', t.dataset.tab === name);
  });
  document.querySelectorAll('.tabpane').forEach(function(p){
    p.hidden = p.id !== 'pane-' + name;
  });
  if (history.replaceState) history.replaceState(null, '', name === 'recs' ? location.pathname : '#' + name);
}
document.querySelectorAll('.tab').forEach(function(t){
  t.addEventListener('click', function(){ showTab(t.dataset.tab); });
});
if (location.hash === '#entries') showTab('entries');

// ── Entries & exits filters + stats ─────────────────────────────────────────
var EE_MKT = 'all';
function eeMarket(m){
  EE_MKT = m;
  document.querySelectorAll('#ee-mkt button').forEach(function(b){
    b.classList.toggle('active', b.dataset.m === m);
  });
  eeApply();
}
function _fmt(v, d){ return (v > 0 ? '+' : '') + v.toFixed(d === undefined ? 2 : d) + '%'; }
function _cls(v){ return v > 0 ? 'green' : (v < 0 ? 'red' : 'blue'); }
function eeApply(){
  var sec = document.getElementById('ee-sector');
  sec = sec ? sec.value : '';
  ['ee-open','ee-closed','ee-skipped','ee-slow'].forEach(function(id){
    var body = document.getElementById(id);
    if (!body) return;
    var shown = 0;
    body.querySelectorAll('tr[data-mkt]').forEach(function(r){
      var ok = (EE_MKT === 'all' || r.dataset.mkt === EE_MKT) && (!sec || r.dataset.sector === sec);
      r.style.display = ok ? '' : 'none';
      if (ok) shown++;
    });
    var empty = body.querySelector('.ee-filter-empty');
    if (empty) empty.style.display = shown ? 'none' : '';
    var cnt = document.getElementById(id + '-n');
    if (cnt) cnt.textContent = shown;
  });
  // Stats from the closed trades that survive the filter
  var rets = [], exc = [], days = [], wins = 0;
  document.querySelectorAll('#ee-closed tr[data-mkt]').forEach(function(r){
    if (r.style.display === 'none') return;
    var v = parseFloat(r.dataset.ret);
    if (!isNaN(v)){ rets.push(v); if (v > 0) wins++; }
    var e = parseFloat(r.dataset.excess); if (!isNaN(e)) exc.push(e);
    var d = parseFloat(r.dataset.days); if (!isNaN(d)) days.push(d);
  });
  var avg = function(a){ return a.reduce(function(x, y){ return x + y; }, 0) / a.length; };
  var med = function(a){ var s = a.slice().sort(function(x, y){ return x - y; }), m = Math.floor(s.length / 2);
                         return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
  var set = function(id, html){ var el = document.getElementById(id); if (el) el.innerHTML = html; };
  set('st-n', rets.length);
  set('st-avg', rets.length ? '<span class="' + _cls(avg(rets)) + '">' + _fmt(avg(rets)) + '</span>' : '—');
  set('st-med', rets.length ? '<span class="' + _cls(med(rets)) + '">' + _fmt(med(rets)) + '</span>' : '—');
  set('st-win', rets.length ? Math.round(100 * wins / rets.length) + '%' : '—');
  set('st-days', days.length ? avg(days).toFixed(1) : '—');
  set('st-exc', exc.length ? '<span class="' + _cls(avg(exc)) + '">' + _fmt(avg(exc)) + '</span>' : '—');
  var unr = [];
  document.querySelectorAll('#ee-open tr[data-mkt]').forEach(function(r){
    if (r.style.display === 'none') return;
    var v = parseFloat(r.dataset.unreal); if (!isNaN(v)) unr.push(v);
  });
  set('st-open', unr.length ? unr.length + ' · <span class="' + _cls(avg(unr)) + '">' + _fmt(avg(unr)) + '</span>'
                            : document.querySelectorAll('#ee-open tr[data-mkt]').length ? '—' : '0');
}
if (document.getElementById('ee-open')) eeApply();
"""


def _d(s: str | None) -> str:
    if not s:
        return "—"
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").strftime("%b %-d")
    except ValueError:
        return s


def _dw(s: str | None) -> str:
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").strftime("%a %b %-d")
    except Exception:
        return s or "—"


def _ticker_cell(r: dict) -> str:
    sub = " · ".join(x for x in (r.get("sector") if r.get("sector") != "—" else "", r.get("industry")) if x)
    return (f'<div class="ticker-sym">{flag(r["market"])} {esc(r["ticker"])}</div>'
            f'<div class="ticker-name">{esc(r.get("name") or "")}</div>'
            + (f'<div><span class="badge-sector">{esc(sub)}</span></div>' if sub else ""))


def _headsup(r: dict) -> str:
    out = []
    fh = r.get("pct_from_52w_high")
    if fh is not None:
        if fh >= -1:
            out.append('<span class="wb info" title="At signal time">At 52w high</span>')
        elif fh >= -5:
            out.append(f'<span class="wb info" title="At signal time">{abs(fh):.1f}% below 52w high</span>')
        else:
            out.append(f'<span class="wb info" title="At signal time">{abs(fh):.0f}% below 52w high</span>')
    if r.get("above_buy_range"):
        out.append('<span class="wb info" title="Signal price was above the buy range">Above buy range</span>')
    return "".join(out)


def _row_attrs(r: dict, **extra) -> str:
    bits = [f'data-mkt="{esc(r["market"])}"', f'data-sector="{esc(r.get("sector") or "—")}"']
    for k, v in extra.items():
        bits.append(f'data-{k}="{"" if v is None else v}"')
    return " ".join(bits)


def _open_row(r: dict) -> str:
    ccy = r.get("currency") or "USD"
    hold = r["hold_days"] or 5
    held = r["days_held"]
    if r["state"] == "pending":
        cd = f'<div class="cd ok">Buys at the open</div><div class="cd-sub">{_dw(r["entry_date"])}</div>'
        bar_cls, frac = "", 0
    elif r["state"] == "sell_today":
        cd = f'<div class="cd sell">Sell today</div><div class="cd-sub">day {hold} of {hold}</div>'
        bar_cls, frac = "sell", 1
    elif r["state"] == "overdue":
        over = -r["days_left"]
        cd = (f'<div class="cd over">Held {over} day{"s" if over != 1 else ""} past</div>'
              f'<div class="cd-sub">sell-by was {_dw(r["sell_by"])}</div>')
        bar_cls, frac = "over", 1
    else:
        left = r["days_left"]
        cd = (f'<div class="cd ok">{left} day{"s" if left != 1 else ""} left</div>'
              f'<div class="cd-sub">sell at close {_dw(r["sell_by"])}</div>')
        bar_cls, frac = "", min(1, held / hold) if hold else 0
    cd += f'<div class="bar {bar_cls}"><i style="width:{int(frac * 100)}%"></i></div>'

    src = {"signal": "signal price", "open": "open", "pending_open": "provisional",
           "manual": "edited"}.get(r.get("entry_price_source"), "")
    entry = (f'<span class="price-main">{money(r["entry_price"], ccy)}</span>'
             f'<div class="price-sub">{_d(r["entry_date"])} · {src}</div>')
    now = (f'<span class="price-main">{money(r["current"], ccy)}</span>'
           f'<div class="price-sub">{pct_html(r["unreal"])} since entry</div>'
           if r.get("current") is not None else '<span class="err">—</span>')
    warn = "".join(f'<span class="wb {k}">{esc(t)}</span>' for k, t in r["warnings"])
    if r.get("holding_ack_date") and r["state"] == "overdue":
        warn += '<span class="wb ok">Holding (confirmed)</span>'
    quiet = r["quiet"]
    q_cls = "dn" if quiet >= 4 else "neu"
    recs = " · ".join(_d(x) for x in r["rec_dates_list"])
    return f"""
    <tr {_row_attrs(r, unreal=r.get('unreal'))}>
      <td>{_ticker_cell(r)}</td>
      <td>{entry}</td>
      <td>{now}</td>
      <td>{cd}</td>
      <td><span class="{q_cls}" style="font-weight:700">{quiet}</span>
          <div class="price-sub">last rec {_d(r.get('last_rec'))}</div></td>
      <td><span class="price-main" style="font-size:.85rem">{money(r.get('stop_price'), ccy)}</span>
          <div class="price-sub">−15%</div></td>
      <td style="white-space:normal;min-width:180px">{warn}{_headsup(r)}
          <div class="price-sub">recs {recs}</div></td>
    </tr>"""


def _closed_row(r: dict) -> str:
    ccy = r.get("currency") or "USD"
    timing = {"early": ("info", "Sold early"), "on_time": ("ok", "On the sell day"),
              "late": ("quiet", "Held past sell day")}.get(r.get("exit_timing"), ("info", ""))
    bench_bits = [f"{'+' if v >= 0 else ''}{v:.2f}% {s}" for s, v in (r.get("bench") or {}).items()
                  if v is not None]
    bench_title = "Benchmark over the same dates: " + ", ".join(bench_bits) if bench_bits else ""
    return f"""
    <tr {_row_attrs(r, ret=r.get('ret'), excess=r.get('excess'), days=r.get('days_held'))}>
      <td>{_ticker_cell(r)}</td>
      <td><span class="price-main">{money(r['entry_price'], ccy)}</span>
          <div class="price-sub">{_d(r['entry_date'])}</div></td>
      <td><span class="price-main">{money(r['exit_price'], ccy)}</span>
          <div class="price-sub">{_d(r['exit_date'])}</div></td>
      <td class="pnl-col">{pct_html(r.get('ret'))}</td>
      <td>{r.get('days_held') if r.get('days_held') is not None else '—'}
          <div class="price-sub">of {r.get('hold_days')}</div></td>
      <td><span class="wb {timing[0]}">{timing[1]}</span></td>
      <td title="{esc(bench_title)}">{pct_html(r.get('excess'))}
          <div class="price-sub">vs {'S&amp;P 500' if r['market'] == 'us' else 'STOXX 600'}</div></td>
    </tr>"""


def _skipped_row(r: dict) -> str:
    ccy = r.get("currency") or "USD"
    return f"""
    <tr {_row_attrs(r)}>
      <td>{_ticker_cell(r)}</td>
      <td>{money(r['entry_price'], ccy)}<div class="price-sub">{_d(r['entry_date'])}</div></td>
      <td>{pct_html(r.get('would_be'))}<div class="price-sub">since entry, if taken</div></td>
    </tr>"""


def _slow_row(r: dict) -> str:
    recs = " → ".join(_d(x) for x in r["rec_dates_list"])
    return f"""
    <tr data-mkt="{esc(r['market'])}" data-sector="{esc(r.get('sector') or '—')}">
      <td><div class="ticker-sym">{flag(r['market'])} {esc(r['ticker'])}</div>
          <div class="ticker-name">{esc(r.get('name') or '')}</div></td>
      <td>{recs}</td>
      <td>{r.get('gap')} scan days</td>
      <td>{pct_html(r.get('since'))}<div class="price-sub">since the ×3</div></td>
    </tr>"""


def _table(body_id: str, heads: list[str], rows: str, empty: str) -> str:
    th = "".join(f"<th>{h}</th>" for h in heads)
    n = len(heads)
    return f"""
  <div class="table-wrap"><table>
    <thead><tr>{th}</tr></thead>
    <tbody id="{body_id}">{rows}
      <tr class="ee-filter-empty" style="display:none"><td colspan="{n}" class="ee-empty">Nothing matches this filter.</td></tr>
      {'' if rows.strip() else f'<tr><td colspan="{n}" class="ee-empty">{empty}</td></tr>'}
    </tbody>
  </table></div>"""


def tab_bar(n_open: int, n_alert: int) -> str:
    hot = " hot" if n_alert else ""
    return f"""
  <div class="tabs" role="tablist">
    <button class="tab active" data-tab="recs" role="tab">📋 Recommendations</button>
    <button class="tab" data-tab="entries" role="tab">🎯 Entries &amp; exits
      <span class="count{hot}" title="open positions">{n_open} open</span></button>
  </div>"""


def section(ee: dict, profile: dict) -> str:
    st = ee["stats"]
    sector_opts = "".join(f'<option value="{esc(s)}">{esc(s)}</option>' for s in ee["sectors"])
    open_html = "".join(_open_row(r) for r in ee["open"])
    closed_html = "".join(_closed_row(r) for r in ee["closed"])
    skipped_html = "".join(_skipped_row(r) for r in ee["skipped"])
    slow_html = "".join(_slow_row(r) for r in ee["slow"])
    show_mkt = len(profile.get("regions", [])) > 1

    return f"""
  <div class="ee-rules">
    <b>Entry</b> when a stock gets its 3rd rec within 3 scan days of the 2nd (the count restarts after 10 quiet scan days) ·
    <b>Exit</b> at the close of trading day 5 (Europe: day 3) · <b>−15%</b> disaster stop, no tight or trailing stops ·
    <b>Flag</b> anything held past the sell day once it goes 4 scan days with no new rec.
    Performance counts only trades marked <b>Sold</b> in Discord, equal-weighted, from entry to your exit price.
  </div>

  <div class="filter-bar">
    {'<span>Market:</span><div class="seg" id="ee-mkt"><button data-m="all" class="active" onclick="eeMarket(&quot;all&quot;)">All</button><button data-m="us" onclick="eeMarket(&quot;us&quot;)">🇺🇸 US</button><button data-m="europe" onclick="eeMarket(&quot;europe&quot;)">🇪🇺 Europe</button></div>' if show_mkt else ''}
    <span>Sector:</span>
    <select id="ee-sector" onchange="eeApply()"><option value="">All sectors</option>{sector_opts}</select>
  </div>

  <div class="summary">
    <div class="stat"><div class="lbl">Closed trades</div><div class="val blue" id="st-n">{st['n']}</div></div>
    <div class="stat"><div class="lbl">Avg return / trade</div><div class="val" id="st-avg">{stat_pct(st['avg'])}</div></div>
    <div class="stat"><div class="lbl">Median</div><div class="val" id="st-med">{stat_pct(st['median'])}</div></div>
    <div class="stat"><div class="lbl">Win rate</div><div class="val" id="st-win">{'—' if st['win'] is None else str(st['win']) + '%'}</div></div>
    <div class="stat"><div class="lbl">Avg days held</div><div class="val" id="st-days">{'—' if st['avg_days'] is None else st['avg_days']}</div></div>
    <div class="stat"><div class="lbl">Avg vs market</div><div class="val" id="st-exc">{stat_pct(st['avg_excess'])}</div></div>
    <div class="stat"><div class="lbl">Open · unrealized</div><div class="val" id="st-open">{len(ee['open'])}</div></div>
  </div>

  <div class="ee-h">Open positions <span class="n" id="ee-open-n">{len(ee['open'])}</span>
    <span class="hint">Countdowns are in trading days and refresh with every site build.</span></div>
  {_table('ee-open', ['Ticker', 'Entry', 'Now', 'Countdown', 'Quiet scan days', 'Stop', 'Warnings'],
          open_html, 'No open positions. A new one opens automatically the moment a stock qualifies.')}

  <div class="ee-h">Closed trades <span class="n" id="ee-closed-n">{len(ee['closed'])}</span>
    <span class="hint">Your actual exits. Hover “vs market” for both benchmarks.</span></div>
  {_table('ee-closed', ['Ticker', 'Entry', 'Exit', 'Return', 'Days held', 'Timing', 'vs market'],
          closed_html, 'No closed trades yet. Press Sold on a Discord alert and it lands here.')}

  <details class="ee-more">
    <summary>Skipped signals (<span id="ee-skipped-n">{len(ee['skipped'])}</span>) — not taken, excluded from performance</summary>
    {_table('ee-skipped', ['Ticker', 'Entry', 'Since'], skipped_html, 'None skipped.')}
  </details>
  <details class="ee-more">
    <summary>Slow ×3s (<span id="ee-slow-n">{len(ee['slow'])}</span>) — 3rd rec came 4–10 scan days after the 2nd, so no entry</summary>
    {_table('ee-slow', ['Ticker', 'Recs', '×2 → ×3', 'Since'], slow_html,
            'None yet. Tracked here so the slow-×3 filter can be rechecked as data comes in.')}
  </details>
  <p class="ee-note">Mark trades from the Discord alert (Sold / Skip / Still holding) or with /sold, /skip, /positions.
    This page updates within a few minutes. Tracking started fresh on go-live; the Recommendations tab keeps the full history.</p>
"""


def alert_count(ee: dict) -> int:
    return sum(1 for r in ee["open"] if r["warnings"])
