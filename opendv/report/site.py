"""The whole site: the landing page, one page per regression, and the shared assets (stylesheet, script, run list)."""

import json
from pathlib import Path

from ..codecov.pages import CSS as CODE_CSS
from ..htmlkit import esc, pct, read_asset
from .format import CHECK_ICON, COPY_ICON, card, fmt_wall
from .model import Regression
from .pages import build_run, page


CSS = read_asset(__package__, "site.css")
JS = read_asset(__package__, "site.js")


def p_regression(g: Regression) -> str:
    bad = [r for r in g.runs if r.status == "fail"]
    cls = "bad" if bad else "ok"
    cards_ = '<div class="cards">' + "".join([
        card("Regression", "FAIL" if bad else "PASS", f'{len(g.runs)} target(s) · {fmt_wall(g.meta["wall_s"])}', cls),
        card("Tests", f"{g.n_pass}/{g.n_tests}", f"{len(bad)} target(s) with problems", cls),
        card("Master seed", str(g.meta["master_seed"]), g.meta["created"], "dim"),
    ]) + "</div>"
    def num(v: float | None) -> str:
        return f' data-v="{-1 if v is None else v}"'

    f_pct = lambda r: pct(r.f_hit, r.f_size) if r.f_size else None
    c_pct = lambda r: pct(r.c_hit, r.c_size) if r.c_size else None
    rows = "".join(
        f'<tr data-name="{esc(r.target)} {esc(r.s.get("toplevel", ""))}">'
        f'<td class="l" data-v="{esc(r.target)}"><a href="{esc(r.target)}/index.html" class="mono">{esc(r.target)}</a>'
        f'<div class="muted">{esc(r.s.get("toplevel", ""))}</div></td>'
        f'<td class="l st-{r.status}" data-v="{0 if r.status == "fail" else 1}">{r.status}</td>'
        f'<td{num(r.n_pass / r.n_tests if r.n_tests else None)}>{r.n_pass}/{r.n_tests}</td><td>{r.seeds_per_test}</td>'
        f'<td{num(f_pct(r))}>{"" if not r.f_size else str(round(pct(r.f_hit, r.f_size))) + "%"}</td>'
        f'<td{num(c_pct(r))}>{"" if not r.c_size else str(round(pct(r.c_hit, r.c_size), 1)) + "%"}</td>'
        f'<td data-v="{r.s["wall_s"]:.3f}">{fmt_wall(r.s["wall_s"])}</td></tr>'
        for r in sorted(g.runs, key=lambda r: (r.status != "fail", r.target)))
    table = ('<h2>Targets</h2>'
             '<input id="tflt" class="tflt" placeholder="Filter targets" aria-label="Filter targets">'
             '<table class="sortable"><tr><th class="l">target</th><th class="l">status</th><th>tests passed</th>'
             f'<th>seeds</th><th>functional</th><th>code</th><th>wall time</th></tr>{rows}</table>'
             '<div class="muted" id="tnone" hidden>No matching targets.</div>')
    replay = (f'<h2>Replay</h2><div class="repro">'
              f'<code>{esc(g.replay)}</code><button class="copy" data-copy="{esc(g.replay)}" title="Copy command" '
              f'aria-label="Copy command">{COPY_ICON}</button></div>')
    crumbs = '<div class="crumbs"><a href="../index.html">Regressions</a> / ' + esc(g.id) + "</div>"
    body = f'<h1>{esc(g.id)}</h1>' + cards_ + table + replay
    return page(f"{g.id}", body, root="../", run=g.id, active="regression", crumbs=crumbs)


def p_landing(entries: list[dict]) -> str:
    def tests_cell(e: dict) -> str:
        n_fail = e["n_tests"] - e["n_pass"]
        p = pct(e["n_pass"], e["n_tests"])
        # Green share = passed, red share = failed; the red segment keeps a minimum width so one failure shows.
        red = f'<i class="f" style="width:{100 - p:.1f}%"></i>' if n_fail else ""
        return (f'<td class="tests" data-v="{p:.4f}"><span class="cnt">{e["n_pass"]}/{e["n_tests"]}</span>'
                f'<span class="bar split"><i class="p" style="width:{p:.1f}%"></i>{red}</span></td>')

    rows = "".join(
        f'<tr><td class="l"><a href="{e["id"]}/index.html" class="mono">{esc(e["id"])}</a></td>'
        f'<td class="l st-{e["status"]}" data-v="{0 if e["status"] == "fail" else 1}">{e["status"]}</td>'
        f'<td>{len(e["targets"])}</td>{tests_cell(e)}<td data-v="{e["wall_s"]}">{fmt_wall(e["wall_s"])}</td><td>{e["master_seed"]}</td></tr>'
        for e in entries)
    cw = max((len(f'{e["n_pass"]}/{e["n_tests"]}') for e in entries), default=1)
    # Rows arrive newest first; the regression header starts marked descending to say so.
    body = ('<h1>Regressions</h1>'
            f'<table class="landing sortable" style="--cw:{cw}ch"><tr><th class="l desc">regression</th><th class="l">status</th><th>targets</th>'
            f'<th>tests passed</th><th>wall time</th><th>master seed</th></tr>{rows}</table>')
    return page("Regressions", body, root="", active="landing")


def build_site(root: Path, only: Path | None = None, rebuild_all: bool = False) -> Path:
    """Write assets + index; (re)build `only`, or every regression if rebuild_all."""
    root = root.resolve()
    dirs = sorted((p.parent for p in root.glob("*/regression.json") if not p.parent.is_symlink()), reverse=True)
    (root / "assets").mkdir(exist_ok=True)
    (root / "assets" / "site.css").write_text(CSS + CODE_CSS)
    (root / "assets" / "site.js").write_text(JS.replace("__CHECK__", CHECK_ICON))
    entries = []
    for d in dirs:
        g = Regression(d)
        if rebuild_all or (only and d.resolve() == only.resolve()) or not (d / "index.html").exists():
            for r in g.runs:
                build_run(r.dir)
            (d / "index.html").write_text(p_regression(g))
        entries.append(g.entry())
    (root / "assets" / "runs.js").write_text("window.RUNS = " + json.dumps(entries) + ";\n")
    (root / "index.html").write_text(p_landing(entries))
    if dirs:  # `latest` is a symlink to the newest regression
        link = root / "latest"
        if link.is_symlink() or not link.exists():
            link.unlink(missing_ok=True)
            link.symlink_to(dirs[0].name)
    return root / "index.html"
