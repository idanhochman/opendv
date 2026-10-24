"""Code coverage pages inside the regression site (see opendv.report).

Reads <run>/code_cov/merged.dat and writes, under <run>/code/:

    index.html                 summary: cards, per-file table
    uncovered.html             every hole across files, filterable
    <file>.source.html         annotated source        } tabs of one
    <file>.toggle.html         per-signal / per-bit    } source file
    <file>.ctrl.html           line + branch points    }

All pages share the site shell (theme, collapsible sidebar) and have their own
sidebar: back link, Summary, one entry per source file, Uncovered. The parsing
and per-signal rendering are in data.py and report.py; only the page layout is here.
"""

from collections import defaultdict
from pathlib import Path

from ..htmlkit import bar, esc, pct, read_asset
from .data import LOW, bit_key, by_file_line, holes, line_status, parse_dat, summarize
from .report import signal_details


CSS = read_asset(__package__, "pages.css")
FILTER_JS = read_asset(__package__, "filter.js")


def _state(h: int, s: int) -> str:
    return "pass" if h == s else ("warn" if pct(h, s) >= 80 else "fail")


def _legend() -> str:
    return ('<div class="legend"><span><span class="bit z">0</span> never hit</span>'
            f'<span><span class="bit lo">n</span> hit &lt; {LOW} times</span>'
            f'<span><span class="bit ok">n</span> hit &ge; {LOW} times</span>'
            '<span><span class="sw ok"></span> covered line</span>'
            '<span><span class="sw part"></span> partly covered</span>'
            '<span><span class="sw z"></span> never hit</span></div>')


class Code:
    def __init__(self, dat: Path):
        self.points = parse_dat(dat)
        self.summ = summarize(self.points)
        self.by_line = by_file_line(self.points)
        self.files = sorted(self.by_line, key=lambda f: Path(f).name)
        self.names = {f: Path(f).name for f in self.files}
        self.holes = holes(self.points)

    def file_points(self, f: str) -> list[dict]:
        return [p for p in self.points if p["file"] == f]

    def file_summ(self, f: str) -> tuple[int, int, dict]:
        fs = summarize(self.file_points(f))
        return sum(v["hit"] for v in fs.values()), sum(v["size"] for v in fs.values()), fs


def sidebar(c: Code, cur: str) -> str:
    def item(href, label, key, dot="", pc=""):
        return (f'<a class="run{" cur" if key == cur else ""}" href="{esc(href)}">{dot}'
                f'<span class="nm">{esc(label)}</span>{pc}</a>')

    out = ['<div id="runs">', item("../index.html", "‹ Back to regression", "-"),
           '<div class="sidehead">Code coverage</div>', item("index.html", "Summary", "summary"),
           '<div class="sidelbl">Files</div>']
    for f in c.files:
        h, s, _ = c.file_summ(f)
        n = c.names[f]
        out.append(item(f"{n}.source.html", n, n, f'<span class="dot d-{_state(h, s)}"></span>',
                        f'<span class="pc">{pct(h, s):.0f}%</span>'))
    out.append('<div class="sidelbl">Review</div>')
    out.append(item("uncovered.html", f"Uncovered ({len(c.holes)})", "uncovered"))
    out.append("</div>")
    return "".join(out)


def p_summary(c: Code) -> str:
    cards = []
    for t, v in c.summ.items():
        st = {"pass": "ok", "warn": "warn", "fail": "bad"}[_state(v["hit"], v["size"])]
        cards.append(f'<div class="card {st}"><div class="lbl">{esc(t)}</div><div class="val">{pct(v["hit"], v["size"]):.1f}%</div>'
                     f'<div class="sub">{v["hit"]}/{v["size"]} points</div></div>')
    types = list(c.summ)
    head = '<tr><th class="l">file</th><th>all points</th>' + "".join(f"<th>{esc(t)}</th>" for t in types) + "<th></th></tr>"
    rows = []
    for f in c.files:
        h, s, fs = c.file_summ(f)
        cells = "".join(f'<td class="mono">{fs[t]["hit"]}/{fs[t]["size"]}</td>' if t in fs else "<td>–</td>" for t in types)
        rows.append(f'<tr><td class="l mono"><a href="{esc(c.names[f])}.source.html">{esc(c.names[f])}</a></td>'
                    f'<td class="mono">{h}/{s} ({pct(h, s):.1f}%)</td>{cells}<td>{bar(h, s)}</td></tr>')
    return (f'<div class="cards">{"".join(cards)}</div>{_legend()}<h2>Files</h2>'
            f'<div class="scroll"><table>{head}{"".join(rows)}</table></div>')


def source_table(path: str, pts_by_line: dict) -> str:
    src = Path(path)
    text = src.read_text().splitlines() if src.exists() else []
    if not text:
        return f'<p class="muted">Source not found: {esc(path)}</p>'
    out = ['<div class="srcwrap"><table class="src">']
    for n, code in enumerate(text, 1):
        pts = pts_by_line.get(n, [])
        st = line_status(pts) if pts else "none"
        ctl = [p for p in pts if p["type"] != "toggle"]
        tog = [p for p in pts if p["type"] == "toggle"]
        if ctl:
            gut = f"{max(p['count'] for p in ctl)}"
        elif tog:
            gut = f"{sum(p['count'] > 0 for p in tog)}/{len(tog)}"
        else:
            gut = ""
        tags = "".join(f"<span class='tag {'z' if p['count'] == 0 else 'ok'}'>{esc(p['what'] or p['type'])} &times;{p['count']}</span>"
                       for p in ctl if p["line"] == n)
        out.append(f"<tr id='L{n}' class='{st}'><td class='ln'><a href='#L{n}'>{n}</a></td><td class='gut'>{gut}</td>"
                   f"<td class='code'><pre>{esc(code) or ' '}</pre>{tags}</td></tr>")
        if tog:
            chips = defaultdict(list)
            for p in tog:
                base, bit = bit_key(p["what"])
                chips[base].append((bit, p["count"]))
            row = "".join(signal_details(base, bits) for base, bits in chips.items())
            out.append(f"<tr class='{st}'><td></td><td></td><td>{row}</td></tr>")
    out.append("</table></div>")
    return "".join(out)


def p_toggle(c: Code, f: str) -> str:
    groups: dict[str, dict] = defaultdict(lambda: defaultdict(dict))
    sigline = {}
    for p in c.file_points(f):
        if p["type"] != "toggle":
            continue
        base, bit = bit_key(p["what"])
        groups[p["hier"]][base][bit] = p["count"]
        sigline[base] = p["line"]
    if not groups:
        return '<p class="muted">No toggle points in this file.</p>'
    out = [_legend()]
    for hier, sigs in sorted(groups.items()):
        h = sum(v > 0 for b in sigs.values() for v in b.values())
        s = sum(len(b) for b in sigs.values())
        out.append(f'<details class="inst"{" open" if h < s else ""}><summary>{esc(hier or "(top)")} '
                   f'<span class="muted">{h}/{s} bits ({pct(h, s):.1f}%)</span></summary>')
        for sig, bits in sorted(sigs.items(), key=lambda kv: (all(v > 0 for v in kv[1].values()), kv[0])):
            out.append(signal_details(sig, bits.items(), f"{esc(c.names[f])}.source.html#L{sigline[sig]}"))
        out.append("</details>")
    return "".join(out)


def p_ctrl(c: Code, f: str) -> str:
    out = []
    for typ in (t for t in c.summ if t != "toggle"):
        pts = sorted((p for p in c.file_points(f) if p["type"] == typ), key=lambda p: (p["count"] > 0, p["line"]))
        if not pts:
            continue
        rows = "".join(
            f'<tr><td class="l mono"><a href="{esc(c.names[f])}.source.html#L{p["line"]}">line {p["line"]}</a></td>'
            f'<td class="l">{esc(p["what"])}</td><td class="l mono">{esc(p["lines"])}</td>'
            f'<td class="mono">{"<span class=z-txt>0</span>" if p["count"] == 0 else p["count"]}</td></tr>' for p in pts)
        h = sum(p["count"] > 0 for p in pts)
        out.append(f'<h2>{esc(typ.capitalize())} <span class="muted">({h}/{len(pts)})</span></h2>'
                   f'<table><tr><th class="l">location</th><th class="l">kind</th><th class="l">lines</th><th>hits</th></tr>{rows}</table>')
    return "".join(out) or '<p class="muted">No line or branch points in this file (pure assigns have toggle points only).</p>'


def p_uncovered(c: Code) -> str:
    # one row per (file, type, signal/block, instance); toggle bits collapse into one row per signal
    agg: dict[tuple, dict] = {}
    for p in c.holes:
        base = bit_key(p["what"])[0] if p["type"] == "toggle" else (p["what"] or p["type"])
        k = (p["file"], p["type"], base, p["hier"], p["line"] if p["type"] != "toggle" else 0)
        a = agg.setdefault(k, {"line": p["line"], "bits": []})
        a["bits"].append(p["what"])
    rows = []
    for (f, typ, base, hier, _), a in sorted(agg.items(), key=lambda kv: (c.names[kv[0][0]], kv[1]["line"], kv[0][2])):
        n = c.names[f]
        detail = f'{len(a["bits"])} bit(s): ' + ", ".join(b[len(base):] or b for b in a["bits"][:8]) + (" …" if len(a["bits"]) > 8 else "") \
            if typ == "toggle" else ""
        text = f"{n} {typ} {base} {hier}".lower()
        rows.append(f'<tr data-t="{esc(text)}" data-ty="{esc(typ)}"><td class="l">{esc(typ)}</td>'
                    f'<td class="l mono"><a href="{esc(n)}.source.html#L{a["line"]}">{esc(n)}:{a["line"]}</a></td>'
                    f'<td class="l mono">{esc(base)}</td><td class="l mono muted">{esc(hier)}</td>'
                    f'<td class="l mono muted">{esc(detail)}</td></tr>')
    types = sorted({p["type"] for p in c.holes})
    opts = '<option value="">all types</option>' + "".join(f'<option value="{esc(t)}">{esc(t)}</option>' for t in types)
    return (f'<div class="filters"><input id="q" placeholder="Filter by file, signal, instance…"><select id="ty">{opts}</select></div>'
            f'<p class="muted"><span id="n">{len(rows)}</span> of {len(rows)} uncovered groups '
            f'({len(c.holes)} points). Toggle bits are grouped per signal and instance.</p>'
            '<div class="scroll"><table><tr><th class="l">type</th><th class="l">where</th><th class="l">signal / block</th>'
            f'<th class="l">instance</th><th class="l">detail</th></tr>{"".join(rows)}</table></div>{FILTER_JS}')


def build(run_dir: Path, run_id: str, scope: str, shell, *, up: str, reg: str, target: str) -> bool:
    """Write the code pages for one target run. `shell` is dashboard.page; `up` is the
    relative path from the code/ directory to the results root."""
    dat = run_dir / "code_cov" / "merged.dat"
    if not dat.exists():
        return False
    c = Code(dat)
    out = run_dir / "code"
    out.mkdir(exist_ok=True)

    def write(name: str, title: str, body: str, cur: str, crumb_extra: str = ""):
        crumbs = (f'<div class="crumbs"><a href="{up}index.html">Regressions</a> / <a href="../../index.html">{esc(reg)}</a> / '
                  f'<a href="../index.html">{esc(target)}</a> / '
                  f'<a href="index.html">Code coverage</a>{crumb_extra}</div>')
        html_ = shell(f"{title} · {run_id}", f"<h1>{esc(title)}</h1>" + body, root=up, run=reg, target=target, active="code", crumbs=crumbs,
                      side=sidebar(c, cur))
        (out / name).write_text(html_)

    write("index.html", "Code coverage", p_summary(c), "summary")
    write("uncovered.html", "Uncovered", p_uncovered(c), "uncovered", " / Uncovered")
    for f in c.files:
        n = c.names[f]
        h, s, _ = c.file_summ(f)
        tabs = '<nav class="tabs">' + "".join(
            f'<a class="tab" href="{esc(n)}.{k}.html">{label}</a>'
            for k, label in (("source", "Source"), ("toggle", "Toggle"), ("ctrl", "Line / Branch"))) + "</nav>"
        for key, body in (("source", source_table(f, c.by_line[f])), ("toggle", p_toggle(c, f)), ("ctrl", p_ctrl(c, f))):
            t2 = tabs.replace(f'<a class="tab" href="{esc(n)}.{key}.html">', f'<a class="tab on" href="{esc(n)}.{key}.html">')
            lead = f'<div class="muted">{h}/{s} points ({pct(h, s):.1f}%)</div>'
            write(f"{n}.{key}.html", n, lead + t2 + (_legend() if key == "source" else "") + body, n, f" / {esc(n)}")
    return True
