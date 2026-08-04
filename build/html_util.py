"""
html_util.py — Small shared rendering helpers.

Includes a compact Markdown renderer. The theses are written by Claude in
Discord-flavoured Markdown (headings, bold, bullets, the occasional link), and
pulling in a full Markdown library for that subset would add a dependency to
the GitHub Action for no real gain. Everything is escaped before any inline
formatting is applied, so thesis text can never inject markup into the page.
"""

from __future__ import annotations

import html as _html
import json
import re


def esc(s) -> str:
    return _html.escape(str(s if s is not None else ""))


def attr(data) -> str:
    """JSON-encode a value for safe embedding in an HTML attribute."""
    return _html.escape(json.dumps(data))


def pct_html(value, cls_prefix: str = "") -> str:
    """Signed, coloured percentage. `—` when there is nothing to measure."""
    if value is None:
        return '<span class="neu">—</span>'
    cls = "up" if value > 0 else ("dn" if value < 0 else "neu")
    sign = "+" if value > 0 else ""
    return f'<span class="{cls_prefix}{cls}">{sign}{value:.2f}%</span>'


def stat_pct(value) -> str:
    if value is None:
        return "—"
    cls = "green" if value > 0 else ("red" if value < 0 else "blue")
    sign = "+" if value > 0 else ""
    return f'<span class="{cls}">{sign}{value:.2f}%</span>'


# Currency symbols. UK names quote in GBX (pence), so 1120 means £11.20 — the
# unit is shown explicitly rather than guessed at, because silently formatting
# pence as pounds turns an £11 stock into an £1,120 one.
_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "CHF": "CHF ", "GBX": ""}


def money(value, currency: str = "USD", decimals: int = 2) -> str:
    if value is None:
        return "—"
    if currency == "GBX":
        return f"{value:,.0f}p"
    sym = _SYMBOLS.get(currency, "")
    return f"{sym}{value:,.{decimals}f}"


def money_signed(value, currency: str = "USD") -> str:
    if value is None:
        return "—"
    sign = "+" if value > 0 else "−"
    return f"{sign}{money(abs(value), currency)}"


def flag(region: str) -> str:
    return "🇪🇺" if region == "europe" else "🇺🇸"


def risk_class(risk: int) -> str:
    if risk <= 3:
        return "risk-low"
    if risk <= 6:
        return "risk-mid"
    return "risk-high"


def horizon_label(months: int) -> str:
    if months == 0:
        return "Intraday – days"
    if months <= 1:
        return "Days – weeks"
    if months < 12:
        return f"{months} months"
    years = months / 12
    return f"{years:.0f}+ years" if years == int(years) else f"{years:.1f} years"


# ── Markdown ─────────────────────────────────────────────────────────────────

_INLINE = [
    (re.compile(r"\*\*\*(.+?)\*\*\*", re.S), r"<strong><em>\1</em></strong>"),
    (re.compile(r"\*\*(.+?)\*\*", re.S), r"<strong>\1</strong>"),
    (re.compile(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", re.S), r"<em>\1</em>"),
    (re.compile(r"__(.+?)__", re.S), r"<strong>\1</strong>"),
    (re.compile(r"`([^`]+)`"), r"<code>\1</code>"),
    (re.compile(r"~~(.+?)~~", re.S), r"<del>\1</del>"),
]

# Only http(s) links are linkified — never javascript: or data: URIs, which
# would otherwise be a script-injection route straight through the thesis text.
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
_BARE_URL = re.compile(r"(?<![\"'>=])(https?://[^\s<)]+)")


def _inline(text: str) -> str:
    out = esc(text)
    out = _LINK.sub(r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', out)
    out = _BARE_URL.sub(r'<a href="\1" target="_blank" rel="noopener noreferrer">\1</a>', out)
    for pattern, repl in _INLINE:
        out = pattern.sub(repl, out)
    return out


def markdown(text: str) -> str:
    """Render the Markdown subset the theses actually use."""
    if not text or not str(text).strip():
        return ""

    lines = str(text).replace("\r\n", "\n").split("\n")
    html_out: list[str] = []
    para: list[str] = []
    list_stack: list[str] = []

    def flush_para():
        if para:
            html_out.append(f"<p>{_inline(' '.join(para))}</p>")
            para.clear()

    def close_lists(to: int = 0):
        while len(list_stack) > to:
            html_out.append(f"</{list_stack.pop()}>")

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            flush_para()
            close_lists()
            continue

        if re.fullmatch(r"([-*_])\1{2,}", stripped):
            flush_para(); close_lists()
            html_out.append("<hr>")
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            flush_para(); close_lists()
            level = min(len(m.group(1)) + 1, 6)
            html_out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            continue

        m = re.match(r"^>\s?(.*)$", stripped)
        if m:
            flush_para(); close_lists()
            html_out.append(f"<blockquote>{_inline(m.group(1))}</blockquote>")
            continue

        m = re.match(r"^([-*+•])\s+(.*)$", stripped)
        if m:
            flush_para()
            if not list_stack or list_stack[-1] != "ul":
                close_lists()
                list_stack.append("ul")
                html_out.append("<ul>")
            html_out.append(f"<li>{_inline(m.group(2))}</li>")
            continue

        m = re.match(r"^(\d+)[.)]\s+(.*)$", stripped)
        if m:
            flush_para()
            if not list_stack or list_stack[-1] != "ol":
                close_lists()
                list_stack.append("ol")
                html_out.append("<ol>")
            html_out.append(f"<li>{_inline(m.group(2))}</li>")
            continue

        close_lists()
        para.append(stripped)

    flush_para()
    close_lists()
    return "\n".join(html_out)


# ── Page shell ───────────────────────────────────────────────────────────────

def page(title: str, css: str, body: str, script: str = "",
         gate_html: str = "", gate_js: str = "", depth: int = 0) -> str:
    """
    Wrap a body in the full document.

    `depth` is how many directory levels deep the page sits, so relative asset
    and back-links resolve on GitHub Pages (which serves from a subpath, making
    absolute `/` links point outside the site).
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<meta name="robots" content="noindex,nofollow"/>
<title>{esc(title)}</title>
<style>{css}</style>
</head>
<body>
{gate_html}
{body}
<script>
{gate_js}
{script}
</script>
</body>
</html>
"""
