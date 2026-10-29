#!/usr/bin/env python3
"""
render_lib.py — Zahlenformat, Markdown-Tabellen und ein kleiner Markdown→HTML-Wandler.

Der Wandler kennt nur, was die Dokumente der Suite erzeugen: Überschriften, Absätze, Listen,
Tabellen, Zitate, **fett**, *kursiv* und `Code`. Alles andere wird als Text ausgegeben. Der
Text wird immer maskiert; eingefügte Texte können kein HTML einschleusen.
"""

from __future__ import annotations

import html
import re

OPEN = "❓ offen"

CSS = """
:root{--bg:#fcfcfb;--fg:#1c2321;--muted:#5b6761;--line:#d9dedb;--accent:#0F5F57;--soft:#eef4f2;--warn:#8a5a00;--warn-bg:#fdf3dc}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#141918;--fg:#e6ebe8;--muted:#9aa7a1;--line:#2c3532;--accent:#5fc2b6;--soft:#1b2321;--warn:#f0c36a;--warn-bg:#2b2412}}
:root[data-theme="dark"]{--bg:#141918;--fg:#e6ebe8;--muted:#9aa7a1;--line:#2c3532;--accent:#5fc2b6;--soft:#1b2321;--warn:#f0c36a;--warn-bg:#2b2412}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 'Segoe UI',system-ui,sans-serif}
main{max-width:60rem;margin:0 auto;padding:2rem 16px 4rem}
h1{font-size:1.9rem;line-height:1.2;margin:0 0 .4rem}
h2{font-size:1.3rem;margin:2.2rem 0 .6rem;padding-top:.6rem;border-top:1px solid var(--line)}
h3{font-size:1.05rem;margin:1.4rem 0 .4rem}
p,li{max-width:46rem}
a{color:var(--accent)}
table{border-collapse:collapse;width:100%;margin:.8rem 0;font-size:.92rem}
.wrap{overflow-x:auto}
th,td{border-bottom:1px solid var(--line);padding:.4rem .6rem;text-align:left;vertical-align:top}
th{background:var(--soft)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
blockquote{margin:1rem 0;padding:.6rem 1rem;border-left:4px solid var(--accent);background:var(--soft)}
blockquote.open{border-left-color:var(--warn);background:var(--warn-bg);color:var(--warn)}
code{background:var(--soft);padding:.1rem .3rem;border-radius:3px}
.meta{color:var(--muted);margin:0 0 1.6rem}
@media print{body{font-size:11pt}main{max-width:none;padding:0}h2{break-after:avoid}table,blockquote{break-inside:avoid}}
"""


def num(x, nd: int = 1) -> str:
    return "–" if x is None else f"{x:,.{nd}f}".replace(",", " ")


def eur(x) -> str:
    return "nicht bewertet" if x is None else f"{x:,.0f} €".replace(",", " ")


def cell(x) -> str:
    return str(x).replace("|", "\\|").replace("\n", " ")


def md_table(headers: list[str], rows: list[list], align: list[str] | None = None) -> str:
    """Markdown-Tabelle; `align` je Spalte 'l' oder 'r'."""
    align = align or ["l"] * len(headers)
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---:" if a == "r" else "---" for a in align) + "|"]
    for r in rows:
        out.append("| " + " | ".join(cell(c) for c in r) + " |")
    return "\n".join(out)


_INLINE = [(re.compile(r"\*\*(.+?)\*\*"), r"<strong>\1</strong>"),
           (re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])"), r"<em>\1</em>"),
           (re.compile(r"`([^`]+)`"), r"<code>\1</code>")]


def inline(text: str) -> str:
    out = html.escape(text, quote=False)
    for rx, repl in _INLINE:
        out = rx.sub(repl, out)
    return out


def _split_row(line: str) -> list[str]:
    parts = re.split(r"(?<!\\)\|", line.strip())
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return [p.strip().replace("\\|", "|") for p in parts]


def md_to_html(md: str) -> str:
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        m = re.match(r"^(#{1,3})\s+(.*)$", line)
        if m:
            n = len(m.group(1))
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
            i += 1
        elif line.lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            head = _split_row(line)
            aligns = ["num" if c.strip().endswith(":") else "" for c in _split_row(lines[i + 1])]
            i += 2
            body = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                body.append(_split_row(lines[i]))
                i += 1

            def td(tag, j, c):
                cls = f' class="{aligns[j]}"' if j < len(aligns) and aligns[j] else ""
                return f"<{tag}{cls}>{inline(c)}</{tag}>"
            rows = "".join("<tr>" + "".join(td("td", j, c) for j, c in enumerate(r)) + "</tr>" for r in body)
            out.append('<div class="wrap"><table><thead><tr>' + "".join(td("th", j, c) for j, c in enumerate(head))
                       + f"</tr></thead><tbody>{rows}</tbody></table></div>")
        elif re.match(r"^\s*[-*]\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                items.append(re.sub(r"^\s*[-*]\s+", "", lines[i]))
                i += 1
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>")
        elif line.startswith(">"):
            quote = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(lines[i].lstrip(">").strip())
                i += 1
            text = " ".join(quote)
            cls = ' class="open"' if text.startswith(OPEN) else ""
            out.append(f"<blockquote{cls}>{inline(text)}</blockquote>")
        else:
            para = []
            while (i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,3}\s|\s*[-*]\s|>|\s*\|)", lines[i])):
                para.append(lines[i].strip())
                i += 1
            if not para:  # Zeile, die keinen Block beginnt und keinen Absatz füllt
                para = [lines[i].strip()]
                i += 1
            out.append(f"<p>{inline(' '.join(para))}</p>")
    return "\n".join(out)


def html_page(title: str, body_html: str, extra_css: str = "", lang: str = "de") -> str:
    return (f'<!doctype html>\n<html lang="{lang}"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{html.escape(title)}</title><style>{CSS}{extra_css}</style></head>"
            f"<body><main>\n{body_html}\n</main></body></html>\n")
