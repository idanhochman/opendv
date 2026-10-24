import pytest

from opendv import cli, config, regress, run


def make_project(root):
    (root / "opendv.yaml").write_text("version: 1\nproject: demo\ntargets: [blk]\n")
    d = root / "blk"
    (d / "rtl").mkdir(parents=True)
    (d / "dv" / "tests").mkdir(parents=True)
    (d / "rtl" / "blk.f").write_text("blk.sv\n")
    (d / "opendv.yaml").write_text("version: 1\ntoplevel: blk_top\nrtl: {filelist: rtl/blk.f}\ndv: {tests: [test_blk]}\n")
    return root


def test_sim_dir_is_next_to_results_dir(tmp_path):
    p = config.load_project(make_project(tmp_path))
    assert p.sim_dir == tmp_path.resolve() / "sim"
    assert p.sim_dir.parent == p.results_dir.parent


def test_sim_run_dir_layout(tmp_path):
    p = config.load_project(make_project(tmp_path))
    t = p.targets["blk"]
    assert run.sim_run_dir(p, t, "test_x", "1") == p.sim_dir / "blk" / "test_x" / "build_1"
    assert run.sim_run_dir(p, t, "test_x", "fresh") == p.sim_dir / "blk" / "test_x" / "build_fresh"


def test_replay_command_for_one_seed():
    assert run.repro_cmd("blk", "test_x", 7) == "opendv run blk:test_x --seed 7"
    assert run.repro_cmd("blk", "test_x", 7, tag="b", waves=False) == "opendv run blk:test_x --seed 7 --tag b --no-waves"


@pytest.mark.parametrize("argv, msg", [
    (["run", "blk"], "runs one test"),                  # a target, not a test
    (["run", "blk:test_*"], "runs one test"),           # a pattern
    (["run", "blk:test_x", "--tag", "a/b"], "--tag"),   # a tag that is not a folder-name
    (["run", "blk:test_x", "--seed", "0"], "--seed"),
    (["run", "nope:test_x"], "unknown target"),
])
def test_run_rejects_what_is_not_one_test(tmp_path, monkeypatch, capsys, argv, msg):
    monkeypatch.chdir(make_project(tmp_path))
    assert cli.main(argv) == 2
    assert msg in capsys.readouterr().err


def test_bare_test_name_resolves_from_inside_a_target(tmp_path, monkeypatch):
    monkeypatch.chdir(make_project(tmp_path) / "blk")
    seen = {}
    monkeypatch.setattr(run, "run", lambda project, target, test, **kw: seen.update(target=target.name, test=test, **kw) or 0)
    assert cli.main(["run", "test_x", "--seed", "5", "--tag", "b", "--no-waves"]) == 0
    assert seen == {"target": "blk", "test": "test_x", "seed": 5, "tag": "b", "waves": False}


def test_run_defaults_are_tag_1_and_waves_on(tmp_path, monkeypatch):
    monkeypatch.chdir(make_project(tmp_path))
    seen = {}
    monkeypatch.setattr(run, "run", lambda project, target, test, **kw: seen.update(kw) or 0)
    cli.main(["run", "blk:test_x"])
    assert seen == {"seed": None, "tag": "1", "waves": True}


def test_regress_is_the_old_run(tmp_path, monkeypatch):
    monkeypatch.chdir(make_project(tmp_path))
    seen = {}
    monkeypatch.setattr(regress, "regress", lambda project, sel, opts: seen.update(targets=[s.target.name for s in sel], seeds=opts.seeds) or 0)
    assert cli.main(["regress", "--all", "--seeds", "3"]) == 0
    assert seen == {"targets": ["blk"], "seeds": 3}


def test_no_command_prints_the_help(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "regress" in out and "run" in out and "examples:" in out


def test_help_command_is_the_same_as_dash_dash_help(capsys):
    assert cli.main(["help", "run"]) == 0
    via_help = capsys.readouterr().out
    with pytest.raises(SystemExit) as e:
        cli.main(["run", "--help"])
    assert e.value.code == 0
    assert capsys.readouterr().out == via_help
    assert "build_<tag>" in via_help


def test_help_for_every_command(capsys):
    for cmd in ("run", "regress", "targets", "report", "help"):
        assert cli.main(["help", cmd]) == 0
        assert capsys.readouterr().out.startswith(f"usage: opendv {cmd}")
    with pytest.raises(SystemExit):
        cli.main(["help", "nope"])


def test_the_command_list_in_the_help_matches_the_commands():
    _, commands = cli.build_parser()
    assert list(commands) == list(cli.COMMANDS)


def test_main_help_lists_each_command_once(capsys):
    cli.main([])
    out = capsys.readouterr().out
    for cmd in cli.COMMANDS:
        assert out.count(f"\n  {cmd} ") == 1
    assert "\n  COMMAND\n" not in out  # argparse's own metavar line is hidden
    assert out.startswith("usage: opendv [-h] COMMAND ...")
