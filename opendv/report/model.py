"""What the dashboard reads: one regression (regression.json) and one target of it (summary.json)."""

import json
from pathlib import Path

import yaml


class Run:
    """Everything the pages need, loaded from <dir>/summary.json."""

    def __init__(self, d: Path):
        self.dir = d
        self.reg = d.resolve().parent.name
        self.target = d.resolve().name
        self.id = f"{self.reg}/{self.target}"
        s = json.loads((d / "summary.json").read_text())
        self.s = s
        self.runs = s["runs"]  # one per (test, seed), in test order then seed order
        self.cov = s.get("coverage", {})
        self.cc = s.get("code_coverage") or {}
        p = d / "merged_coverage.yml"
        self.bins = yaml.safe_load(p.read_text()) if p.exists() else {}
        self.first = self.cov.get("first_seed", {})
        self.bad_runs = [x for x in self.runs if x["status"] in ("fail", "error")]
        self.names: list[str] = list(s["tests"])
        self.seeds_per_test = max(len(v) for v in s["seeds"].values())
        self.groups = self.cov.get("groups", {})
        self.f_hit = sum(g["hit"] for g in self.groups.values())
        self.f_size = sum(g["size"] for g in self.groups.values())
        by = self.cc.get("by_type") or {}
        self.c_hit = sum(v["hit"] for v in by.values())
        self.c_size = sum(v["size"] for v in by.values())
        self.code_requested = any((Path(r["run_dir"]) / "coverage.dat").exists() for r in self.runs)
        self.n_pass = sum(x["status"] == "pass" for x in self.runs)
        self.n_tests = len(self.runs)
        self.scope = f'tests: {s["testcase"]}' if s.get("testcase") else "full suite"
        self.func_configured = s.get("functional_configured", True)
        self.has_waves = any((Path(x["run_dir"]) / "dump.fst").exists() for x in self.runs)

    status = property(lambda self: "fail" if self.bad_runs else "pass")

    def test_status(self, name: str) -> str:
        sts = [x["status"] for x in self.test_results(name)]
        return "fail" if "fail" in sts or "error" in sts else ("pass" if sts else "none")

    def test_results(self, name: str) -> list[dict]:
        """The runs of one test, in seed order."""
        return [x for x in self.runs if x["test"] == name]


class Regression:
    """One `opendv regress`: regression.json plus a Run per target."""

    def __init__(self, d: Path):
        self.dir = d
        self.id = d.name
        self.meta = json.loads((d / "regression.json").read_text())
        self.runs = [Run(d / t) for t in self.meta["targets"] if (d / t / "summary.json").exists()]
        self.status = "fail" if any(r.status == "fail" for r in self.runs) else "pass"
        self.n_pass = sum(r.n_pass for r in self.runs)
        self.n_tests = sum(r.n_tests for r in self.runs)
        argv = self.meta.get("argv") or "opendv regress"
        self.replay = argv if "--master-seed" in argv else f'{argv} --master-seed {self.meta["master_seed"]}'

    def entry(self) -> dict:
        return {"id": self.id, "status": self.status, "argv": self.meta.get("argv", ""),
                "master_seed": self.meta["master_seed"], "wall_s": round(self.meta["wall_s"], 1),
                "n_pass": self.n_pass, "n_tests": self.n_tests,
                "targets": [{"name": r.target, "status": r.status} for r in self.runs]}
