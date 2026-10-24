"""opendv.yaml loading, validation, discovery and target selection.

Two file kinds, both named opendv.yaml:

  project   lists the targets and holds defaults (has a `targets:` key)
  target    one verification target: a toplevel, its file list and its tests
            (has a `toplevel:` key)

A target keeps its verification code under dv/: dv/tests holds the cocotb test modules
(named in `dv.tests`, globs like `test_*` allowed) and dv/env the environment they import; both go on the simulator's
Python path, followed by `dv.pythonpath` (reuse from other targets).

All paths inside a file are relative to that file. A directory with only a
target file works as a one-target project.
"""

import difflib
from dataclasses import dataclass, field
from pathlib import Path

import yaml

FILENAME = "opendv.yaml"
VERSION = 1
BUILTIN_SEEDS = 8

PROJECT_KEYS = {"version", "project", "targets", "defaults", "results_dir"}
DEFAULT_KEYS = {"seeds", "code_cov", "waves", "sim"}
SIM_KEYS = {"tool", "build_args"}
TARGET_KEYS = {"version", "name", "toplevel", "rtl", "dv", "coverage", "seeds", "waves", "sim"}
RTL_KEYS = {"filelist", "parameters"}
DV_KEYS = {"dir", "tests", "pythonpath"}
COVERAGE_KEYS = {"functional"}


class ConfigError(Exception):
    """A problem with a config file or with how the command line names targets."""


@dataclass
class Defaults:
    seeds: int | list[int] = BUILTIN_SEEDS
    code_cov: bool = False
    waves: bool = False
    build_args: list[str] = field(default_factory=list)


@dataclass
class Target:
    name: str
    dir: Path
    toplevel: str
    filelist: Path
    parameters: dict
    modules: list[str]
    dv_dir: Path
    pythonpath: list[Path]
    functional_cov: str | None
    seeds: int | list[int] | None
    waves: bool | None  # None = the project default
    build_args: list[str]

    @property
    def sys_path(self) -> list[Path]:
        """What the simulator's Python needs on its path to import the tests."""
        env = self.dv_dir / "env"
        return [self.dv_dir / "tests", *([env] if env.is_dir() else []), *self.pythonpath]


@dataclass
class Project:
    name: str
    root: Path
    targets: dict[str, Target]  # in display order
    defaults: Defaults
    results_dir: Path

    @property
    def sim_dir(self) -> Path:
        """Where `opendv run` (single test, for debugging) puts its builds and results, next to results_dir."""
        return self.root / "sim"

    def seeds_for(self, t: Target) -> int | list[int]:
        return t.seeds if t.seeds is not None else self.defaults.seeds

    def waves_for(self, t: Target) -> bool:
        return t.waves if t.waves is not None else self.defaults.waves

    def build_args_for(self, t: Target) -> list[str]:
        return [*self.defaults.build_args, *t.build_args]


# -- loading -----------------------------------------------------------------

def _read(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise ConfigError(f"{path}: not valid YAML: {e}") from None
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected a mapping at the top level")
    return data


def _keys(d, allowed: set[str], where: str):
    if not isinstance(d, dict):
        raise ConfigError(f"{where}: expected a mapping")
    for k in d:
        if k not in allowed:
            hint = difflib.get_close_matches(str(k), allowed, n=1)
            raise ConfigError(f"{where}: unknown key '{k}'" + (f" (did you mean '{hint[0]}'?)" if hint else "")
                              + f"; allowed: {', '.join(sorted(allowed))}")


def _version(d: dict, path: Path):
    v = d.get("version", VERSION)
    if v != VERSION:
        raise ConfigError(f"{path}: version {v} is not supported (this opendv reads version {VERSION})")


def _seeds(v, where: str):
    if isinstance(v, bool) or not (isinstance(v, int) or (isinstance(v, list) and v
                                                         and all(isinstance(s, int) and not isinstance(s, bool) for s in v))):
        raise ConfigError(f"{where}: seeds must be a count (e.g. 8) or a non-empty list of integers")
    if isinstance(v, int) and v < 1:
        raise ConfigError(f"{where}: seed count must be at least 1")
    return v


def _bool(v, where: str) -> bool:
    if not isinstance(v, bool):
        raise ConfigError(f"{where}: expected true or false")
    return v


def _str_list(v, where: str) -> list[str]:
    if not isinstance(v, list) or not all(isinstance(s, str) for s in v):
        raise ConfigError(f"{where}: expected a list of strings")
    return v


def _modules(entries: list[str], tests_dir: Path, path: Path) -> list[str]:
    """dv.tests entries are module names; one with glob characters (`test_*`) expands to
    the matching files of dv/tests, sorted by name."""
    out: list[str] = []
    for e in entries:
        if not any(c in e for c in "*?["):
            names = [e]
        else:
            names = sorted(f.stem for f in tests_dir.glob(e + ".py"))
            if not names:
                raise ConfigError(f"{path}: dv.tests pattern '{e}' matches no file in {tests_dir}")
        out += [n for n in names if n not in out]
    return out


def load_target(tdir: Path) -> Target:
    path = tdir / FILENAME
    d = _read(path)
    _keys(d, TARGET_KEYS, str(path))
    _version(d, path)
    if "toplevel" not in d:
        raise ConfigError(f"{path}: missing 'toplevel'")
    rtl = d.get("rtl") or {}
    _keys(rtl, RTL_KEYS, f"{path}: rtl")
    if "filelist" not in rtl:
        raise ConfigError(f"{path}: missing 'rtl.filelist'")
    filelist = (tdir / rtl["filelist"]).resolve()
    if not filelist.is_file():
        raise ConfigError(f"{path}: rtl.filelist '{rtl['filelist']}' not found ({filelist})")
    dv = d.get("dv") or {}
    _keys(dv, DV_KEYS, f"{path}: dv")
    if not dv.get("tests"):
        raise ConfigError(f"{path}: missing 'dv.tests' (the cocotb test modules)")
    cov = d.get("coverage") or {}
    _keys(cov, COVERAGE_KEYS, f"{path}: coverage")
    sim = d.get("sim") or {}
    _keys(sim, SIM_KEYS, f"{path}: sim")
    dv_dir = (tdir / dv.get("dir", "dv")).resolve()
    if not (dv_dir / "tests").is_dir():
        raise ConfigError(f"{path}: no tests directory at {dv_dir / 'tests'} (dv.dir is '{dv.get('dir', 'dv')}')")
    pypath = [(tdir / p).resolve() for p in _str_list(dv.get("pythonpath", []), f"{path}: dv.pythonpath")]
    for p in pypath:
        if not p.is_dir():
            raise ConfigError(f"{path}: dv.pythonpath entry {p} does not exist")
    return Target(
        name=str(d.get("name", tdir.resolve().name)),
        dir=tdir.resolve(),
        toplevel=str(d["toplevel"]),
        filelist=filelist,
        parameters=dict(rtl.get("parameters") or {}),
        modules=_modules(_str_list(dv["tests"], f"{path}: dv.tests"), dv_dir / "tests", path),
        dv_dir=dv_dir,
        pythonpath=pypath,
        functional_cov=cov.get("functional"),
        seeds=_seeds(d["seeds"], f"{path}: seeds") if "seeds" in d else None,
        waves=_bool(d["waves"], f"{path}: waves") if "waves" in d else None,
        build_args=_str_list(sim.get("build_args", []), f"{path}: sim.build_args"),
    )


def _defaults(d: dict, path: Path) -> Defaults:
    _keys(d, DEFAULT_KEYS, f"{path}: defaults")
    sim = d.get("sim") or {}
    _keys(sim, SIM_KEYS, f"{path}: defaults.sim")
    if sim.get("tool", "verilator") != "verilator":
        raise ConfigError(f"{path}: defaults.sim.tool: only 'verilator' is supported")
    return Defaults(
        seeds=_seeds(d["seeds"], f"{path}: defaults.seeds") if "seeds" in d else BUILTIN_SEEDS,
        code_cov=bool(d.get("code_cov", False)),
        waves=_bool(d.get("waves", False), f"{path}: defaults.waves"),
        build_args=_str_list(sim.get("build_args", []), f"{path}: defaults.sim.build_args"),
    )


def load_project(root: Path) -> Project:
    path = root / FILENAME
    d = _read(path)
    _keys(d, PROJECT_KEYS, str(path))
    _version(d, path)
    entries = d.get("targets")
    if not isinstance(entries, list) or not entries:
        raise ConfigError(f"{path}: 'targets' must be a non-empty list of target directories")
    targets: dict[str, Target] = {}
    for e in entries:
        tdir = root / str(e)
        if not (tdir / FILENAME).is_file():
            raise ConfigError(f"{path}: target '{e}' has no {FILENAME} ({tdir})")
        t = load_target(tdir)
        if t.name in targets:
            raise ConfigError(f"{path}: two targets are named '{t.name}' ({targets[t.name].dir} and {t.dir})")
        targets[t.name] = t
    return Project(
        name=str(d.get("project", root.resolve().name)),
        root=root.resolve(),
        targets=targets,
        defaults=_defaults(d.get("defaults") or {}, path),
        results_dir=(root / d.get("results_dir", "regress")).resolve(),
    )


# -- discovery ---------------------------------------------------------------

def _kind(path: Path) -> str:
    d = _read(path)
    return "project" if "targets" in d else ("target" if "toplevel" in d else "unknown")


def find(cwd: Path) -> tuple[Project, Target | None]:
    """The project that contains `cwd` and the target `cwd` is inside (if any).

    A directory holding only a target file is its own one-target project."""
    cwd = cwd.resolve()
    target_dir = project_dir = None
    for d in [cwd, *cwd.parents]:
        f = d / FILENAME
        if not f.is_file():
            continue
        kind = _kind(f)
        if kind == "target" and target_dir is None:
            target_dir = d
        elif kind == "project":
            project_dir = d
            break
    if project_dir is not None:
        project = load_project(project_dir)
        cur = next((t for t in project.targets.values() if target_dir and t.dir == target_dir), None)
        return project, cur
    if target_dir is not None:
        t = load_target(target_dir)
        return Project(t.name, target_dir, {t.name: t}, Defaults(), (target_dir / "regress").resolve()), t
    raise ConfigError(f"no {FILENAME} found in {cwd} or any parent directory")


# -- selection ---------------------------------------------------------------

@dataclass
class Selection:
    target: Target
    tests: list[str]  # empty = every test of the target


def resolve(project: Project, current: Target | None, args: list[str], all_: bool = False) -> list[Selection]:
    """Turn command-line words into (target, tests):

      target:test   exactly that test       target   the whole target
      test          a test of the current target (when run from inside one)
    With no words: the current target, or an error asking for targets / --all."""
    names = ", ".join(project.targets)
    if all_:
        if args:
            raise ConfigError("--all cannot be combined with target or test names")
        return [Selection(t, []) for t in project.targets.values()]
    if not args:
        if current:
            return [Selection(current, [])]
        raise ConfigError(f"say what to run: a target, target:test, or --all. Targets: {names}")
    whole: set[str] = set()
    tests: dict[str, list[str]] = {}
    for a in args:
        if ":" in a:
            tname, test = a.split(":", 1)
            if tname not in project.targets:
                raise ConfigError(_unknown_target(tname, project))
            if test:
                tests.setdefault(tname, []).append(test)
            else:
                whole.add(tname)
        elif a in project.targets:
            whole.add(a)
        elif current:
            tests.setdefault(current.name, []).append(a)
        else:
            raise ConfigError(_unknown_target(a, project) + " (run from inside a target directory to name a bare test)")
    return [Selection(t, [] if t.name in whole else tests[t.name])
            for t in project.targets.values() if t.name in whole or t.name in tests]


def _unknown_target(name: str, project: Project) -> str:
    hint = difflib.get_close_matches(name, project.targets, n=1)
    return (f"unknown target '{name}'" + (f" (did you mean '{hint[0]}'?)" if hint else "")
            + f". Targets: {', '.join(project.targets)}")
