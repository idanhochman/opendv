"""Reading what one simulator run left behind: results.xml and sim.log."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_results(run_dir: Path) -> list[dict]:
    """The tests recorded in one run dir's results.xml (one test per simulation)."""
    xml = run_dir / "results.xml"
    if not xml.exists():
        return []
    tests, t = [], 0.0
    for tc in ET.parse(xml).getroot().iter("testcase"):
        start, dur = _sim_times(tc, t)
        failure = tc.find("failure")
        error = tc.find("error")
        bad = failure if failure is not None else error
        status = "fail" if bad is not None else ("skip" if tc.find("skipped") is not None else "pass")
        msg = ""
        if bad is not None:
            msg = (bad.get("message") or bad.text or "").strip().splitlines()
            msg = msg[-1] if msg else ""
        tests.append({
            "name": tc.get("name"), "status": status, "sim_ns": dur,
            "start_ns": start, "end_ns": start + dur, "message": msg,
        })
        t = start + dur
    return tests


def _sim_times(tc, fallback_start: float) -> tuple[float, float]:
    """(start_ns, duration_ns) of one testcase. cocotb 2.x records them as
    <property name="sim_time_start|stop|duration"> in the sim_time_unit; 1.x
    wrote a sim_time_ns attribute (start is then the sum of earlier tests)."""
    props = {p.get("name"): p.get("value") for p in tc.iter("property")}
    if "sim_time_duration" in props:
        scale = _UNIT_NS.get(props.get("sim_time_unit", "ns"), 1.0)
        return float(props.get("sim_time_start", 0)) * scale, float(props["sim_time_duration"]) * scale
    return fallback_start, float(tc.get("sim_time_ns", 0))


_FAILED = re.compile(r"^\s*([\d.]+)(ps|ns|us|ms)?\s+(?:INFO|WARNING|ERROR)\s+cocotb\.regression\s+(\S+) failed")


_ERRLINE = re.compile(r"^\s+(\w*(?:Error|Exception|Failure)\b.*)$")


_UNIT_NS = {"ps": 1e-3, "ns": 1.0, "us": 1e3, "ms": 1e6, None: 1.0}


def parse_log_failures(run_dir: Path) -> dict[str, dict]:
    """From sim.log: for each failed test, the exact sim time cocotb logged
    the failure (when the scoreboard/assert fired) and the last exception
    line of its traceback -- results.xml only says 'Test failed'."""
    log = run_dir / "sim.log"
    if not log.exists():
        return {}
    out: dict[str, dict] = {}
    cur = None
    for line in log.read_text(errors="replace").splitlines():
        m = _FAILED.match(line)
        if m:
            cur = m.group(3).split(".")[-1]
            out[cur] = {"at_ns": float(m.group(1)) * _UNIT_NS[m.group(2)], "message": ""}
            continue
        if cur and "cocotb.regression" in line:
            cur = None
        elif cur:
            e = _ERRLINE.match(line.strip() and line)
            if e:
                out[cur]["message"] = e.group(1).strip()
    return out


def fill_result(r: dict) -> None:
    """Read one finished run's results.xml / sim.log into the run record."""
    rd = Path(r["run_dir"])
    found = parse_results(rd)
    t = next((x for x in found if x["name"] == r["test"]), found[0] if found else None)
    if t is None:
        r.update(status="error", sim_ns=0.0, message=(r.get("runner_error") or "no results.xml").splitlines()[0])
        return
    r.update(status=t["status"], sim_ns=t["sim_ns"], message=t["message"])
    fail = parse_log_failures(rd).get(r["test"])
    if t["status"] == "fail" and fail:
        r["message"] = fail["message"] or r["message"]
        r["detected_ns"] = fail["at_ns"]
