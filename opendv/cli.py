"""The `opendv` command line: run, regress, targets, report, help.

Parsing and dispatch only; the work is in run.py and regress.py (the two flows), config.py
(opendv.yaml, target selection) and report/ (the dashboard).
"""

import argparse
import shlex
import sys
from pathlib import Path

from . import config


def _seeds_option(ap: argparse.ArgumentParser):
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--seeds", type=int, metavar="N", help="N random seeds per test (default: config, else 8)")
    g.add_argument("--seed-list", type=int, nargs="+", metavar="SEED", help="run exactly these seeds")


def cmd_run(args) -> int:
    from .run import TAG, run

    if not TAG.match(args.tag):
        raise config.ConfigError(f"--tag '{args.tag}': use letters, digits, '.', '_' or '-'")
    if args.seed is not None and args.seed < 1:
        raise config.ConfigError("--seed must be at least 1")
    project, current = config.find(Path.cwd())
    sel = config.resolve(project, current, [args.test])
    if len(sel) != 1 or len(sel[0].tests) != 1 or any(c in sel[0].tests[0] for c in "*?["):
        raise config.ConfigError("`opendv run` runs one test: name it TARGET:TEST (or TEST from inside a target "
                                 "directory). For targets, several tests or several seeds use `opendv regress`.")
    return run(project, sel[0].target, sel[0].tests[0], seed=args.seed, tag=args.tag, waves=args.waves)


def cmd_regress(args) -> int:
    from .regress import Options, regress

    project, current = config.find(Path.cwd())
    sel = config.resolve(project, current, args.selectors, args.all)
    if args.seed_list:
        seeds = args.seed_list
    elif args.seeds is not None:
        if args.seeds < 1:
            raise config.ConfigError("--seeds must be at least 1")
        seeds = args.seeds
    else:
        seeds = None
    opts = Options(
        seeds=seeds, master_seed=args.master_seed, code_cov=args.code_cov, waves=args.waves,
        cov_from_failed=args.cov_from_failed, skip_build=args.skip_build, out=args.out,
        argv="opendv " + shlex.join(sys.argv[1:]))
    if args.jobs:
        opts.jobs = args.jobs
    return regress(project, sel, opts)


def cmd_targets(args) -> int:
    project, current = config.find(Path.cwd())
    print(f"project {project.name}  ({project.root})")
    for t in project.targets.values():
        seeds = project.seeds_for(t)
        print(f"  {'*' if current and t.name == current.name else ' '} {t.name:<12} {t.toplevel:<20} "
              f"tests: {', '.join(t.modules):<28} seeds: {seeds}")
    return 0


def cmd_report(args) -> int:
    from .report import build_site

    project, _ = config.find(Path.cwd())
    print(build_site(project.results_dir, rebuild_all=args.rebuild_all))
    return 0


INTRO = """opendv: plug-and-play design verification. Verilator + cocotb, a parallel multi-seed
regression runner, merged functional and code coverage, and a static HTML dashboard.

Run it from anywhere inside a project: a directory tree of opendv.yaml files, one per
target. A bare TEST name means a test of the target you are standing in."""

COMMANDS = {
    "run": "build and run ONE test with one seed, for debugging (waves on)",
    "regress": "a regression: many tests and seeds, merged coverage, the dashboard",
    "targets": "list the project's targets, their toplevels and tests",
    "report": "regenerate the dashboard",
    "help": "show help for a command",
}


def _table(title: str, rows) -> str:
    """Two columns of (left, right) under a title, the right column aligned after the widest left."""
    width = max(len(left) for left, _ in rows)
    return title + ":\n" + "\n".join(f"  {left.ljust(width)}  {right}" for left, right in rows)


MAIN_EXAMPLES = _table("examples", [
    ("opendv targets", "list the project's targets"),
    ("opendv run fabric:test_irq_routing", "debug one test: random seed, waves on"),
    ("opendv regress --all --seeds 4", "the whole project, 4 random seeds per test"),
    ("opendv report", "rebuild the dashboard (regress/index.html)"),
    ("opendv help run", "help for one command (same as: opendv run --help)"),
])

RUN_HELP = """Build the target and run ONE test with ONE seed, with waves on. Everything for the run is
in <project>/sim/<target>/<test>/build_<tag>/: the compiled model, sim.log, results.xml,
dump.fst and coverage.yml. Nothing is added to the regression history or the dashboard."""

RUN_EXAMPLES = _table("examples", [
    ("opendv run fabric:test_irq_routing", "random seed, printed at the end"),
    ("opendv run test_irq_routing", "the same, from inside the fabric directory"),
    ("opendv run fabric:test_irq_routing --seed 17", "replay a seed (a failure report prints the command)"),
    ("opendv run fabric:test_irq_routing --tag 2", "keep build_1, build and run afresh in build_2"),
])

REGRESS_HELP = """Build the selected targets, run every selected test once per seed in parallel, merge the
coverage and write the dashboard (<project>/regress/<timestamp>/). Name targets, TARGET:TEST
(globs ok) or --all; inside a target directory with no selector, runs that target."""

REGRESS_EXAMPLES = _table("examples", [
    ("opendv regress --all --seeds 4", "the whole project, 4 random seeds per test"),
    ("opendv regress router regfile", "two targets, the seeds from the config"),
    ("opendv regress 'fabric:test_irq*' --seeds 20", "some tests, 20 seeds each"),
    ("opendv regress --all --master-seed 123", "replay a regression exactly"),
    ("opendv regress top --seed-list 17 99", "fixed seeds"),
    ("opendv regress --all --code-cov --waves", "with code coverage and waveforms"),
])


def build_parser() -> tuple[argparse.ArgumentParser, dict[str, argparse.ArgumentParser]]:
    """The parser, and the parser of each command (for `opendv help COMMAND`)."""
    raw = argparse.RawDescriptionHelpFormatter
    # The command list is written out from COMMANDS (argparse would print an extra metavar line above it),
    # so the sub-parser action itself is hidden from the generated help.
    ap = argparse.ArgumentParser(prog="opendv", usage="%(prog)s [-h] COMMAND ...", description=INTRO + "\n\n" + _table("commands", list(COMMANDS.items())),
                                 epilog=MAIN_EXAMPLES, formatter_class=raw)
    sub = ap.add_subparsers(dest="cmd", metavar="COMMAND", help=argparse.SUPPRESS, prog="opendv")

    u = sub.add_parser("run", description=RUN_HELP, epilog=RUN_EXAMPLES, formatter_class=raw)
    u.add_argument("test", metavar="TEST", help="target:test, or a test of the current target")
    u.add_argument("--seed", type=int, help="the seed to run (default: a random one, printed)")
    u.add_argument("--tag", default="1", help="build_<tag> folder under sim/<target>/<test>/ (default 1: rerunning "
                   "overwrites it; another tag keeps the old one and compiles afresh)")
    u.add_argument("--waves", action=argparse.BooleanOptionalAction, default=True, help="write an FST waveform (default: on)")
    u.set_defaults(fn=cmd_run)

    r = sub.add_parser("regress", description=REGRESS_HELP, epilog=REGRESS_EXAMPLES, formatter_class=raw)
    r.add_argument("selectors", nargs="*", metavar="SELECTOR", help="target, target:test (glob ok), or a test of the current target")
    r.add_argument("--all", action="store_true", help="every target in the project")
    _seeds_option(r)
    r.add_argument("--master-seed", type=int, help="replay a regression: the seeds are derived from this")
    r.add_argument("--jobs", type=int, help="parallel simulator runs (default: CPU count)")
    r.add_argument("--code-cov", action="store_true", help="collect Verilator line+toggle coverage")
    r.add_argument("--waves", action=argparse.BooleanOptionalAction, default=None,
                   help="write FST waveforms (default: the `waves` setting in opendv.yaml, which is off)")
    r.add_argument("--cov-from-failed", action="store_true", help="also merge coverage from runs with failing tests")
    r.add_argument("--skip-build", action="store_true", help="reuse the previous build")
    r.add_argument("--out", type=Path, help="write this regression here instead of <results_dir>/<timestamp>")
    r.set_defaults(fn=cmd_regress)

    t = sub.add_parser("targets", description="List the project's targets, their toplevels, tests and seeds. A * marks "
                                              "the target you are standing in.")
    t.set_defaults(fn=cmd_targets)

    p = sub.add_parser("report", description="Regenerate the dashboard over all regressions under results_dir. Only "
                                             "missing pages are rebuilt unless --rebuild-all.")
    p.add_argument("--rebuild-all", action="store_true", help="every regression, not only missing pages")
    p.set_defaults(fn=cmd_report)

    h = sub.add_parser("help", description="Show help for a command (same as COMMAND --help).")
    h.add_argument("topic", nargs="?", choices=list(COMMANDS), metavar="COMMAND", help=", ".join(COMMANDS))

    return ap, dict(sub.choices)


def main(argv=None) -> int:
    ap, commands = build_parser()
    args = ap.parse_args(argv)
    if args.cmd in (None, "help"):
        (commands[args.topic] if getattr(args, "topic", None) else ap).print_help()
        return 0
    try:
        return args.fn(args)
    except config.ConfigError as e:
        print(f"opendv: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
