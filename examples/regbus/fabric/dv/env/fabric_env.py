"""Env for the fabric subsystem (2 masters -> router -> 2 regfiles), also used unchanged by the
chip top, which wraps the fabric. Besides the driver it adds nothing of its own: the regfile
components are reused.

  driver      FabricDriver on the two master ports (the address window picks the regfile)
  agents      passive regfile agents on the router<->regfile wires, so the scoreboards see the
              order in which accesses actually reached each regfile
  checkers    a protocol checker on each master port (the agents carry one on the regfile side)
  routing     a passthrough scoreboard between the master ports and the regfile ports: every access
              reaches the regfile its window selects, unchanged, and its response gets back unchanged
  models      one regfile model + scoreboard per regfile, from regfile/dv/env"""

from cocotb.triggers import ClockCycles
from cocotbext.axi import AxiLiteBus

from axi_lite_checker import AxiLiteProtocolChecker
from axi_lite_monitor import AxiLiteMonitor
from axi_lite_passthrough import AxiLitePassthroughScoreboard
from dv_utils import export_coverage_at_end, reset, start_clock
from fabric_coverage import FabricCoverage
from fabric_driver import FabricDriver
from regfile_agent import RegfileAgent
from regfile_model import RegfileModel
from regfile_scoreboard import RegfileScoreboard

# Regfile IDs differ per level: the top overrides the fabric defaults.
IDS = {
    "axi_lite_fabric": (0xFAB0_0000, 0xFAB0_0001),
    "regbus_top": (0xA0A0_0001, 0xA0A0_0002),
}


class FabricEnv:
    def __init__(self, dut):
        self.dut = dut
        # The router<->regfile wires live in the fabric; at chip top that is one level down.
        self.scope = dut.fabric if hasattr(dut, "fabric") else dut
        self.ids = IDS[dut._name]
        start_clock(dut)
        export_coverage_at_end()

        self.driver = FabricDriver(dut, dut.clk, dut.rst_n)
        self.checkers = [AxiLiteProtocolChecker(AxiLiteBus.from_prefix(dut, f"s{m}"), dut.clk, dut.rst_n, name=f"s{m}")
                         for m in range(2)]
        self.agents = [RegfileAgent(AxiLiteBus.from_prefix(self.scope, f"r{k}"), dut.clk, dut.rst_n,
                                    name=f"r{k}", active=False) for k in range(2)]
        self.master_monitors = [AxiLiteMonitor(AxiLiteBus.from_prefix(dut, f"s{m}"), dut.clk, dut.rst_n, name=f"s{m}")
                                for m in range(2)]
        self.routing = AxiLitePassthroughScoreboard(lambda addr: addr >> 7 & 1, 2)  # the window bit picks the regfile
        self.routing.connect(self.master_monitors, [a.monitor for a in self.agents])
        self.models = [RegfileModel(i) for i in self.ids]
        self.scoreboards = [RegfileScoreboard(mod, f"regfile{k}") for k, mod in enumerate(self.models)]
        for sb, agent in zip(self.scoreboards, self.agents):
            sb.connect(agent.monitor)
        self.coverage = FabricCoverage(self.master_monitors, self.agents, self.models)  # after the scoreboards: it reads the models

    @classmethod
    async def start(cls, dut):
        """Build the env and bring the DUT out of reset: how every test begins."""
        env = cls(dut)
        await reset(dut)
        return env

    async def reset(self):
        """Reset the DUT in the middle of a test, with nothing in flight; the models follow."""
        await reset(self.dut)
        for model in self.models:
            model.reset()

    def irq(self, regfile: int) -> int:
        return int(getattr(self.scope, f"irq{regfile}").value)

    async def drain(self):
        """Let the monitors report the last transaction, then check that the scoreboards saw
        everything the driver issued, on both sides of the fabric."""
        await ClockCycles(self.dut.clk, 6)
        checked = sum(sb.checked for sb in self.scoreboards)
        assert checked == self.driver.issued, f"regfile scoreboards checked {checked} of {self.driver.issued} transactions"
        assert self.routing.checked == self.driver.issued, (
            f"routing scoreboard matched {self.routing.checked} of {self.driver.issued} transactions")
        assert not self.routing.pending, f"{self.routing.pending} access(es) seen on only one side of the fabric"
