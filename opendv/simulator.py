"""Verilator through the cocotb runner: build a target, list its tests, run one simulator process."""

import re
import sys
import time
import traceback
from pathlib import Path

from . import config


def build_target(project: config.Project, target: config.Target, bdir: Path, *, code_cov: bool,
                 waves: bool) -> tuple[str, float, str | None]:
    """Compile the target into `bdir`. Returns (target name, seconds, error text or None)."""
    from cocotb_tools.runner import get_runner

    t0 = time.monotonic()
    bdir.mkdir(parents=True, exist_ok=True)
    args = ["-F", str(target.filelist), *(["--trace-fst"] if waves else []), *project.build_args_for(target)]
    if code_cov:
        args += ["--coverage-line", "--coverage-toggle"]
    try:
        get_runner("verilator").build(
            sources=[], hdl_toplevel=target.toplevel, parameters=target.parameters,
            build_dir=bdir, always=True, waves=waves, build_args=args, log_file=bdir / "build.log")
    except Exception as e:  # the log has the compiler output
        tail = ""
        log = bdir / "build.log"
        if log.exists():
            tail = "\n".join(log.read_text(errors="replace").splitlines()[-25:])
        return target.name, time.monotonic() - t0, f"{type(e).__name__}: {e}\n{tail}"
    return target.name, time.monotonic() - t0, None


def simulate(spec: dict, run_dir: Path, *, test_filter: str | None, seed: int | None, env: dict, waves: bool) -> str | None:
    """One simulator process; returns an error text, or None. cocotb raises
    RuntimeError when a test failed, which is a result, not an opendv error."""
    from cocotb_tools.runner import get_runner

    run_dir.mkdir(parents=True, exist_ok=True)
    for p in reversed(spec["sys_path"]):  # cocotb's runner forwards sys.path
        sys.path.insert(0, p)
    try:
        get_runner("verilator").test(
            hdl_toplevel=spec["toplevel"],
            hdl_toplevel_lang="verilog",  # runner.test() otherwise needs build() state from the same process
            test_module=spec["modules"],
            test_filter=test_filter,
            seed=seed,
            build_dir=spec["build_dir"],
            test_dir=run_dir,
            results_xml=str(run_dir / "results.xml"),
            log_file=run_dir / "sim.log",
            extra_env=env,
            waves=waves,
        )
        return None
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        if not (run_dir / "results.xml").exists():
            err += "\n" + traceback.format_exc()
        return err


_LISTED = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+$")


def list_target(spec: dict) -> dict:
    """Worker: the target's tests ('module.test', in cocotb's run order). cocotb
    discovers them inside a simulator, so this is one short simulator run that
    prints the names (COCOTB_LIST_TESTS) and exits."""
    d = Path(spec["list_dir"])
    err = simulate(spec, d, test_filter=None, seed=None, env={"COCOTB_LIST_TESTS": "1"}, waves=False)
    log = d / "sim.log"
    names = []
    if log.exists():
        on = False
        for line in log.read_text(errors="replace").splitlines():
            if "Listing tests that were discovered" in line:
                on = True
            elif "All tests listed" in line:
                break
            elif on and _LISTED.match(line.strip()):
                names.append(line.strip())
    if not names and not err:
        err = f"no tests listed by cocotb (see {log})"
    return {"target": spec["target"], "names": names, "error": err if not names else None}


def test_filter(tests: list[str]) -> str | None:
    """cocotb test_filter regex for `target:test` selectors (names or globs).
    cocotb matches it against 'module.test', so anchor on the final name."""
    if not tests:
        return None
    pieces = [re.escape(t).replace(r"\*", ".*").replace(r"\?", ".") for t in tests]
    return r"\.(" + "|".join(pieces) + ")$"
