"""
render_investor.py — The watchlist page for the eight investing profiles
(P01–P07, P10).

Same layout as the watchlist you already use — entry price, live price, P&L,
and the Recs badge with its hover breakdown — with two additions:

  * the recommendation-count filter (>=, >, <=, <, = X)
  * every ticker links through to its own detail page

The date filter re-anchors: pick a period and the entry price becomes the first
recommendation *inside* that window, with P&L recomputed from it. Otherwise a
name first flagged in June would keep showing its June entry while you were
looking at August, which reads as a performance claim for a trade you never had.
"""

from __future__ import annotations

from .html_util import (attr, esc, flag, horizon_label, markdown, money,
                        money_signed, pct_html, page, risk_class, stat_pct)
from .theme import GATE_HTML, GATE_JS, PASSPHRASE, TICKER_CSS, page_css


def _recs_cell(row: dict) -> str:
    """The ×N badge plus the JSON payload its tooltip is built from."""
    history = row["history"]
    count = len(history)
    if not count:
        return '<span class="neu">—</span>'

    ordinals = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩",
                "⑪", "⑫", "⑬", "⑭", "⑮"]
    payload = []
    for i, h in enumerate(history):
        pnl = h["pnl"]
        payload.append({
            "ord": ordinals[i] if i < len(ordinals) else f"#{i+1}",
            "date": h["date"],
            "time": h["time"],
            "price": money(h["price"], row["currency"]),
            "conf": h["confidence"],
            "conf_cls": f"badge-{h['confidence']}",
            "pnl_str": f"{'+' if pnl >= 0 else ''}{pnl:.2f}%" if pnl is not None else "—",
            "pnl_cls": "up" if (pnl or 0) > 0 else ("dn" if (pnl or 0) < 0 else "neu"),
        })

    badge = "recs-1" if count == 1 else ("recs-2" if count == 2 else "recs-3plus")
    return (f'<div class="recs-badge {badge}" data-recs="{attr(payload)}" '
            f'onmouseenter="showRecs(this,event)" onmouseleave="hideRecs()" '
            f'onclick="toggleRecs(this,event)">&#215;{count}</div>')


def _row_html(row: dict, ticker_href: str) -> str:
    cur = row["current"]
    chg = row["day_chg"]
    entry = row["entry"]
    ccy = row["currency"]

    if cur is None:
        cur_cell = '<span class="err">—</span>'
    else:
        arrow = "▲" if (chg or 0) > 0 else ("▼" if (chg or 0) < 0 else "")
        cls = "up" if (chg or 0) > 0 else ("dn" if (chg or 0) < 0 else "neu")
        chg_txt = f"{'+' if chg >= 0 else ''}{chg:.2f}%" if chg is not None else ""
        cur_cell = (f'<span class="price-main">{money(cur, ccy)}</span>'
                    f'<div class="price-sub {cls}">{arrow} {chg_txt}</div>')

    adj = " · split-adj" if row["split_adjusted"] else ""
    entry_cell = (f'<span class="price-main">{money(entry, ccy)}</span>'
                  f'<div class="price-sub">Signal entry{adj}</div>') if entry else "—"

    date_cell = (f'<span class="sig-date">{esc(row["signal_date"])}</span>'
                 f'<div class="sig-time">🕑 {esc(row["signal_time"])}</div>')

    abs_pnl = row["pnl_abs"]
    if abs_pnl is not None:
        cls = "up" if abs_pnl > 0 else ("dn" if abs_pnl < 0 else "neu")
        abs_cell = f'<span class="{cls}">{money_signed(abs_pnl, ccy)}</span>'
    else:
        abs_cell = "—"

    # Payload for client-side re-anchoring when a date range is applied.
    hist = [{"d": h["date"], "t": h["time"], "p": h["price"]}
            for h in row["history"] if h["price"] is not None]

    return f"""
    <tr data-pnl="{row['pnl_pct'] if row['pnl_pct'] is not None else 999}"
        data-date="{esc(row['signal_date'])}"
        data-recs="{row['rec_count']}"
        data-recdates="{esc(','.join(row['rec_dates']))}"
        data-rechist="{attr(hist)}"
        data-curprice="{cur if cur is not None else ''}"
        data-ccy="{esc(ccy)}">
      <td>
        <a class="ticker-link" href="{ticker_href}">
          <div class="ticker-sym">{flag(row['region'])} {esc(row['ticker'])}<span class="go">↗</span></div>
          <div class="ticker-name">{esc(row['name'])}</div>
          <div><span class="badge-sector">{esc(row['sector'] or row['exchange'] or '—')}</span></div>
        </a>
      </td>
      <td><span class="badge-{row['confidence']}">{row['confidence']}</span></td>
      <td>{entry_cell}</td>
      <td>{date_cell}</td>
      <td>{cur_cell}</td>
      <td class="pnl-col">{pct_html(row['pnl_pct'])}</td>
      <td>{abs_cell}</td>
      <td>{_recs_cell(row)}</td>
    </tr>"""


SCRIPT = r"""
// ── Sort ────────────────────────────────────────────────────────────────────
var SORT_KEYS = ['pnl-desc','pnl-asc','date-desc','date-asc','recs-desc','recs-asc'];

function sortBy(key, dir){
  SORT_KEYS.forEach(function(id){
    var el = document.getElementById('btn-' + id);
    if (el) el.classList.remove('active');
  });
  var active = document.getElementById('btn-' + key + '-' + dir);
  if (active) active.classList.add('active');

  var body = document.getElementById('tbl-body');
  var rows = Array.prototype.slice.call(body.querySelectorAll('tr[data-pnl]'));
  rows.sort(function(a, b){
    var av, bv;
    if (key === 'pnl'){
      av = parseFloat(a.dataset.pnl); bv = parseFloat(b.dataset.pnl);
      // 999 is the "no price available" sentinel — always sink those rows to
      // the bottom regardless of direction, so an unpriced ticker never looks
      // like the best or worst performer.
      if (av === 999) return 1;
      if (bv === 999) return -1;
    } else if (key === 'recs'){
      av = parseInt(a.dataset.recs, 10); bv = parseInt(b.dataset.recs, 10);
    } else {
      av = a.dataset.date; bv = b.dataset.date;
      return dir === 'desc' ? bv.localeCompare(av) : av.localeCompare(bv);
    }
    return dir === 'desc' ? bv - av : av - bv;
  });
  rows.forEach(function(r){ body.appendChild(r); });
}

// ── Formatting helpers (mirror the Python side) ─────────────────────────────
function _pctHtml(v){
  if (v === null || v === undefined || isNaN(v)) return '<span class="neu">—</span>';
  var cls = v > 0 ? 'up' : (v < 0 ? 'dn' : 'neu');
  return '<span class="' + cls + '">' + (v > 0 ? '+' : '') + v.toFixed(2) + '%</span>';
}
function _money(v, ccy){
  if (v === null || v === undefined || isNaN(v)) return '—';
  if (ccy === 'GBX') return Math.round(v).toLocaleString() + 'p';
  var sym = {USD:'$', EUR:'€', GBP:'£', CHF:'CHF '}[ccy] || '';
  return sym + v.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
}

// Re-anchor a row to the first recommendation inside [from, to] and recompute
// its P&L against the live price.
function _reanchor(row, from, to){
  var hist = JSON.parse(row.dataset.rechist || '[]');
  var cur  = parseFloat(row.dataset.curprice);
  var ccy  = row.dataset.ccy || 'USD';
  var inRange = hist.filter(function(h){
    return (!from || h.d >= from) && (!to || h.d <= to);
  });
  var cells = row.querySelectorAll('td');
  if (!inRange.length) return;

  var anchor = inRange[0];
  var pnl = (!isNaN(cur) && anchor.p) ? ((cur - anchor.p) / anchor.p * 100) : null;

  cells[2].innerHTML = '<span class="price-main">' + _money(anchor.p, ccy) + '</span>' +
                       '<div class="price-sub">Entry in range</div>';
  cells[3].innerHTML = '<span class="sig-date">' + anchor.d + '</span>' +
                       (anchor.t ? '<div class="sig-time">🕑 ' + anchor.t + '</div>' : '');
  cells[5].innerHTML = _pctHtml(pnl);
  if (pnl !== null){
    var abs = cur - anchor.p;
    var cls = abs > 0 ? 'up' : (abs < 0 ? 'dn' : 'neu');
    cells[6].innerHTML = '<span class="' + cls + '">' + (abs > 0 ? '+' : '−') +
                         _money(Math.abs(abs), ccy) + '</span>';
  }
  // Count only the recommendations inside the window, so the badge agrees with
  // what the filter is showing.
  var badge = cells[7].querySelector('.recs-badge');
  if (badge){
    badge.textContent = '×' + inRange.length;
    badge.className = 'recs-badge ' + (inRange.length === 1 ? 'recs-1' :
                      (inRange.length === 2 ? 'recs-2' : 'recs-3plus'));
  }
  row.dataset.liveRecs = inRange.length;
  row.dataset.pnl = (pnl === null ? 999 : pnl);
}

function _restore(row){
  row.innerHTML = row.dataset.original;
  row.dataset.pnl = row.dataset.originalPnl;
  row.dataset.liveRecs = row.dataset.recs;
}

// ── Combined filter: period + recommendation count ──────────────────────────
function applyFilter(){
  var from = document.getElementById('date-from').value;
  var to   = document.getElementById('date-to').value;
  var op   = document.getElementById('recs-op').value;
  var xRaw = document.getElementById('recs-x').value;
  var x    = xRaw === '' ? null : parseInt(xRaw, 10);

  var rows = Array.prototype.slice.call(
    document.getElementById('tbl-body').querySelectorAll('tr[data-pnl]'));
  var shown = 0, pnls = [], wins = 0, losses = 0;

  rows.forEach(function(row){
    _restore(row);

    // Period: a row survives if ANY of its recommendation dates lands in range,
    // so a name re-recommended this week still appears even though it was first
    // flagged months ago.
    var dates = (row.dataset.recdates || '').split(',').filter(Boolean);
    var inPeriod = !from && !to ? true : dates.some(function(d){
      return (!from || d >= from) && (!to || d <= to);
    });

    if (inPeriod && (from || to)) _reanchor(row, from, to);

    var count = parseInt(row.dataset.liveRecs || row.dataset.recs, 10);
    var passCount = true;
    if (x !== null && !isNaN(x)){
      switch (op){
        case 'gte': passCount = count >= x; break;
        case 'gt':  passCount = count >  x; break;
        case 'lte': passCount = count <= x; break;
        case 'lt':  passCount = count <  x; break;
        case 'eq':  passCount = count === x; break;
      }
    }

    var visible = inPeriod && passCount;
    row.style.display = visible ? '' : 'none';
    if (visible){
      shown++;
      var p = parseFloat(row.dataset.pnl);
      if (!isNaN(p) && p !== 999){
        pnls.push(p);
        if (p > 0) wins++; else losses++;
      }
    }
  });

  _renderFilterState(shown, rows.length, pnls, wins, losses, from, to, op, x);
}

function _renderFilterState(shown, total, pnls, wins, losses, from, to, op, x){
  var active = !!(from || to || (x !== null && !isNaN(x)));
  var countEl = document.getElementById('filter-count');
  var statsEl = document.getElementById('filter-stats');

  if (!active){
    countEl.textContent = '';
    statsEl.style.display = 'none';
    document.getElementById('empty-msg').style.display = total ? 'none' : '';
    return;
  }

  countEl.textContent = shown + ' of ' + total + ' shown';

  var bits = [];
  if (from || to) bits.push('📅 ' + (from || 'start') + ' → ' + (to || 'now'));
  if (x !== null && !isNaN(x)){
    var sym = {gte:'≥', gt:'>', lte:'≤', lt:'<', eq:'='}[op];
    bits.push('🔁 recs ' + sym + ' ' + x);
  }
  document.getElementById('fs-title').textContent = bits.join('   ·   ');

  var avg = pnls.length ? pnls.reduce(function(a, b){ return a + b; }, 0) / pnls.length : null;
  document.getElementById('fs-avg').innerHTML = avg === null ? '—' :
    '<span class="' + (avg > 0 ? 'green' : (avg < 0 ? 'red' : 'blue')) + '">' +
    (avg > 0 ? '+' : '') + avg.toFixed(2) + '%</span>';
  document.getElementById('fs-win').textContent = wins + ' / ' + pnls.length;
  document.getElementById('fs-los').textContent = losses + ' / ' + pnls.length;
  statsEl.style.display = '';

  document.getElementById('empty-msg').style.display = shown ? 'none' : '';
}

function clearFilter(){
  document.getElementById('date-from').value = '';
  document.getElementById('date-to').value   = '';
  document.getElementById('recs-x').value     = '';
  document.getElementById('recs-op').value    = 'gte';
  applyFilter();
}

// ── Recs tooltip ────────────────────────────────────────────────────────────
var pinned = null;

function _buildTooltip(recs){
  var h = '<div class="rec-header">All recommendations</div>';
  recs.forEach(function(r){
    h += '<div class="rec-item">' +
           '<div class="rec-ord">' + r.ord + '</div>' +
           '<div><div class="rec-date">' + r.date + '</div>' +
             (r.time ? '<div class="rec-time">🕑 ' + r.time + '</div>' : '') + '</div>' +
           '<div class="rec-price">' + r.price + '</div>' +
           '<div class="rec-conf ' + r.conf_cls + '">' + r.conf + '</div>' +
           '<div class="rec-pnl ' + r.pnl_cls + '">' + r.pnl_str + '</div>' +
         '</div>';
  });
  return h;
}

function _place(event){
  var tip = document.getElementById('recs-tooltip');
  var w = tip.offsetWidth, h = tip.offsetHeight;
  var x = event.clientX + 14, y = event.clientY + 14;
  if (x + w > window.innerWidth  - 12) x = event.clientX - w - 14;
  if (y + h > window.innerHeight - 12) y = Math.max(12, window.innerHeight - h - 12);
  tip.style.left = x + 'px';
  tip.style.top  = y + 'px';
}

function showRecs(el, event){
  if (pinned) return;
  var tip = document.getElementById('recs-tooltip');
  tip.innerHTML = _buildTooltip(JSON.parse(el.dataset.recs));
  tip.style.display = 'block';
  _place(event);
}

function hideRecs(){
  if (pinned) return;
  document.getElementById('recs-tooltip').style.display = 'none';
}

function toggleRecs(el, event){
  event.stopPropagation();
  var tip = document.getElementById('recs-tooltip');
  if (pinned === el){
    pinned = null;
    tip.style.display = 'none';
  } else {
    pinned = el;
    tip.innerHTML = _buildTooltip(JSON.parse(el.dataset.recs));
    tip.style.display = 'block';
    _place(event);
  }
}

document.addEventListener('click', function(){
  if (pinned){
    pinned = null;
    document.getElementById('recs-tooltip').style.display = 'none';
  }
});

// Snapshot each row's pristine markup so the filter can restore it rather than
// re-deriving the original numbers after a re-anchor.
document.querySelectorAll('#tbl-body tr[data-pnl]').forEach(function(row){
  row.dataset.original    = row.innerHTML;
  row.dataset.originalPnl = row.dataset.pnl;
  row.dataset.liveRecs    = row.dataset.recs;
});

sortBy('pnl', 'desc');
"""


def render(view: dict, updated: str, max_recs: int) -> str:
    p = view["profile"]
    rows = view["rows"]

    all_dates = sorted({d for r in rows for d in r["rec_dates"]})
    min_date = all_dates[0] if all_dates else ""
    max_date = all_dates[-1] if all_dates else ""

    rows_html = "".join(
        _row_html(r, f"{r['ticker'].replace('.', '-')}/") for r in rows
    )

    if not rows:
        rows_html = ('<tr class="empty-row"><td colspan="8">'
                     'No recommendations logged for this profile yet. '
                     'They appear here automatically as they are posted to Discord.'
                     '</td></tr>')

    body = f"""
<div id="recs-tooltip"></div>
<div class="wrap">
  <a class="backlink" href="../">← All channels</a>
  <header>
    <div>
      <h1>{esc(p['name'])}</h1>
      <p>{esc(p['description'])}</p>
      <div class="chips">
        <span class="chip">{esc(p['id'])}</span>
        <span class="chip">#signals-{esc(p['discord_role'])}</span>
        <span class="chip {risk_class(p['risk_tolerance'])}">Risk {p['risk_tolerance']}/10</span>
        <span class="chip">{esc(horizon_label(p['investment_horizon_months']))}</span>
        <span class="chip">{' · '.join('🇪🇺 Europe' if r == 'europe' else '🇺🇸 US' for r in p['regions'])}</span>
        <span class="chip">Max {p['max_recs_per_day']}/day</span>
      </div>
    </div>
    <div class="updated">⏱ Prices as of {esc(updated)}</div>
  </header>

  <div class="summary">
    <div class="stat"><div class="lbl">Tickers Tracked</div><div class="val blue">{view['total']}</div></div>
    <div class="stat"><div class="lbl">Total Recs</div><div class="val">{view['total_recs']}</div></div>
    <div class="stat"><div class="lbl">Avg P&amp;L</div><div class="val">{stat_pct(view['avg_pnl'])}</div></div>
    <div class="stat"><div class="lbl">Winners</div><div class="val green">{view['winners']} / {view['measured']}</div></div>
    <div class="stat"><div class="lbl">Losers</div><div class="val red">{view['losers']} / {view['measured']}</div></div>
  </div>

  <div class="controls-row">
    <div class="controls-left">
      <div class="sort-bar">
        <span>Sort by:</span>
        <button class="sort-btn" id="btn-pnl-desc"  onclick="sortBy('pnl','desc')">P&amp;L % <span class="arrow">▼</span></button>
        <button class="sort-btn" id="btn-pnl-asc"   onclick="sortBy('pnl','asc')">P&amp;L % <span class="arrow">▲</span></button>
        <button class="sort-btn" id="btn-date-desc" onclick="sortBy('date','desc')">Date <span class="arrow">▼</span> Newest</button>
        <button class="sort-btn" id="btn-date-asc"  onclick="sortBy('date','asc')">Date <span class="arrow">▲</span> Oldest</button>
        <button class="sort-btn" id="btn-recs-desc" onclick="sortBy('recs','desc')">Recs <span class="arrow">▼</span></button>
        <button class="sort-btn" id="btn-recs-asc"  onclick="sortBy('recs','asc')">Recs <span class="arrow">▲</span></button>
      </div>

      <div class="filter-bar">
        <span>Period:</span>
        <label>From <input type="date" id="date-from" min="{min_date}" max="{max_date}" onchange="applyFilter()"></label>
        <label>To <input type="date" id="date-to" min="{min_date}" max="{max_date}" onchange="applyFilter()"></label>
      </div>

      <div class="filter-bar recs-filter">
        <span>Times recommended:</span>
        <select id="recs-op" onchange="applyFilter()">
          <option value="gte">&ge;</option>
          <option value="gt">&gt;</option>
          <option value="lte">&le;</option>
          <option value="lt">&lt;</option>
          <option value="eq">=</option>
        </select>
        <input type="number" id="recs-x" min="1" max="{max(max_recs, 1)}" step="1"
               placeholder="X" oninput="applyFilter()">
        <button class="filter-clear" onclick="clearFilter()">Clear all</button>
        <span class="filter-count" id="filter-count"></span>
      </div>
    </div>

    <div class="filter-stats" id="filter-stats" style="display:none">
      <div class="fs-title" id="fs-title">Selected</div>
      <div class="fs-grid">
        <div><div class="fs-lbl">Avg P&amp;L</div><div class="fs-val" id="fs-avg">—</div></div>
        <div><div class="fs-lbl">Winners</div><div class="fs-val green" id="fs-win">—</div></div>
        <div><div class="fs-lbl">Losers</div><div class="fs-val red" id="fs-los">—</div></div>
      </div>
    </div>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Ticker</th><th>Conf</th><th>Entry Price</th><th>Signal Date</th>
          <th>Current Price</th><th>P&amp;L %</th><th>P&amp;L / share</th>
          <th title="Number of times this ticker was recommended — hover for the breakdown">Recs</th>
        </tr>
      </thead>
      <tbody id="tbl-body">{rows_html}
        <tr class="empty-row" id="empty-msg" style="display:none">
          <td colspan="8">Nothing matches this filter.</td>
        </tr>
      </tbody>
    </table>
  </div>

  <footer>
    Every recommendation posted to <code>#signals-{esc(p['discord_role'])}</code> ·
    Prices via Yahoo Finance · Entry prices captured live at the moment of recommendation
    <div class="disclaimer">This is not professional financial advice — always make your own decisions.</div>
  </footer>
</div>
"""
    return page(f"{p['name']} — Signal Watchlist",
                page_css(), body, SCRIPT, GATE_HTML, GATE_JS, depth=1)
