import re

import pytest

from opendv import config, regress, seeds, simulator


def make_project(root, targets=("blk", "sub"), project_extra=""):
    (root / "opendv.yaml").write_text(
        "version: 1\nproject: demo\ntargets: [" + ", ".join(targets) + "]\n" + project_extra)
    for t in targets:
        d = root / t
        (d / "rtl").mkdir(parents=True)
        (d / "dv" / "tests").mkdir(parents=True)
        (d / "rtl" / f"{t}.f").write_text(f"{t}.sv\n")
        (d / "opendv.yaml").write_text(
            f"version: 1\ntoplevel: {t}_top\nrtl: {{filelist: rtl/{t}.f}}\ndv: {{tests: [test_{t}]}}\n")
    return root


def test_load_project(tmp_path):
    p = config.load_project(make_project(tmp_path))
    assert list(p.targets) == ["blk", "sub"]
    t = p.targets["blk"]
    assert t.toplevel == "blk_top" and t.modules == ["test_blk"]
    assert t.filelist == (tmp_path / "blk/rtl/blk.f").resolve()
    assert t.sys_path == [(tmp_path / "blk/dv/tests").resolve()]  # no env/ dir, none added
    assert p.seeds_for(t) == config.BUILTIN_SEEDS
    assert p.results_dir == (tmp_path / "regress").resolve()


def test_waves_default_off_and_target_overrides_project(tmp_path):
    make_project(tmp_path, project_extra="defaults: {waves: true}\n")
    (tmp_path / "sub/opendv.yaml").write_text(
        "toplevel: s\nrtl: {filelist: rtl/sub.f}\ndv: {tests: [t]}\nwaves: false\n")
    p = config.load_project(tmp_path)
    assert p.waves_for(p.targets["blk"]) is True    # project default
    assert p.waves_for(p.targets["sub"]) is False   # target override
    assert config.Defaults().waves is False         # off unless asked for


def test_waves_must_be_a_boolean(tmp_path):
    make_project(tmp_path, project_extra="defaults: {waves: yes please}\n")
    with pytest.raises(config.ConfigError, match="waves: expected true or false"):
        config.load_project(tmp_path)


def test_cli_waves_overrides_config(tmp_path):
    p = config.load_project(make_project(tmp_path, project_extra="defaults: {waves: true}\n"))
    t = p.targets["blk"]
    assert regress.use_waves(p, t, regress.Options()) is True
    assert regress.use_waves(p, t, regress.Options(waves=False)) is False


def test_precedence_target_seeds_over_defaults(tmp_path):
    make_project(tmp_path, project_extra="defaults: {seeds: 5}\n")
    (tmp_path / "sub/opendv.yaml").write_text(
        "toplevel: s\nrtl: {filelist: rtl/sub.f}\ndv: {tests: [t]}\nseeds: [3, 17]\n")
    p = config.load_project(tmp_path)
    assert p.seeds_for(p.targets["blk"]) == 5
    assert p.seeds_for(p.targets["sub"]) == [3, 17]


@pytest.mark.parametrize("bad, msg", [
    ("toplevl: x\n", "did you mean 'toplevel'"),
    ("toplevel: x\nrtl: {filelist: rtl/nope.f}\ndv: {tests: [t]}\n", "not found"),
    ("toplevel: x\nrtl: {filelist: rtl/blk.f}\ndv: {}\n", "dv.tests"),
    ("toplevel: x\nrtl: {filelist: rtl/blk.f}\ndv: {tests: [t]}\nseeds: 0\n", "at least 1"),
    ("version: 2\ntoplevel: x\n", "version 2"),
])
def test_target_validation(tmp_path, bad, msg):
    make_project(tmp_path)
    (tmp_path / "blk/opendv.yaml").write_text(bad)
    with pytest.raises(config.ConfigError, match=msg):
        config.load_project(tmp_path)


def test_duplicate_target_names(tmp_path):
    make_project(tmp_path)
    (tmp_path / "sub/opendv.yaml").write_text(
        "name: blk\ntoplevel: s\nrtl: {filelist: rtl/sub.f}\ndv: {tests: [t]}\n")
    with pytest.raises(config.ConfigError, match="two targets are named 'blk'"):
        config.load_project(tmp_path)


def test_find_from_inside_a_target(tmp_path):
    make_project(tmp_path)
    project, cur = config.find(tmp_path / "sub" / "test")
    assert project.root == tmp_path.resolve() and cur.name == "sub"
    project, cur = config.find(tmp_path)
    assert cur is None


def test_single_target_without_project_file(tmp_path):
    make_project(tmp_path)
    (tmp_path / "opendv.yaml").unlink()
    project, cur = config.find(tmp_path / "blk")
    assert list(project.targets) == ["blk"] and cur.name == "blk"
    assert project.root == (tmp_path / "blk").resolve()


def test_find_nothing(tmp_path):
    with pytest.raises(config.ConfigError, match="no opendv.yaml"):
        config.find(tmp_path)


def sel(args, project, cur=None, all_=False):
    return [(s.target.name, s.tests) for s in config.resolve(project, cur, args, all_)]


def test_resolve(tmp_path):
    p = config.load_project(make_project(tmp_path))
    sub = p.targets["sub"]
    assert sel([], p, sub) == [("sub", [])]                                # standing in a target
    assert sel(["blk", "sub:t1", "sub:t2"], p) == [("blk", []), ("sub", ["t1", "t2"])]
    assert sel(["t_x"], p, sub) == [("sub", ["t_x"])]                      # bare test of the current target
    assert sel(["blk", "blk:t1"], p) == [("blk", [])]                      # whole target wins
    assert sel([], p, all_=True) == [("blk", []), ("sub", [])]
    assert sel(["sub:"], p) == [("sub", [])]


def test_resolve_errors(tmp_path):
    p = config.load_project(make_project(tmp_path))
    with pytest.raises(config.ConfigError, match="say what to run"):
        config.resolve(p, None, [])
    with pytest.raises(config.ConfigError, match="did you mean 'blk'"):
        config.resolve(p, None, ["blq:t"])
    with pytest.raises(config.ConfigError, match="inside a target directory"):
        config.resolve(p, None, ["some_test"])
    with pytest.raises(config.ConfigError, match="--all cannot be combined"):
        config.resolve(p, None, ["blk"], all_=True)


def test_draw_seeds_replayable_and_distinct():
    a = seeds.draw_seeds(42, "fabric", 8)
    assert a == seeds.draw_seeds(42, "fabric", 8)           # same master + target -> same seeds
    assert a != seeds.draw_seeds(42, "top", 8)              # per-target streams differ
    assert a != seeds.draw_seeds(43, "fabric", 8)
    assert len(set(a)) == 8 and all(1 <= s < 2**31 for s in a)


def test_test_filter_matches_cocotb_names():
    f = re.compile(simulator.test_filter(["test_irq_routing", "test_win*"]))
    assert f.search("test_fabric.test_irq_routing")          # imported test: module differs
    assert f.search("test_top.test_window_isolation")
    assert not f.search("test_fabric.test_irq_routing_extra")
    assert not f.search("test_fabric.xtest_irq_routing")
    assert simulator.test_filter([]) is None


def test_per_test_seeds_are_independent_and_replayable():
    a = seeds.draw_seeds(42, "fabric:test_a", 4)
    assert a == seeds.draw_seeds(42, "fabric:test_a", 4)   # same master + target + test -> same seeds
    assert a != seeds.draw_seeds(42, "fabric:test_b", 4)   # every test draws its own seeds


def test_tests_glob_expands_to_files_in_dv_tests(tmp_path):
    make_project(tmp_path)
    for n in ("test_b", "test_a", "helper"):
        (tmp_path / "blk/dv/tests" / f"{n}.py").write_text("")
    (tmp_path / "blk/opendv.yaml").write_text(
        "toplevel: x\nrtl: {filelist: rtl/blk.f}\ndv: {tests: ['test_*', test_a, other_mod]}\n")
    p = config.load_project(tmp_path)
    assert p.targets["blk"].modules == ["test_a", "test_b", "other_mod"]  # sorted, no duplicates, plain names kept


def test_tests_glob_matching_nothing_is_an_error(tmp_path):
    make_project(tmp_path)
    (tmp_path / "blk/opendv.yaml").write_text("toplevel: x\nrtl: {filelist: rtl/blk.f}\ndv: {tests: ['nope_*']}\n")
    with pytest.raises(config.ConfigError, match="matches no file"):
        config.load_project(tmp_path)
