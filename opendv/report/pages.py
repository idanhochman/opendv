"""The pages of one target in a regression: overview, tests, failures, functional and code coverage, runs, one test."""

from pathlib import Path

from ..codecov.pages import build as build_code_pages
from ..htmlkit import bar, esc, pct
from ..run import repro_cmd
from .format import COPY_ICON, card, fmt_t, fmt_wall, norm_msg, rel, test_href
from .model import Run


SECTIONS = [("index", "Overview"), ("tests", "Tests"), ("failures", "Failures"),
            ("functional", "Functional coverage"), ("code", "Code coverage"), ("runs", "Runs")]


MAX_HOLE_ROWS = 25


def page(title: str, body: str, *, root: str, run: str = "", active: str = "", test: str = "",
         crumbs: str = "", side: str = "", target: str = "") -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<script>try{{var t=localStorage.getItem("theme");if(t)document.documentElement.dataset.theme=t;if(localStorage.getItem("nav")=="off")document.documentElement.classList.add("nav-off")}}catch(e){{}}</script>
<link rel="stylesheet" href="{root}assets/site.css"></head>
<body data-root="{root}" data-run="{esc(run)}" data-target="{esc(target)}" data-page="{esc(active)}" data-test="{esc(test)}">
<button id="navtoggle" title="Show/hide navigation" aria-label="Toggle navigation">☰</button>
<aside id="side"{' data-static="1"' if side else ''}>{side or f'<noscript>Enable JavaScript for the navigation, or open <a href="{root}index.html">the index</a>.</noscript>'}</aside>
<main>{crumbs}{body}</main>
<script src="{root}assets/runs.js"></script><script src="{root}assets/site.js"></script>
</body></html>"""


def run_page(r: Run, key: str, body: str, *, title: str, test: str = "") -> str:
    """A page inside a target's run. `key` is the active tab; `test` set for test pages."""
    up = "../" if test else ""
    tabs = "".join(
        f'<a class="tab{" on" if k == key else ""}" href="{up}{k}.html">{label}</a>'
        for k, label in SECTIONS)
    crumbs = (f'<div class="crumbs"><a href="{up}../../index.html">Regressions</a> / '
              f'<a href="{up}../index.html">{esc(r.reg)}</a> / <a href="{up}index.html">{esc(r.target)}</a>'
              + (f' / {esc(test)}' if test else "") + "</div>")
    head = (f'<h1>{esc(title)}</h1><div class="muted">{esc(r.target)} ({esc(r.s.get("toplevel", ""))}) · '
            f'{esc(r.scope)} · {len(r.names)} tests × {r.seeds_per_test} seeds · {fmt_wall(r.s["wall_s"])}</div>')
    return page(f"{title} · {r.id}", head + f'<nav class="tabs">{tabs}</nav>' + body,
                root=up + "../../", run=r.reg, target=r.target, active=key, test=test, crumbs=crumbs)


def cards(r: Run) -> str:
    cls = "bad" if r.bad_runs else "ok"
    by = r.cc.get("by_type", {})
    holes = r.cov.get("holes", [])
    return '<div class="cards">' + "".join([
        card("Target", "FAIL" if r.bad_runs else "PASS", f'{len(r.names)} tests × {r.seeds_per_test} seeds · {fmt_wall(r.s["wall_s"])}', cls),
        card("Runs passed", f"{r.n_pass}/{r.n_tests}", f"{len(r.bad_runs)} run(s) with problems", cls),
        card("Functional", f"{pct(r.f_hit, r.f_size):.0f}%" if r.f_size else "n/a",
             f"{r.f_hit}/{r.f_size} bins · {len(holes)} hole(s)" if r.f_size else
             ("no passing runs to merge" if r.func_configured else "not defined for this target"),
             ("ok" if not holes else "warn") if r.f_size else "dim"),
        card("Code", f"{pct(r.c_hit, r.c_size):.1f}%" if r.c_size else "n/a",
             " · ".join(f'{t} {pct(v["hit"], v["size"]):.0f}%' for t, v in by.items())
             or ("no passing runs" if r.code_requested else "not collected"),
             "" if r.c_size else "dim"),
    ]) + "</div>"


def matrix(r: Run, link_tests: bool = True) -> str:
    """One row per test; one cell per run (each test has its own seeds, so the columns are run numbers)."""
    head = '<tr><th class="l">test</th>' + "".join(f"<th>{i}</th>" for i in range(1, r.seeds_per_test + 1)) + "</tr>"
    rows = []
    for n in r.names:
        name = f'<a href="{test_href(n)}">{esc(n)}</a>' if link_tests else esc(n)
        cells = [f'<tr><td class="l mono">{name}</td>']
        for x in r.test_results(n):
            sym = {"pass": "✓", "fail": "✗", "skip": "·", "error": "!"}[x["status"]]
            tip = f'{n} seed {x["seed"]}: {x["status"]}, {fmt_t(x["sim_ns"])}'
            cells.append(f'<td class="c-{x["status"]}" title="{esc(tip)}">{sym}</td>')
        rows.append("".join(cells) + "</tr>")
    return f'<div class="scroll"><table class="matrix">{head}{"".join(rows)}</table></div>'


def fail_groups(r: Run, name: str) -> list[dict]:
    """Failures of one test grouped by message-with-data-masked."""
    groups: dict[str, dict] = {}
    for x in r.test_results(name):
        if x["status"] != "fail":
            continue
        g = groups.setdefault(norm_msg(x["message"]), {"example": x["message"], "items": []})
        g["items"].append(x)
    return list(groups.values())


def replay_box(cmd: str) -> str:
    return (f'<h2>Replay</h2><div class="repro"><code>{esc(cmd)}</code>'
            f'<button class="copy" data-copy="{esc(cmd)}" title="Copy command" aria-label="Copy command">{COPY_ICON}</button></div>')


def replay_flags(r: Run) -> str:
    return (" --code-cov" if r.code_requested else "") + (" --waves" if r.has_waves else "")


def replay_cmd(r: Run, selector: str, seeds: list[int]) -> str:
    if len(seeds) == 1 and ":" in selector:  # one test, one seed: the debug command
        return repro_cmd(*selector.split(":"), seeds[0])
    return f'opendv regress {selector} --seed-list {" ".join(map(str, seeds))}{replay_flags(r)}'


def failure_block(r: Run, name: str, detail: bool) -> str:
    gs = fail_groups(r, name)
    title = esc(name) if detail else f'<a href="{test_href(name)}">{esc(name)}</a>'
    out = [f'<div class="fail"><h3><span class="mono">{title}</span> '
           f'<span class="muted">{sum(len(g["items"]) for g in gs)} of {len(r.test_results(name))} seeds failed</span></h3>']
    for g in gs:
        seeds = [x["seed"] for x in g["items"]]
        out.append(f'<div class="fmsg">{esc(g["example"] or "(no message)")}</div>'
                   f'<div class="muted">seeds {", ".join(map(str, seeds))}</div>')
        if detail:
            # Waves cell: the waveform's path and the failure time (there is no viewer launcher).
            waves = lambda x: (f'<td class="l mono">{esc(rel(Path(x["run_dir"]) / "dump.fst", r.dir))} @ '
                               f'{fmt_t(x.get("detected_ns", x["sim_ns"]))}</td>' if r.has_waves else "")
            rows = "".join(
                f'<tr><td>{x["seed"]}</td><td>{fmt_t(x.get("detected_ns", x["sim_ns"]))}</td>{waves(x)}'
                f'<td class="l"><a href="../{esc(rel(Path(x["run_dir"]) / "sim.log", r.dir))}">sim.log</a></td></tr>'
                for x in g["items"])
            out.append(f'<table><tr><th>seed</th><th>detected</th>{"<th class=\"l\">waves</th>" if r.has_waves else ""}'
                       f'<th class="l">log</th></tr>{rows}</table>')
        cmd = repro_cmd(r.target, name, seeds[0])
        out.append(f'<div class="repro"><code>{esc(cmd)}</code>'
                   f'<button class="copy" data-copy="{esc(cmd)}" title="Copy command" aria-label="Copy command">{COPY_ICON}</button></div>')
    out.append("</div>")
    return "".join(out)


def p_overview(r: Run) -> str:
    n_bad = sum(r.test_status(n) == "fail" for n in r.names)
    if r.bad_runs:
        msg = (f'<p><b>{n_bad} of {len(r.names)} tests</b> failed in at least one seed. '
               f'<a href="failures.html">See failures →</a></p>')
    else:
        msg = ""
    sel = f'{r.target}:{r.s["testcase"]}' if r.s.get("testcase") else r.target
    if r.s.get("seed_mode") == "list":  # fixed seeds: every test ran the same list
        cmd = replay_cmd(r, sel, [x["seed"] for x in r.test_results(r.names[0])])
    else:  # random seeds: the master seed regenerates every test's seeds
        cmd = f'opendv regress {sel} --master-seed {r.s["master_seed"]} --seeds {r.seeds_per_test}{replay_flags(r)}'
    return cards(r) + "<h2>Tests × seeds</h2>" + matrix(r) + msg + replay_box(cmd)


def p_tests(r: Run) -> str:
    rows = []
    for n in r.names:
        res = r.test_results(n)
        npass = sum(x["status"] == "pass" for x in res)
        st = r.test_status(n)
        rows.append(f'<tr><td class="l mono"><a href="{test_href(n)}">{esc(n)}</a></td>'
                    f'<td class="l st-{st}">{st}</td><td>{npass}/{len(res)}</td>'
                    f'<td>{fmt_t(sum(x["sim_ns"] for x in res) / max(1, len(res)))}</td></tr>')
    return ('<table><tr><th class="l">test</th><th class="l">status</th><th>seeds passed</th><th>avg sim time</th></tr>'
            + "".join(rows) + "</table>")


def p_failures(r: Run) -> str:
    out = []
    for x in r.runs:
        if x["status"] == "error":
            out.append(f'<div class="fail"><h3>{esc(x["test"])} seed {x["seed"]} — run error</h3>'
                       f'<pre>{esc(x.get("runner_error") or "")}</pre></div>')
    bad = [n for n in r.names if r.test_status(n) == "fail"]
    if not bad and not out:
        return '<p class="muted">No failures.</p>'
    note = ('<p class="muted">Times are when the scoreboard noticed, not when the bus diverged. '
            'Messages differing only in data values are grouped.</p>')
    return note + "".join(out) + "".join(failure_block(r, n, detail=False) for n in bad)


def p_functional(r: Run) -> str:
    if not r.groups:
        return ('<p class="muted">No functional coverage merged (no passing runs).</p>' if r.func_configured else
                '<p class="muted">This target defines no functional coverage '
                '(<code>coverage.functional</code> in its opendv.yaml).</p>')
    grp = "".join(f'<tr><td class="l mono">{esc(g)}</td><td>{v["hit"]}/{v["size"]}</td>'
                  f'<td class="pcbar"><div class="pcwrap"><span class="pc">{pct(v["hit"], v["size"]):.0f}%</span>{bar(v["hit"], v["size"])}</div></td></tr>'
                  for g, v in r.groups.items())
    rows = []
    for point, bs in r.bins.items():
        for b, hits in bs.items():
            rows.append((hits != 0, point, str(b), hits, r.first.get(f"{point} {b}")))
    rows.sort(key=lambda x: (x[0], x[1], x[2]))  # holes first
    brow = "".join(f'<tr class="{"" if h else "hole"}"><td class="l mono">{esc(p)}</td><td class="l mono">{esc(b)}</td>'
                   f'<td>{hits}</td><td class="l mono">{"" if fs is None else f"{esc(fs['test'])} · {fs['seed']}"}</td></tr>' for h, p, b, hits, fs in rows)
    return (f'<h2>Groups</h2><table class="cov"><tr><th class="l">group</th><th>hit</th><th class="l">coverage</th></tr>{grp}</table>'
            f'<h2>Bins <span class="muted">({len(rows)}, holes first)</span></h2>'
            f'<table><tr><th class="l">point</th><th class="l">bin</th><th>hits</th><th class="l">first hit (test · seed)</th></tr>{brow}</table>')


def p_code(r: Run) -> str:
    cc = r.cc
    if not cc.get("by_type"):
        return ('<p class="muted">Collected, but no passing runs to merge (failed runs are excluded).</p>'
                if r.code_requested else
                '<p class="muted">Not collected (run <code>opendv regress --code-cov</code>).</p>')
    rows = "".join(f'<tr><td class="l">{t}</td><td>{v["hit"]}/{v["size"]}</td>'
                   f'<td class="pcbar"><div class="pcwrap"><span class="pc">{pct(v["hit"], v["size"]):.1f}%</span>{bar(v["hit"], v["size"])}</div></td></tr>'
                   for t, v in cc["by_type"].items())
    # One row per (type, file, signal base) to keep the hole list short.
    agg: dict[tuple, list] = {}
    for h in cc.get("holes", []):
        agg.setdefault((h["type"], h["file"], h["line"], h["what"].split("[")[0]), []).append(h["what"])
    shown = sorted(agg.items())[:MAX_HOLE_ROWS]
    hrows = "".join(
        f'<tr><td class="l">{t}</td><td class="l mono">{esc(f)}:{ln}</td><td class="l mono">{esc(base)}</td>'
        f'<td class="l mono muted">{len(w)} point(s)'
        + (f': {esc(", ".join(w[:6]))}{" …" if len(w) > 6 else ""}' if t == "toggle" else "") + "</td></tr>"
        for (t, f, ln, base), w in shown)
    more = (f'<p class="muted">Showing {len(shown)} of {len(agg)} groups. '
            f'<a href="code/index.html">See the detailed report for all of them →</a></p>' if len(agg) > len(shown) else "")
    return (f'<h2>Summary</h2><table class="cov"><tr><th class="l">type</th><th>hit</th><th class="l">coverage</th></tr>{rows}</table>'
            f'<p><a href="code/index.html">Open the detailed code coverage report →</a></p>'
            f'<h2>Uncovered <span class="muted">({len(agg)} groups)</span></h2>'
            f'<table><tr><th class="l">type</th><th class="l">where</th><th class="l">signal / block</th>'
            f'<th class="l">detail</th></tr>{hrows}</table>{more}')


def p_runs(r: Run) -> str:
    rows, seen = [], set()
    for x in r.runs:
        mine = {k for k, v in r.first.items() if v["test"] == x["test"] and v["seed"] == x["seed"]}
        new = len(mine - seen)
        seen |= mine
        d = Path(x["run_dir"])
        rows.append(f'<tr><td class="l mono"><a href="{test_href(x["test"])}">{esc(x["test"])}</a></td><td>{x["seed"]}</td>'
                    f'<td class="l st-{x["status"]}">{x["status"]}</td><td>{fmt_t(x["sim_ns"])}</td>'
                    f'<td data-v="{x["wall_s"]:.3f}">{fmt_wall(x["wall_s"])}</td><td>+{new}</td>'
                    f'<td class="l"><a href="{esc(rel(d / "sim.log", r.dir))}">log</a>'
                    + (f' · <a href="{esc(rel(d / "dump.fst", r.dir))}">fst</a>' if r.has_waves else "") + "</td></tr>")
    return ('<table><tr><th class="l">test</th><th>seed</th><th class="l">status</th><th>sim time</th><th>wall time</th>'
            f'<th>new bins</th><th class="l">files</th></tr>{"".join(rows)}</table>')


def p_test(r: Run, name: str) -> str:
    res = r.test_results(name)
    st = r.test_status(name)
    n_ok = sum(x["status"] == "pass" for x in res)
    avg = sum(x["sim_ns"] for x in res) / max(1, len(res))
    rows = "".join(
        f'<tr><td>{x["seed"]}</td><td class="l st-{x["status"]}">{x["status"]}</td><td>{fmt_t(x["sim_ns"])}</td>'
        f'<td class="l"><a href="../{esc(rel(Path(x["run_dir"]) / "sim.log", r.dir))}">sim.log</a>'
        + (f' · <a href="../{esc(rel(Path(x["run_dir"]) / "dump.fst", r.dir))}">fst</a>' if r.has_waves else "") + "</td></tr>"
        for x in res)
    seeds_tbl = ('<table><tr><th>seed</th><th class="l">status</th><th>sim time</th><th class="l">files</th></tr>'
                 f'{rows}</table>')
    body = ('<div class="cards">'
            + card("Status", st.upper(), f"{n_ok}/{len(res)} seeds passed", "ok" if st == "pass" else "bad")
            + card("Avg sim time", fmt_t(avg), "per seed") + "</div>"
            f'<h2>Seeds</h2>{seeds_tbl}'
            + replay_box(replay_cmd(r, f"{r.target}:{name}", [x["seed"] for x in res])))
    if st == "fail":
        body += "<h2>Failures</h2>" + failure_block(r, name, detail=True)
    body += ('<p class="muted">Coverage is measured per regression, not per test — see the '
             '<a href="../functional.html">Functional</a> and <a href="../code.html">Code</a> tabs.</p>')
    return body


def build_run(d: Path) -> None:
    r = Run(d)
    pages = {"index": ("Overview", p_overview(r)), "tests": ("Tests", p_tests(r)),
             "failures": ("Failures", p_failures(r)), "functional": ("Functional coverage", p_functional(r)),
             "code": ("Code coverage", p_code(r)), "runs": ("Runs", p_runs(r))}
    for k, (title, body) in pages.items():
        (d / f"{k}.html").write_text(run_page(r, k, body, title=title))
    build_code_pages(d, r.id, r.scope, page, up="../../../", reg=r.reg, target=r.target)
    (d / "tests").mkdir(exist_ok=True)
    for n in r.names:
        (d / "tests" / f"{n}.html").write_text(run_page(r, "tests", p_test(r, n), title=n, test=n))
