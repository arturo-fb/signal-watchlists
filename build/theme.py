"""
theme.py — Shared visual language for every page on the site.

Lifted from the original generate_watchlist.py so the published pages look
identical to the watchlist you already use, then extended with the pieces the
new pages need (profile cards, the recs-count filter, the trader calendar, the
passphrase gate, ticker detail layout).

Everything is one stylesheet inlined into every page. The site is static and
served from GitHub Pages; a shared external CSS file would save a few KB but
cost a round trip on first paint, and these pages are small.
"""

PASSPHRASE = "alpha-loop-2026"

# ── Colour + type tokens ─────────────────────────────────────────────────────
BASE_CSS = """
:root{
  --bg:#0f1117; --surface:#1a1d27; --surface2:#22263a; --border:#2e3250;
  --accent:#4f8ef7; --green:#22c55e; --red:#ef4444; --yellow:#f59e0b;
  --purple:#a78bfa; --muted:#6b7280; --text:#e2e8f0; --sub:#94a3b8;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  min-height:100vh;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
.wrap{max-width:1400px;margin:0 auto;padding:28px 20px 56px}
.up{color:var(--green)} .dn{color:var(--red)} .neu{color:var(--sub)}
.green{color:var(--green)} .red{color:var(--red)} .blue{color:var(--accent)}
.err{color:var(--muted)}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.9em}

/* ── Header ─────────────────────────────────────────────────────────────── */
header{display:flex;align-items:flex-start;justify-content:space-between;
  flex-wrap:wrap;gap:12px;margin-bottom:24px}
header h1{font-size:1.5rem;font-weight:700;letter-spacing:-.01em}
header p{color:var(--sub);font-size:.83rem;margin-top:5px}
.updated{color:var(--sub);font-size:.78rem;background:var(--surface);
  border:1px solid var(--border);border-radius:8px;padding:6px 12px;white-space:nowrap}
.backlink{display:inline-flex;align-items:center;gap:6px;font-size:.78rem;
  color:var(--sub);margin-bottom:14px;transition:color .15s}
.backlink:hover{color:var(--accent)}

/* Profile meta chips under the page title */
.chips{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}
.chip{font-size:.68rem;padding:3px 10px;border-radius:99px;
  background:var(--surface2);border:1px solid var(--border);color:var(--sub)}
.chip.risk-low{color:var(--green);border-color:rgba(34,197,94,.3)}
.chip.risk-mid{color:var(--yellow);border-color:rgba(245,158,11,.3)}
.chip.risk-high{color:var(--red);border-color:rgba(239,68,68,.3)}

/* ── Summary stat cards ─────────────────────────────────────────────────── */
.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));
  gap:12px;margin-bottom:16px}
.stat{background:var(--surface);border:1px solid var(--border);
  border-radius:12px;padding:16px}
.stat .lbl{font-size:.7rem;color:var(--sub);text-transform:uppercase;letter-spacing:.5px}
.stat .val{font-size:1.35rem;font-weight:700;margin-top:4px;font-variant-numeric:tabular-nums}

/* ── Sort + filter controls ─────────────────────────────────────────────── */
.sort-bar,.filter-bar{display:flex;align-items:center;gap:10px;
  margin-bottom:14px;flex-wrap:wrap}
.sort-bar > span,.filter-bar > span{font-size:.75rem;color:var(--sub);
  text-transform:uppercase;letter-spacing:.4px}
.sort-btn{background:var(--surface);border:1px solid var(--border);color:var(--sub);
  border-radius:8px;padding:6px 14px;font-size:.78rem;font-weight:600;cursor:pointer;
  display:inline-flex;align-items:center;gap:5px;transition:all .15s;font-family:inherit}
.sort-btn:hover{border-color:var(--accent);color:var(--text)}
.sort-btn.active{border-color:var(--accent);color:var(--accent);background:rgba(79,142,247,.08)}
.sort-btn .arrow{font-size:.7rem;opacity:.7}
.filter-bar label{font-size:.75rem;color:var(--sub);display:inline-flex;align-items:center;gap:5px}
.filter-bar input[type=date],.filter-bar input[type=number],.filter-bar select{
  background:var(--surface);border:1px solid var(--border);color:var(--text);
  border-radius:8px;padding:5px 9px;font-size:.78rem;font-family:inherit;color-scheme:dark}
.filter-bar input:focus,.filter-bar select:focus{outline:none;border-color:var(--accent)}
.filter-clear{background:var(--surface);border:1px solid var(--border);color:var(--sub);
  border-radius:8px;padding:6px 12px;font-size:.76rem;font-weight:600;cursor:pointer;
  transition:all .15s;font-family:inherit}
.filter-clear:hover{border-color:var(--accent);color:var(--text)}
.filter-count{font-size:.74rem;color:var(--accent);font-weight:600}

/* The recommendation-count filter gets its own tinted row so it reads as a
   distinct control rather than a second date field. */
.recs-filter{background:rgba(167,139,250,.05);border:1px solid rgba(167,139,250,.22);
  border-radius:10px;padding:9px 14px}
.recs-filter > span{color:var(--purple)}
.recs-filter select{min-width:64px;font-weight:700;text-align:center}
.recs-filter input[type=number]{width:78px;font-weight:700;text-align:center}

.controls-row{display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap;margin-bottom:8px}
.controls-left{flex:1 1 auto;min-width:0}
.filter-stats{flex:0 0 auto;min-width:320px;background:var(--surface);
  border:1px solid var(--accent);border-radius:12px;padding:12px 18px;
  box-shadow:0 0 0 1px rgba(79,142,247,.15)}
.filter-stats .fs-title{font-size:.68rem;color:var(--accent);text-transform:uppercase;
  letter-spacing:.5px;margin-bottom:9px;font-weight:700}
.fs-grid{display:flex;gap:26px}
.fs-lbl{font-size:.63rem;color:var(--sub);text-transform:uppercase;letter-spacing:.4px}
.fs-val{font-size:1.1rem;font-weight:700;margin-top:3px;font-variant-numeric:tabular-nums}

/* ── Table ──────────────────────────────────────────────────────────────── */
.table-wrap{background:var(--surface);border:1px solid var(--border);
  border-radius:14px;overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.875rem}
thead th{background:var(--surface2);color:var(--sub);font-weight:600;font-size:.7rem;
  text-transform:uppercase;letter-spacing:.5px;padding:12px 14px;text-align:left;white-space:nowrap}
thead th:first-child{border-radius:14px 0 0 0} thead th:last-child{border-radius:0 14px 0 0}
tbody tr{border-top:1px solid var(--border);transition:background .1s}
tbody tr:hover{background:var(--surface2)}
td{padding:13px 14px;vertical-align:middle;white-space:nowrap}
.ticker-sym{font-weight:700;font-size:1rem;color:var(--accent);
  display:inline-flex;align-items:center;gap:5px;transition:opacity .15s}
a.ticker-link:hover .ticker-sym{opacity:.75;text-decoration:underline}
.ticker-sym .go{font-size:.68rem;opacity:0;transition:opacity .15s}
a.ticker-link:hover .ticker-sym .go{opacity:.6}
.ticker-name{font-size:.74rem;color:var(--sub);margin-top:2px}
.badge-sector{display:inline-block;font-size:.67rem;padding:2px 7px;border-radius:99px;
  background:var(--surface2);border:1px solid var(--border);color:var(--sub);margin-top:3px}
.badge-HIGH,.badge-MEDIUM,.badge-LOW{display:inline-block;font-size:.68rem;font-weight:700;
  padding:3px 9px;border-radius:99px;text-transform:uppercase}
.badge-HIGH{background:rgba(79,142,247,.12);border:1px solid rgba(79,142,247,.3);color:var(--accent)}
.badge-MEDIUM{background:rgba(245,158,11,.1);border:1px solid rgba(245,158,11,.3);color:var(--yellow)}
.badge-LOW{background:rgba(107,114,128,.12);border:1px solid rgba(107,114,128,.3);color:var(--sub)}
.price-main{font-weight:600;font-size:.95rem;font-variant-numeric:tabular-nums}
.price-sub{font-size:.7rem;color:var(--sub);margin-top:2px}
.sig-date{font-size:.82rem;color:var(--sub);font-variant-numeric:tabular-nums}
.sig-time{font-size:.7rem;color:var(--muted);margin-top:2px;font-variant-numeric:tabular-nums}
.pnl-col span{font-weight:700;font-size:.95rem;font-variant-numeric:tabular-nums}
.empty-row td{text-align:center;color:var(--muted);padding:36px 14px;font-size:.85rem}

/* ── Recs badge + tooltip ───────────────────────────────────────────────── */
.recs-badge{display:inline-flex;align-items:center;justify-content:center;min-width:34px;
  padding:4px 11px;border-radius:99px;font-size:.78rem;font-weight:700;cursor:pointer;
  user-select:none;transition:filter .15s}
.recs-badge:hover{filter:brightness(1.25)}
.recs-1{background:rgba(79,142,247,.1);border:1px solid rgba(79,142,247,.3);color:var(--accent)}
.recs-2{background:rgba(245,158,11,.1);border:1px solid rgba(245,158,11,.3);color:var(--yellow)}
.recs-3plus{background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.3);color:var(--green)}
#recs-tooltip{position:fixed;z-index:9999;display:none;background:#1e2235;
  border:1px solid var(--border);border-radius:10px;padding:10px 14px;
  min-width:300px;max-width:380px;box-shadow:0 8px 32px rgba(0,0,0,.55);pointer-events:none}
.rec-header{font-size:.63rem;color:var(--sub);text-transform:uppercase;letter-spacing:.6px;
  padding-bottom:7px;margin-bottom:4px;border-bottom:1px solid var(--border)}
.rec-item{display:grid;grid-template-columns:18px 82px 66px 58px 60px;gap:6px;align-items:center;
  padding:5px 0;border-bottom:1px solid rgba(46,50,80,.4)}
.rec-item:last-child{border-bottom:none}
.rec-ord{font-size:.78rem;color:var(--sub)}
.rec-date{font-size:.74rem;color:var(--text);font-variant-numeric:tabular-nums}
.rec-time{font-size:.64rem;color:var(--muted);font-variant-numeric:tabular-nums;margin-top:1px}
.rec-price{font-size:.78rem;font-weight:600;color:var(--text);font-variant-numeric:tabular-nums}
.rec-conf{font-size:.6rem;font-weight:700;padding:2px 6px;border-radius:99px;text-align:center}
.rec-pnl{font-size:.78rem;font-weight:700;text-align:right;font-variant-numeric:tabular-nums}

footer{margin-top:28px;font-size:.72rem;color:var(--muted);text-align:center;line-height:1.7}
.disclaimer{margin-top:6px;color:var(--muted)}
"""

# ── Landing page ─────────────────────────────────────────────────────────────
LANDING_CSS = """
.hero{min-height:88vh;display:flex;flex-direction:column;align-items:center;
  justify-content:center;text-align:center;padding:60px 20px;position:relative;
  background:radial-gradient(ellipse 80% 60% at 50% 0%,rgba(79,142,247,.13),transparent 70%)}
.hero-badge{display:inline-flex;align-items:center;gap:7px;font-size:.72rem;
  color:var(--accent);background:rgba(79,142,247,.08);border:1px solid rgba(79,142,247,.25);
  border-radius:99px;padding:6px 15px;margin-bottom:24px;letter-spacing:.3px}
.hero h1{font-size:clamp(2.1rem,6vw,3.6rem);font-weight:800;letter-spacing:-.03em;
  line-height:1.08;max-width:15ch;margin-bottom:20px}
.hero h1 .grad{background:linear-gradient(115deg,var(--accent),var(--purple));
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
.hero .lede{color:var(--sub);font-size:clamp(.95rem,2vw,1.1rem);max-width:60ch;
  line-height:1.65;margin-bottom:34px}
.hero-stats{display:flex;gap:36px;flex-wrap:wrap;justify-content:center;margin-bottom:44px}
.hs-val{font-size:1.7rem;font-weight:800;font-variant-numeric:tabular-nums}
.hs-lbl{font-size:.68rem;color:var(--sub);text-transform:uppercase;letter-spacing:.6px;margin-top:3px}
.scroll-cue{position:absolute;bottom:34px;left:50%;transform:translateX(-50%);
  color:var(--sub);font-size:.74rem;display:flex;flex-direction:column;align-items:center;
  gap:7px;animation:bob 2.4s ease-in-out infinite;cursor:pointer}
.scroll-cue .chev{font-size:1.1rem;color:var(--accent)}
@keyframes bob{0%,100%{transform:translate(-50%,0)}50%{transform:translate(-50%,7px)}}

.section-head{text-align:center;margin:0 0 34px}
.section-head h2{font-size:1.9rem;font-weight:700;letter-spacing:-.02em;margin-bottom:9px}
.section-head p{color:var(--sub);font-size:.9rem;max-width:58ch;margin:0 auto;line-height:1.6}

.profiles-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:16px}
.pcard{background:var(--surface);border:1px solid var(--border);border-radius:15px;
  padding:22px;display:flex;flex-direction:column;gap:11px;position:relative;
  overflow:hidden;transition:transform .18s,border-color .18s,box-shadow .18s}
.pcard::before{content:'';position:absolute;inset:0 auto 0 0;width:3px;
  background:var(--accent);opacity:.55;transition:opacity .18s}
.pcard:hover{transform:translateY(-3px);border-color:var(--accent);
  box-shadow:0 12px 34px rgba(0,0,0,.42)}
.pcard:hover::before{opacity:1}
.pcard.is-trader::before{background:var(--red)}
.pcard.is-trader:hover{border-color:var(--red)}
.pc-top{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}
.pc-id{font-size:.66rem;color:var(--muted);letter-spacing:1px;font-weight:700}
.pc-name{font-size:1.12rem;font-weight:700;margin-top:3px;letter-spacing:-.01em}
.pc-handle{font-size:.72rem;color:var(--accent);margin-top:3px;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.pc-desc{font-size:.8rem;color:var(--sub);line-height:1.55;flex:1}
.pc-meta{display:flex;gap:6px;flex-wrap:wrap}
.pc-foot{display:flex;align-items:center;justify-content:space-between;
  border-top:1px solid var(--border);padding-top:12px;margin-top:3px}
.pc-count{font-size:.74rem;color:var(--sub)}
.pc-count b{color:var(--text);font-size:.9rem}
.pc-go{font-size:.76rem;font-weight:700;color:var(--accent);display:inline-flex;
  align-items:center;gap:5px}
.pcard:hover .pc-go{gap:9px}
.pc-go span{transition:transform .18s}
.daytag{font-size:.6rem;font-weight:700;letter-spacing:.5px;padding:3px 8px;
  border-radius:99px;background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.32);
  color:var(--red);text-transform:uppercase}
"""

# ── Trader (day-trading) pages ───────────────────────────────────────────────
TRADER_CSS = """
.section{margin-bottom:30px}
.section-title{display:flex;align-items:center;justify-content:space-between;
  gap:12px;flex-wrap:wrap;margin-bottom:13px}
.section-title h2{font-size:1.06rem;font-weight:700;display:flex;align-items:center;gap:9px}
.section-title .hint{font-size:.74rem;color:var(--muted)}
.live-dot{width:7px;height:7px;border-radius:50%;background:var(--green);
  box-shadow:0 0 0 3px rgba(34,197,94,.18);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
.live-dot.closed{background:var(--muted);box-shadow:0 0 0 3px rgba(107,114,128,.15);animation:none}

/* Month-performance button + its hover panel */
.perf-btn{position:relative;background:var(--surface);border:1px solid var(--accent);
  color:var(--accent);border-radius:9px;padding:8px 16px;font-size:.79rem;font-weight:700;
  cursor:pointer;font-family:inherit;display:inline-flex;align-items:center;gap:7px;
  transition:all .15s}
.perf-btn:hover{background:rgba(79,142,247,.1)}
#month-panel{position:fixed;z-index:9999;display:none;background:#1e2235;
  border:1px solid var(--border);border-radius:12px;padding:14px 16px;min-width:330px;
  max-width:400px;box-shadow:0 14px 44px rgba(0,0,0,.62)}
.mp-title{font-size:.66rem;color:var(--sub);text-transform:uppercase;letter-spacing:.6px;
  padding-bottom:8px;margin-bottom:7px;border-bottom:1px solid var(--border);
  display:flex;justify-content:space-between;align-items:center}
.mp-row{display:grid;grid-template-columns:104px 1fr 62px;gap:9px;align-items:center;
  padding:5px 0;border-bottom:1px solid rgba(46,50,80,.4)}
.mp-row:last-child{border-bottom:none}
.mp-date{font-size:.74rem;color:var(--text);font-variant-numeric:tabular-nums}
.mp-n{font-size:.65rem;color:var(--muted)}
.mp-bar{height:5px;border-radius:99px;background:rgba(255,255,255,.05);position:relative;
  overflow:hidden}
.mp-bar i{position:absolute;top:0;bottom:0;left:50%;border-radius:99px;display:block}
.mp-pct{font-size:.76rem;font-weight:700;text-align:right;font-variant-numeric:tabular-nums}

/* Weekly P/L blocks */
.weeks{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:14px}
.week{background:var(--surface);border:1px solid var(--border);border-radius:13px;
  padding:16px 18px}
.week-head{display:flex;align-items:baseline;justify-content:space-between;gap:10px;
  padding-bottom:10px;margin-bottom:9px;border-bottom:1px solid var(--border)}
.week-name{font-size:.82rem;font-weight:700}
.week-range{font-size:.66rem;color:var(--muted);margin-top:2px;font-variant-numeric:tabular-nums}
.week-total{font-size:1.15rem;font-weight:800;font-variant-numeric:tabular-nums}
.week-total-lbl{font-size:.6rem;color:var(--sub);text-transform:uppercase;
  letter-spacing:.4px;text-align:right;margin-top:2px}
.day-row{display:grid;grid-template-columns:98px 30px 1fr 60px;gap:8px;align-items:center;
  padding:5px 0;font-size:.76rem}
.day-name{color:var(--sub);font-variant-numeric:tabular-nums}
.day-n{color:var(--muted);font-size:.66rem;text-align:center}
.day-pct{font-weight:700;text-align:right;font-variant-numeric:tabular-nums}
.day-row.no-data{opacity:.4}
.week-empty{font-size:.74rem;color:var(--muted);padding:8px 0}

/* Month-to-date banner */
.mtd{background:linear-gradient(135deg,rgba(79,142,247,.1),rgba(167,139,250,.07));
  border:1px solid rgba(79,142,247,.32);border-radius:15px;padding:24px 26px;
  display:flex;align-items:center;justify-content:space-between;gap:22px;flex-wrap:wrap}
.mtd-left .mtd-lbl{font-size:.68rem;color:var(--accent);text-transform:uppercase;
  letter-spacing:.7px;font-weight:700}
.mtd-left .mtd-val{font-size:2.5rem;font-weight:800;margin-top:5px;
  font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.mtd-left .mtd-sub{font-size:.75rem;color:var(--sub);margin-top:5px}
.mtd-right{display:flex;gap:30px;flex-wrap:wrap}
.mtd-stat .v{font-size:1.25rem;font-weight:700;font-variant-numeric:tabular-nums}
.mtd-stat .l{font-size:.63rem;color:var(--sub);text-transform:uppercase;
  letter-spacing:.4px;margin-top:2px}
.pending{font-size:.65rem;color:var(--yellow);background:rgba(245,158,11,.1);
  border:1px solid rgba(245,158,11,.28);border-radius:99px;padding:2px 8px;margin-left:6px}
"""

# ── Ticker detail pages ──────────────────────────────────────────────────────
TICKER_CSS = """
.tk-head{display:flex;align-items:flex-start;gap:18px;flex-wrap:wrap;
  padding-bottom:22px;margin-bottom:24px;border-bottom:1px solid var(--border)}
.tk-id{flex:1 1 300px}
.tk-sym{font-size:2.3rem;font-weight:800;color:var(--accent);letter-spacing:-.02em}
.tk-name{font-size:1rem;color:var(--sub);margin-top:3px}
.tk-price{text-align:right}
.tk-price .p{font-size:1.9rem;font-weight:800;font-variant-numeric:tabular-nums}
.tk-price .c{font-size:.88rem;font-weight:700;margin-top:3px;font-variant-numeric:tabular-nums}

.tk-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
  gap:12px;margin-bottom:26px}

.panel{background:var(--surface);border:1px solid var(--border);border-radius:15px;
  padding:24px 26px;margin-bottom:20px}
.panel-head{display:flex;align-items:center;justify-content:space-between;gap:12px;
  flex-wrap:wrap;padding-bottom:14px;margin-bottom:16px;border-bottom:1px solid var(--border)}
.panel-head h2{font-size:1.02rem;font-weight:700;display:flex;align-items:center;gap:9px}
.ai-tag{font-size:.62rem;font-weight:700;letter-spacing:.5px;padding:3px 9px;border-radius:99px;
  background:rgba(167,139,250,.12);border:1px solid rgba(167,139,250,.32);
  color:var(--purple);text-transform:uppercase}
.src-tag{font-size:.66rem;color:var(--muted)}

/* Thesis prose */
.thesis{font-size:.9rem;line-height:1.72;color:var(--text)}
.thesis h1,.thesis h2,.thesis h3{font-size:.9rem;font-weight:700;margin:18px 0 7px;color:var(--text)}
.thesis h1:first-child,.thesis h2:first-child,.thesis h3:first-child{margin-top:0}
.thesis p{margin-bottom:12px}
.thesis p:last-child{margin-bottom:0}
.thesis ul,.thesis ol{margin:0 0 12px 20px}
.thesis li{margin-bottom:6px}
.thesis strong{color:#fff;font-weight:700}
.thesis em{color:var(--sub)}
.thesis code{background:var(--surface2);border:1px solid var(--border);
  border-radius:5px;padding:1px 5px}
.thesis blockquote{border-left:3px solid var(--border);padding-left:14px;
  color:var(--sub);margin:0 0 12px}
.thesis hr{border:none;border-top:1px solid var(--border);margin:18px 0}

/* Timeline of individual theses under the summary */
.tl-item{border-left:2px solid var(--border);padding:0 0 22px 20px;position:relative}
.tl-item:last-child{padding-bottom:0}
.tl-item::before{content:'';position:absolute;left:-6px;top:5px;width:10px;height:10px;
  border-radius:50%;background:var(--surface);border:2px solid var(--accent)}
.tl-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:9px}
.tl-ord{font-size:.9rem;color:var(--sub)}
.tl-date{font-size:.8rem;font-weight:700;font-variant-numeric:tabular-nums}
.tl-time{font-size:.7rem;color:var(--muted);font-variant-numeric:tabular-nums}
.tl-price{font-size:.8rem;font-weight:700;font-variant-numeric:tabular-nums}
.tl-pnl{font-size:.8rem;font-weight:700;margin-left:auto;font-variant-numeric:tabular-nums}
.tl-body{font-size:.85rem;line-height:1.68;color:var(--sub)}
.tl-risk{font-size:.78rem;color:var(--sub);background:rgba(239,68,68,.05);
  border-left:2px solid rgba(239,68,68,.35);border-radius:0 7px 7px 0;
  padding:9px 13px;margin-top:11px;line-height:1.6}
.tl-risk b{color:var(--red);font-weight:700}

/* "All recommendations" table on the detail page */
.allrecs{width:100%;border-collapse:collapse;font-size:.85rem}
.allrecs thead th{background:transparent;border-bottom:1px solid var(--border);
  color:var(--sub);font-size:.66rem;text-transform:uppercase;letter-spacing:.5px;
  padding:0 12px 10px;text-align:left}
.allrecs tbody tr{border-top:1px solid rgba(46,50,80,.5)}
.allrecs tbody tr:hover{background:var(--surface2)}
.allrecs td{padding:11px 12px;font-variant-numeric:tabular-nums}
.allrecs .ord{color:var(--sub);font-size:.95rem}
.no-thesis{font-size:.84rem;color:var(--muted);font-style:italic;line-height:1.6}
"""

# ── Passphrase gate ──────────────────────────────────────────────────────────
# Deliberately simple. The repo is public, so this keeps casual visitors out of
# the pages — it is not, and is not presented as, real access control. Anyone
# who opens devtools or reads the repo can bypass it. That trade-off is the
# price of free GitHub Pages hosting; the alternative is a paid plan.
GATE_CSS = """
#gate{position:fixed;inset:0;z-index:99999;background:var(--bg);
  display:flex;align-items:center;justify-content:center;padding:24px}
#gate .box{background:var(--surface);border:1px solid var(--border);border-radius:17px;
  padding:42px 38px;max-width:400px;width:100%;text-align:center}
#gate h2{font-size:1.2rem;font-weight:700;margin-bottom:8px}
#gate p{font-size:.82rem;color:var(--sub);margin-bottom:22px;line-height:1.6}
#gate input{width:100%;background:var(--bg);border:1px solid var(--border);
  color:var(--text);border-radius:10px;padding:12px 15px;font-size:.92rem;
  font-family:inherit;text-align:center;letter-spacing:.4px}
#gate input:focus{outline:none;border-color:var(--accent)}
#gate button{width:100%;margin-top:11px;background:var(--accent);border:none;color:#fff;
  border-radius:10px;padding:12px;font-size:.88rem;font-weight:700;cursor:pointer;
  font-family:inherit;transition:filter .15s}
#gate button:hover{filter:brightness(1.1)}
#gate .err-msg{color:var(--red);font-size:.78rem;margin-top:11px;min-height:1.1em}
body.locked{overflow:hidden}
"""

GATE_HTML = """
<div id="gate">
  <div class="box">
    <h2>&#128274; Private watchlists</h2>
    <p>These pages are for the Discord group. Enter the passphrase to continue.</p>
    <input type="password" id="gate-input" placeholder="Passphrase"
           autocomplete="current-password" autofocus>
    <button onclick="tryUnlock()">Unlock</button>
    <div class="err-msg" id="gate-err"></div>
  </div>
</div>
"""

# sessionStorage, not localStorage: the unlock lasts for the browsing session
# and is gone when the tab closes, which suits a shared or borrowed device.
GATE_JS = """
(function(){
  var KEY='sig-wl-unlocked', PASS='%(pass)s';
  function unlock(){
    var g=document.getElementById('gate');
    if(g) g.remove();
    document.body.classList.remove('locked');
  }
  window.tryUnlock=function(){
    var v=(document.getElementById('gate-input').value||'').trim();
    if(v===PASS){ try{sessionStorage.setItem(KEY,'1');}catch(e){} unlock(); }
    else{
      document.getElementById('gate-err').textContent='Not quite — try again.';
      document.getElementById('gate-input').value='';
      document.getElementById('gate-input').focus();
    }
  };
  try{ if(sessionStorage.getItem(KEY)==='1'){ unlock(); return; } }catch(e){}
  document.body.classList.add('locked');
  document.addEventListener('keydown',function(e){
    if(e.key==='Enter' && document.getElementById('gate')) window.tryUnlock();
  });
})();
""" % {"pass": PASSPHRASE}


def page_css(*extra: str) -> str:
    """BASE_CSS plus the gate, plus whichever page-specific blocks are needed."""
    return "\n".join([BASE_CSS, GATE_CSS, *extra])
