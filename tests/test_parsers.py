from opendv import results
from opendv.codecov import data

XML_V2 = """<testsuites><testsuite>
<testcase name="a"><properties><property name="sim_time_unit" value="ns"/>
<property name="sim_time_start" value="0.0"/><property name="sim_time_stop" value="250.0"/>
<property name="sim_time_duration" value="250.0"/></properties></testcase>
<testcase name="b"><properties><property name="sim_time_unit" value="ns"/>
<property name="sim_time_start" value="250.0"/><property name="sim_time_stop" value="460.0"/>
<property name="sim_time_duration" value="210.0"/></properties><failure message="boom"/></testcase>
</testsuite></testsuites>"""

XML_V1 = """<testsuites><testsuite>
<testcase name="a" sim_time_ns="100"/><testcase name="b" sim_time_ns="50"/>
</testsuite></testsuites>"""


def _parse(tmp_path, xml):
    (tmp_path / "results.xml").write_text(xml)
    return results.parse_results(tmp_path)


def test_sim_times_cocotb2(tmp_path):
    a, b = _parse(tmp_path, XML_V2)
    assert (a["start_ns"], a["sim_ns"], a["status"]) == (0.0, 250.0, "pass")
    assert (b["start_ns"], b["end_ns"], b["status"]) == (250.0, 460.0, "fail")


def test_sim_times_cocotb1_fallback(tmp_path):
    a, b = _parse(tmp_path, XML_V1)
    assert (a["start_ns"], b["start_ns"], b["end_ns"]) == (0.0, 100.0, 150.0)


def _dat(tmp_path, *records):
    p = tmp_path / "merged.dat"
    lines = ["# SystemC::Coverage-3"]
    for what, count in records:
        lines.append(f"C 'f/x/a.sv\x01l\x0212\x01o\x02{what}\x01h\x02top.a\x01page\x02v_toggle/a' {count}")
    p.write_text("\n".join(lines) + "\n")
    return data.parse_dat(p)


def test_directional_toggle_merged_per_bit(tmp_path):
    pts = _dat(tmp_path, ("req:0->1", 5), ("req:1->0", 3), ("d[2]:0->1", 4), ("d[2]:1->0", 0))
    by = {p["what"]: p for p in pts}
    assert set(by) == {"req", "d[2]"}
    assert by["req"]["count"] == 3 and (by["req"]["rise"], by["req"]["fall"]) == (5, 3)
    assert by["d[2]"]["count"] == 0  # only one direction seen -> hole
    assert data.bit_key("d[2]") == ("d", 2)


def test_non_directional_toggle_untouched(tmp_path):
    (p,) = _dat(tmp_path, ("req", 7))
    assert p["what"] == "req" and p["count"] == 7 and "rise" not in p


LOG_V2 = """\
  4750.01ns INFO     cocotb.axi_lite_router.s0          Write start addr: 0x00000064
  4800.01ns WARNING  cocotb.regression                  test_router.test_random_coverage_closure failed
                                                        Traceback (most recent call last):
                                                          File "x.py", line 1, in f
                                                        AssertionError: m0+0x64: master1 read 0x9aefecca, expected 7
                                                        assert 1 == 2
  4800.01ns INFO     cocotb.regression                  running test_router.test_zz (7/7)
"""


def test_failure_scraped_from_cocotb2_warning_line(tmp_path):
    (tmp_path / "sim.log").write_text(LOG_V2)
    got = results.parse_log_failures(tmp_path)["test_random_coverage_closure"]
    assert got["at_ns"] == 4800.01
    assert got["message"].startswith("AssertionError: m0+0x64")


def test_fmt_wall_picks_a_readable_unit():
    from opendv.report.format import fmt_wall
    assert [fmt_wall(x) for x in (0.4, 1.5, 9.96, 12.4, 59.6, 125, 3000.2, 3599.7, 3900, 7261)] == [
        "400 ms", "1.5 s", "10 s", "12 s", "1m 00s", "2m 05s", "50m 00s", "1h 00m", "1h 05m", "2h 01m"]
