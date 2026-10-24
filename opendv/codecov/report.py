"""HTML report for Verilator code coverage, built straight from a merged
coverage.dat (verilator_coverage --write output).

Unlike `genhtml` (which only gets per-line counts via the lcov export), this
keeps every point's type, so toggle coverage is shown per signal, per bit.

    python3 -m opendv.codecov.report regress/<ts>/code_cov/merged.dat [-o report.html]
"""

import argparse
import html
from collections import defaultdict
from pathlib import Path

from ..htmlkit import read_asset
from .data import LOW, bit_key, by_file_line, holes, line_status, parse_dat, summarize


CSS = read_asset(__package__, "report.css")


def _pct(h, s):
    return f"{100 * h / s:.1f}%" if s else "-"


def _cls(n):
    return "z" if n == 0 else ("lo" if n < LOW else "ok")


def signal_details(sig, bits, link=None):
    """One signal: collapsed row = name + toggled/total bits + bar; click to
    open the per-bit grid (MSB left, cell = toggle count, red = never)."""
    bits = list(bits)
    hit = sum(c > 0 for _, c in bits)
    pct = 100 * hit / len(bits)
    cells = "".join(
        f"<span class='bit {_cls(c)}' title='{html.escape(sig)}{'' if b is None else f'[{b}]'}: {c} toggles'>"
        f"{b if c == 0 and b is not None else (c if c < 1000 else '1k+')}</span>"
        for b, c in sorted(bits, key=lambda x: -1 if x[0] is None else -x[0]))
    name = f"<a href='{link}'>{html.escape(sig)}</a>" if link else html.escape(sig)
    cls = "full" if hit == len(bits) else ("none" if hit == 0 else "some")
    return (f"<details class='sig {cls}'><summary><span class='sname mono'>{name}</span>"
            f"<span class='spct mono'>{pct:.0f}%</span><span class='bar sbar'><i style='width:{pct:.0f}%'></i></span>"
            f"<span class='scnt mono mut'>{hit}/{len(bits)} bits</span></summary>"
            f"<div class=bits>{cells}</div></details>")


def _source_section(fid, path, pts_by_line, merged_pts):
    src = Path(path)
    text = src.read_text().splitlines() if src.exists() else []
    h = sum(p["count"] > 0 for p in merged_pts)
    out = [f"<section id='{fid}'><h2>{html.escape(src.name)} "
           f"<span class=mut>{h}/{len(merged_pts)} points ({_pct(h, len(merged_pts))})</span></h2>"]
    if not text:
        out.append(f"<p class=mut>source not found: {html.escape(path)}</p></section>")
        return "".join(out)
    out.append("<table class=src>")
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
        tags = "".join(
            f"<span class='tag {'z' if p['count'] == 0 else 'ok'}'>{html.escape(p['what'] or p['type'])} &times;{p['count']}</span>"
            for p in ctl if p["line"] == n)
        out.append(f"<tr id='{fid}-L{n}' class='{st}'><td class='ln'><a href='#{fid}-L{n}'>{n}</a>"
                   f"<td class='gut mono'>{gut}<td class='code'><pre>{html.escape(code) or ' '}</pre>{tags}</tr>")
        if tog:
            chips = defaultdict(list)
            for p in tog:
                base, bit = bit_key(p["what"])
                chips[base].append((bit, p["count"]))
            row = "".join(signal_details(base, bits) for base, bits in chips.items())
            out.append(f"<tr class='{st} togrow'><td><td><td>{row}</tr>")
    out.append("</table></section>")
    return "".join(out)


def render_html(points: list[dict], title="Code coverage") -> str:
    summ = summarize(points)
    tot_h = sum(v["hit"] for v in summ.values())
    tot_s = sum(v["size"] for v in summ.values())
    flines = by_file_line(points)
    fids = {f: f"src{i}" for i, f in enumerate(sorted(flines))}
    types = [t for t in summ if t != "toggle"]

    nav = ["<nav><a href='#summary'>Summary</a><a href='#files'>Files</a><a href='#toggle'>Toggle</a>"]
    nav += [f"<a href='#{t}'>{t.capitalize()}</a>" for t in types]
    nav.append("<span class=sep>Source:</span>")
    nav += [f"<a href='#{fid}'>{html.escape(Path(f).name)}</a>" for f, fid in fids.items()]
    nav.append("</nav>")

    out = [f"<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
           f"<title>{html.escape(title)}</title><style>{CSS}</style><body>" + "".join(nav),
           f"<h1 id=summary>{html.escape(title)}</h1><div class=mut>Verilator coverage points: {tot_h}/{tot_s} hit ({_pct(tot_h, tot_s)})</div>",
           "<div class=cards>"]
    for t, v in summ.items():
        w = 100 * v["hit"] / v["size"] if v["size"] else 0
        out.append(f"<a class=card href='#{t}'><span class=mut>{t}</span><b>{_pct(v['hit'], v['size'])}</b>"
                   f"{v['hit']}/{v['size']}<div class=bar><i style='width:{w:.1f}%'></i></div></a>")
    out.append("</div><div class=legend><span><span class='bit z'>0</span>never hit</span>"
               f"<span><span class='bit lo'>n</span>hit &lt; {LOW} times</span>"
               f"<span><span class='bit ok'>n</span>hit &ge; {LOW} times</span>"
               "<span><span class='sw ok'></span>covered line</span>"
               "<span><span class='sw part'></span>partly covered</span>"
               "<span><span class='sw z'></span>never hit</span></div>")

    # -- file index (like genhtml's directory page) --
    out.append("<h2 id=files>Files</h2><table><tr><th>file<th class=n>all points")
    out += [f"<th class=n>{t}" for t in summ]
    out.append("</tr>")
    for f, fid in fids.items():
        fp = [p for p in points if p["file"] == f]
        fs = summarize(fp)
        h, s = sum(v["hit"] for v in fs.values()), sum(v["size"] for v in fs.values())
        cells = "".join(
            f"<td class='n mono'>{fs[t]['hit']}/{fs[t]['size']}</td>" if t in fs else "<td class=n>-</td>" for t in summ)
        out.append(f"<tr><td><a href='#{fid}'>{html.escape(Path(f).name)}</a>"
                   f"<td class='n mono'>{h}/{s} ({_pct(h, s)}){cells}</tr>")
    out.append("</table>")

    # -- toggle: per file/instance, per signal, one cell per bit (MSB left) --
    out.append("<h2 id=toggle>Toggle coverage</h2>")
    tog = [p for p in points if p["type"] == "toggle"]
    groups = defaultdict(lambda: defaultdict(dict))
    sigline = {}
    for p in tog:
        base, bit = bit_key(p["what"])
        groups[(p["file"], p["hier"])][base][bit] = p["count"]
        sigline[(p["file"], base)] = p["line"]
    for (f, hier), sigs in sorted(groups.items()):
        h = sum(c > 0 for b in sigs.values() for c in b.values())
        s = sum(len(b) for b in sigs.values())
        open_ = " open" if h < s else ""
        out.append(f"<details{open_}><summary>{html.escape(Path(f).name)} "
                   f"<span class='mut mono'>{html.escape(hier)}</span> &mdash; {h}/{s} bits ({_pct(h, s)})</summary>")
        for sig, bits in sorted(sigs.items(), key=lambda kv: (all(c > 0 for c in kv[1].values()), kv[0])):
            out.append(signal_details(sig, bits.items(), f"#{fids[f]}-L{sigline[(f, sig)]}"))
        out.append("</details>")

    # -- line / branch / other: one row per point, holes first, linked to source --
    for typ in types:
        pts = sorted((p for p in points if p["type"] == typ), key=lambda p: (p["count"] > 0, p["file"], p["line"]))
        out.append(f"<h2 id='{typ}'>{typ.capitalize()} coverage <span class=mut>({summ[typ]['hit']}/{summ[typ]['size']})</span></h2>"
                   "<table><tr><th>location<th>kind<th>lines<th class=n>hits</tr>")
        for p in pts:
            z = ' class=z-txt' if p["count"] == 0 else ""
            out.append(f"<tr><td class=mono><a href='#{fids[p['file']]}-L{p['line']}'>{html.escape(Path(p['file']).name)}:{p['line']}</a>"
                       f"<td>{html.escape(p['what'])}<td class=mono>{html.escape(p['lines'])}"
                       f"<td class='n mono'><span{z}>{p['count']}</span></tr>")
        out.append("</table>")

    # -- annotated source, one section per file --
    out.append("<h2>Source</h2>")
    for f, fid in fids.items():
        fm = {}
        for n_pts in flines[f].values():
            for p in n_pts:
                fm[id(p)] = p
        out.append(_source_section(fid, f, flines[f], list(fm.values())))
    out.append("</body></html>")
    return "".join(out)


def write_report(dat: Path, out_html: Path, title="Code coverage") -> dict:
    pts = parse_dat(dat)
    out_html.write_text(render_html(pts, title))
    return {"html": str(out_html), "by_type": summarize(pts),
            "holes": [{"type": p["type"], "file": Path(p["file"]).name, "line": p["line"],
                       "what": p["what"], "hier": p["hier"]} for p in holes(pts)]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dat", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    a = ap.parse_args()
    r = write_report(a.dat, a.out or a.dat.with_name("report.html"))
    print(r["html"])
    for t, v in r["by_type"].items():
        print(f"  {t:<8} {v['hit']}/{v['size']}  {_pct(v['hit'], v['size'])}")
