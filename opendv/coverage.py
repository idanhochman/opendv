"""Merging coverage across the runs of a target: cocotb-coverage YAML (functional) and Verilator (code)."""

import subprocess
import sys
from pathlib import Path

import yaml

from .codecov.report import write_report


BINS = "bins:_hits"


def load_cov(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) if path.exists() else {}


def leaf_bins(cov: dict) -> dict[tuple[str, str], int]:
    return {
        (name, str(b)): hits
        for name, item in cov.items() if BINS in item
        for b, hits in item[BINS].items()
    }


def merge_coverage(per_seed: dict[int, dict]) -> dict:
    """Sum bin hits across seeds. Returns per-leaf totals, plus for each
    bin the first seed (lowest seed number) that hit it."""
    total: dict[tuple[str, str], int] = {}
    first: dict[tuple[str, str], int] = {}
    for seed in sorted(per_seed):
        for key, hits in leaf_bins(per_seed[seed]).items():
            total[key] = total.get(key, 0) + hits
            if hits and key not in first:
                first[key] = seed
    return {"bins": total, "first_seed": first}


def group_summary(total: dict[tuple[str, str], int], at_least: int = 1) -> dict[str, tuple[int, int]]:
    """Per top-level group (router.txn, router.gap, ...): (hit, size)."""
    groups: dict[str, list[int]] = {}
    for (name, _), hits in total.items():
        group = ".".join(name.split(".")[:2])
        g = groups.setdefault(group, [0, 0])
        g[1] += 1
        g[0] += hits >= at_least
    return {k: (v[0], v[1]) for k, v in sorted(groups.items())}


def write_merged_yaml(path: Path, total: dict[tuple[str, str], int]):
    out: dict[str, dict[str, int]] = {}
    for (name, b), hits in sorted(total.items()):
        out.setdefault(name, {})[b] = hits
    path.write_text(yaml.safe_dump(out, sort_keys=False))


def merge_code_coverage(out: Path, run_dirs: list[Path], title: str = "Code coverage") -> dict | None:
    """Merge each run's coverage.dat with verilator_coverage; write merged.dat,
    lcov info and annotated sources under out/code_cov/. Returns None if no
    run produced a coverage.dat."""
    dats = [str(d / "coverage.dat") for d in run_dirs if (d / "coverage.dat").exists()]
    if not dats:
        print("\nCODE COVERAGE: no coverage.dat produced", file=sys.stderr)
        return None
    cc = out / "code_cov"
    cc.mkdir(exist_ok=True)
    merged, info, ann = cc / "merged.dat", cc / "merged.info", cc / "annotated"
    vc = ["verilator_coverage"]
    subprocess.run(vc + ["--write", str(merged), "--write-info", str(info), *dats], check=True,
                   capture_output=True)
    rep = subprocess.run(vc + ["--annotate", str(ann), "--annotate-all", "--annotate-min", "1", "--annotate-points", str(merged)],
                         check=True, capture_output=True, text=True)
    rpt = write_report(merged, cc / "report.html", title)
    return {"runs": len(dats), "merged": str(merged), "info": str(info), "annotated": str(ann),
            "report": (rep.stdout + rep.stderr).strip(), "html": rpt["html"],
            "by_type": rpt["by_type"], "holes": rpt["holes"]}
