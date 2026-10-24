"""`opendv regress`: build targets, run every selected test once per seed, merge coverage, write the dashboard."""

import json
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from . import config
from .coverage import group_summary, load_cov, merge_code_coverage, merge_coverage, write_merged_yaml
from .report import build_site
from .results import fill_result
from .run import repro_cmd
from .seeds import draw_seeds, new_master_seed
from .simulator import build_target, list_target, simulate, test_filter


@dataclass
class Options:
    seeds: int | list[int] | None = None  # CLI override: a count (random) or an explicit list
    master_seed: int | None = None
    jobs: int = os.cpu_count() or 4
    code_cov: bool = False
    waves: bool | None = None  # CLI override of the config; None = use the config
    cov_from_failed: bool = False
    skip_build: bool = False
    out: Path | None = None
    argv: str = ""


def build_dir(project: config.Project, target: config.Target) -> Path:
    return project.results_dir / "_build" / target.name


def use_waves(project: config.Project, target: config.Target, opts: Options) -> bool:
    return opts.waves if opts.waves is not None else project.waves_for(target)


def run_test(spec: dict) -> dict:
    """Worker: one test, one seed, one simulator process. Never raises -- a
    crashed run is a result too (status='error'), not a reason to abort."""
    run_dir = Path(spec["run_dir"])
    t0 = time.monotonic()
    err = simulate(spec, run_dir, test_filter="^" + re.escape(spec["fullname"]) + "$", seed=spec["seed"],
                    env={"OPENDV_SEED": str(spec["seed"]), "OPENDV_RUN_DIR": str(run_dir)}, waves=spec["waves"])
    return {"target": spec["target"], "test": spec["test"], "fullname": spec["fullname"], "seed": spec["seed"],
            "run_dir": str(run_dir), "wall_s": time.monotonic() - t0, "runner_error": err, "t0": t0, "t1": time.monotonic()}


def collect_target(project: config.Project, target: config.Target, runs: list[dict], out: Path,
                   tests: list[str], seeds: dict[str, list[int]], seed_mode: str, filt: list[str],
                   master: int, opts: Options) -> dict:
    """Parse one target's finished runs, merge coverage, print and write its summary."""
    order = {t: i for i, t in enumerate(tests)}
    runs = sorted(runs, key=lambda r: (order[r["test"]], r["seed"]))
    wall = max(r["t1"] for r in runs) - min(r["t0"] for r in runs)
    cov_by_run: dict[tuple[int, int], dict] = {}
    for r in runs:
        r.pop("t0"), r.pop("t1")
        fill_result(r)
        cov = load_cov(Path(r["run_dir"]) / target.functional_cov) if target.functional_cov else {}
        # A failed test's coverage isn't trustworthy: the run stopped where the failure hit.
        if cov and (r["status"] in ("pass", "skip") or opts.cov_from_failed):
            cov_by_run[(order[r["test"]], r["seed"])] = cov
    merged = merge_coverage(cov_by_run)
    write_merged_yaml(out / "merged_coverage.yml", merged["bins"])
    ok_dirs = [Path(r["run_dir"]) for r in runs if r["status"] in ("pass", "skip") or opts.cov_from_failed]
    code_cov = merge_code_coverage(out, ok_dirs, f"{target.name} code coverage") if opts.code_cov else None

    n_seeds = max(len(v) for v in seeds.values())
    print(f"\n=== {target.name} ({target.toplevel})  {len(tests)} test(s) x {n_seeds} seed(s)")
    print(f"{'test':<40} {'passed':>7} {'sim ns':>9} {'wall s':>7}  new bins")
    seen: set = set()
    for name in tests:
        mine_runs = [r for r in runs if r["test"] == name]
        new = 0
        for r in mine_runs:
            mine = {k for k, v in merged["first_seed"].items() if v == (order[name], r["seed"])}
            new += len(mine - seen)
            seen |= mine
        print(f"{name:<40} {f'{sum(r['status'] == 'pass' for r in mine_runs)}/{len(mine_runs)}':>7} "
              f"{sum(r['sim_ns'] for r in mine_runs):>9.0f} {sum(r['wall_s'] for r in mine_runs):>7.1f}  +{new}")
    bad = [r for r in runs if r["status"] in ("fail", "error")]
    if bad:
        print("FAILURES")
    for r in bad:
        rd = Path(r["run_dir"])
        waves = f"   waves: {rd / 'dump.fst'}" if use_waves(project, target, opts) else ""
        print(f"  {r['test']} seed {r['seed']}: {r['status']}{waves}\n      log: {rd / 'sim.log'}")
        print(f"      detected @ {r.get('detected_ns', r['sim_ns']):>7.0f} ns  {r['message']}")
        print(f"      repro: {repro_cmd(target.name, r['test'], r['seed'])}")

    holes = sorted(k for k, h in merged["bins"].items() if h == 0)
    if target.functional_cov:
        skipped = len(runs) - len(cov_by_run)
        print(f"MERGED FUNCTIONAL COVERAGE over {len(cov_by_run)} of {len(runs)} run(s)"
              + (f"  ({skipped} excluded: failed/errored; --cov-from-failed to include)" if skipped else ""))
        for grp, (hit, size) in group_summary(merged["bins"]).items():
            print(f"  {grp:<20} {hit:>3}/{size:<3} {100 * hit / size:5.1f}%")
        for name, b in holes:
            print(f"  hole: {name} {b}")
    if code_cov:
        print(f"CODE COVERAGE ({code_cov['runs']} run(s) merged)")
        for t, v in code_cov["by_type"].items():
            print(f"  {t:<8} {v['hit']:>4}/{v['size']:<4} {100 * v['hit'] / v['size']:5.1f}%")

    summary = {
        "target": target.name, "toplevel": target.toplevel, "master_seed": master, "seed_mode": seed_mode,
        "tests": tests, "seeds": seeds,
        "wall_s": wall, "testcase": ", ".join(filt) if filt else None,
        "functional_configured": bool(target.functional_cov),
        "waves": use_waves(project, target, opts),
        "runs": runs,
        "coverage": {
            "groups": {g: {"hit": h, "size": s} for g, (h, s) in group_summary(merged["bins"]).items()},
            "holes": [f"{n} {b}" for n, b in holes],
            "first_seed": {f"{n} {b}": {"test": tests[i], "seed": sd} for (n, b), (i, sd) in merged["first_seed"].items()},
        },
        "code_coverage": code_cov,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def regress(project: config.Project, selections: list[config.Selection], opts: Options) -> int:
    """`opendv regress`: run the selected targets as one regression. Returns the exit code."""
    master = opts.master_seed or new_master_seed()
    code_cov = opts.code_cov or project.defaults.code_cov
    reg = opts.out.resolve() if opts.out else project.results_dir / time.strftime("%Y%m%d-%H%M%S")
    n = 1
    while reg.exists() and not opts.out:  # two regressions started in the same second
        n += 1
        reg = project.results_dir / f"{time.strftime('%Y%m%d-%H%M%S')}-{n}"
    reg.mkdir(parents=True, exist_ok=True)
    targets = [s.target for s in selections]

    print(f"regression {reg.name}   master seed {master}   (replay: --master-seed {master})", flush=True)
    t_start = time.monotonic()
    if not opts.skip_build:
        print(f"building {len(targets)} target(s): {', '.join(t.name for t in targets)}", flush=True)
        with ThreadPoolExecutor(max_workers=max(1, min(len(targets), opts.jobs))) as pool:
            built = list(pool.map(lambda t: build_target(project, t, build_dir(project, t), code_cov=code_cov,
                                                         waves=use_waves(project, t, opts)), targets))
        broken = [b for b in built if b[2]]
        for name, secs, err in built:
            print(f"  {name}: {'FAILED' if err else f'built in {secs:.1f}s'}", flush=True)
        for name, _, err in broken:
            print(f"\nBUILD ERROR in {name}:\n{err}", file=sys.stderr)
        if broken:
            return 2

    def base(t: config.Target) -> dict:
        return {"target": t.name, "toplevel": t.toplevel, "modules": t.modules,
                "sys_path": [str(p) for p in t.sys_path], "build_dir": str(build_dir(project, t))}

    # Which tests does each target have? cocotb only knows inside a simulator.
    with ProcessPoolExecutor(max_workers=max(1, min(len(targets), opts.jobs))) as pool:
        listed = {r["target"]: r for r in pool.map(
            list_target, [{**base(t), "list_dir": str(build_dir(project, t) / "_list")} for t in targets])}
    plan: dict[str, dict] = {}
    for s in selections:
        t = s.target
        if listed[t.name]["error"]:
            print(f"\nCANNOT LIST TESTS of {t.name}:\n{listed[t.name]['error']}", file=sys.stderr)
            return 2
        shorts = [f.rsplit(".", 1)[1] for f in listed[t.name]["names"]]
        dup = sorted({n for n in shorts if shorts.count(n) > 1})
        if dup:  # results, seeds and the dashboard are keyed by the short test name
            print(f"\n{t.name}: test name(s) defined in more than one module: {', '.join(dup)}", file=sys.stderr)
            return 2
        flt = test_filter(s.tests)
        full = [f for f in listed[t.name]["names"] if not flt or re.search(flt, f)]
        if not full:
            print(f"\nno test of {t.name} matches {', '.join(s.tests)} (tests: "
                  f"{', '.join(f.rsplit('.', 1)[1] for f in listed[t.name]['names'])})", file=sys.stderr)
            return 2
        names = [f.rsplit(".", 1)[1] for f in full]
        spec = opts.seeds if opts.seeds is not None else project.seeds_for(t)
        plan[t.name] = {
            "tests": names, "full": dict(zip(names, full)), "mode": "list" if isinstance(spec, list) else "random",
            # every test draws its own seeds, a pure function of (master seed, target, test)
            "seeds": {n_: list(spec) if isinstance(spec, list) else draw_seeds(master, f"{t.name}:{n_}", spec)
                      for n_ in names}}

    specs, by_target = [], {}
    for s in selections:
        t = s.target
        for name in plan[t.name]["tests"]:
            for seed in plan[t.name]["seeds"][name]:
                specs.append({**base(t), "test": name, "fullname": plan[t.name]["full"][name], "seed": seed,
                              "run_dir": str(reg / t.name / name / f"seed_{seed}"), "waves": use_waves(project, t, opts)})
    print(f"running {len(specs)} simulator run(s) on {opts.jobs} worker(s) -> {reg}", flush=True)
    with ProcessPoolExecutor(max_workers=opts.jobs) as pool:
        for r in pool.map(run_test, specs):
            by_target.setdefault(r["target"], []).append(r)

    summaries = []
    for s in selections:
        t = s.target
        out = reg / t.name
        out.mkdir(parents=True, exist_ok=True)
        p = plan[t.name]
        summaries.append(collect_target(project, t, by_target[t.name], out, p["tests"], p["seeds"], p["mode"],
                                        s.tests, master, opts))

    wall = time.monotonic() - t_start
    (reg / "regression.json").write_text(json.dumps({
        "id": reg.name, "created": time.strftime("%Y-%m-%d %H:%M:%S"), "master_seed": master, "argv": opts.argv,
        "project": project.name, "wall_s": wall, "targets": [t.name for t in targets],
    }, indent=2))

    bad = [s["target"] for s in summaries if any(r["status"] in ("fail", "error") for r in s["runs"])]
    print(f"\n{'target':<14} {'status':<6} {'tests passed':>13} {'seeds':>6}")
    for s in summaries:
        rr = s["runs"]
        print(f"{s['target']:<14} {'FAIL' if s['target'] in bad else 'pass':<6} "
              f"{f'{sum(r['status'] == 'pass' for r in rr)}/{len(rr)}':>13} {max(len(v) for v in s['seeds'].values()):>6}")
    site = build_site(reg.parent, only=reg)
    print(f"\n{len(specs)} runs in {wall:.1f}s\ndashboard: {reg / 'index.html'}  (all regressions: {site})")
    return 1 if bad else 0
