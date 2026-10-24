"""`opendv run`: one test, one seed, for debugging. Everything lands in one folder, with no regression history."""

import re
import shutil
import sys
from pathlib import Path

from . import config
from .results import fill_result, parse_results
from .seeds import new_master_seed
from .simulator import build_target, list_target, simulate


TAG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def sim_run_dir(project: config.Project, target: config.Target, test: str, tag: str) -> Path:
    return project.sim_dir / target.name / test / f"build_{tag}"


def repro_cmd(target: str, test: str, seed: int, tag: str = "1", waves: bool = True) -> str:
    """The `opendv run` command that repeats one test with one seed."""
    return f"opendv run {target}:{test} --seed {seed}" + ("" if tag == "1" else f" --tag {tag}") + ("" if waves else " --no-waves")


def run(project: config.Project, target: config.Target, test: str, *, seed: int | None = None,
            tag: str = "1", waves: bool = True) -> int:
    """`opendv run`: build the target and run one test with one seed, all inside
    <project>/sim/<target>/<test>/build_<tag>/. The same tag reuses (and overwrites) that folder; a new
    tag compiles and runs in a fresh one. Returns 0 on pass, 1 on a failing test, 2 on any other problem."""
    seed = seed or new_master_seed()
    d = sim_run_dir(project, target, test, tag)
    d.mkdir(parents=True, exist_ok=True)
    for stale in ("results.xml", "sim.log", "dump.fst", "coverage.yml"):
        (d / stale).unlink(missing_ok=True)
    print(f"{target.name}:{test}   seed {seed}   tag {tag}   waves {'on' if waves else 'off'}\n  dir: {d}", flush=True)

    _, secs, err = build_target(project, target, d, code_cov=False, waves=waves)
    if err:
        print(f"\nBUILD ERROR in {target.name}:\n{err}", file=sys.stderr)
        return 2
    print(f"  built in {secs:.1f}s", flush=True)

    spec = {"target": target.name, "toplevel": target.toplevel, "modules": target.modules,
            "sys_path": [str(p) for p in target.sys_path], "build_dir": str(d)}
    err = simulate(spec, d, test_filter=rf"^\w+\.{re.escape(test)}$", seed=seed,
                    env={"OPENDV_SEED": str(seed), "OPENDV_RUN_DIR": str(d)}, waves=waves)
    found = parse_results(d)
    if len(found) != 1:
        if found:
            print(f"\n{target.name}: test name '{test}' is defined in more than one module", file=sys.stderr)
        else:  # no such test, or the simulator died before reporting; list what exists to tell which
            listed = list_target({**spec, "list_dir": str(d / "_list")})
            shutil.rmtree(d / "_list", ignore_errors=True)
            names = [f.rsplit(".", 1)[1] for f in listed["names"]]
            if names and test not in names:
                print(f"\nno test '{test}' in {target.name} (tests: {', '.join(names)})", file=sys.stderr)
                shutil.rmtree(d, ignore_errors=True)  # nothing worth keeping: a mistyped name
                try:
                    d.parent.rmdir()
                except OSError:
                    pass
            else:
                print(f"\nthe simulator produced no result for {test}:\n{err}\nlog: {d / 'sim.log'}", file=sys.stderr)
        return 2

    r = {"run_dir": str(d), "test": test, "runner_error": err}
    fill_result(r)
    status = r["status"].upper()
    print(f"\n{status}  {test}   seed {seed}   sim time {r['sim_ns']:.0f} ns")
    if r["status"] != "pass":
        where = f"  (detected @ {r['detected_ns']:.0f} ns)" if "detected_ns" in r else ""
        print(f"  {r['message']}{where}")
    print(f"  log:   {d / 'sim.log'}")
    if (d / "dump.fst").exists():
        print(f"  waves: {d / 'dump.fst'}")
    print(f"  rerun: {repro_cmd(target.name, test, seed, tag, waves)}")
    return {"pass": 0, "fail": 1}.get(r["status"], 2)
