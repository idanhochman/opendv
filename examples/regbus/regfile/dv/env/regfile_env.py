"""Env for axi_lite_regfile: wiring only. Components live in regfile_{regs,model,item,driver,agent,scoreboard,coverage}.py; sequences in regfile_sequences.py."""

from cocotb.triggers import ClockCycles
from cocotbext.axi import AxiLiteBus

from dv_utils import export_coverage_at_end, reset, start_clock
from regfile_agent import RegfileAgent
from regfile_coverage import RegfileCoverage
from regfile_model import RegfileModel
from regfile_scoreboard import RegfileScoreboard

REG_ID = 0x5EF0_0001  # the regfile's ID parameter


class RegfileEnv:
    def __init__(self, dut):
        self.dut = dut
        start_clock(dut)
        export_coverage_at_end()
        self.agent = RegfileAgent(AxiLiteBus.from_prefix(dut, "s"), dut.clk, dut.rst_n, name="s")
        self.driver = self.agent.driver
        self.model = RegfileModel(REG_ID)
        self.scoreboard = RegfileScoreboard(self.model)
        self.scoreboard.connect(self.agent.monitor)
        self.coverage = RegfileCoverage(self.model, self.agent.monitor)  # after the scoreboard: it reads the model

    @classmethod
    async def start(cls, dut):
        """Build the env and bring the DUT out of reset: how every test begins."""
        env = cls(dut)
        await reset(dut)
        return env

    async def reset(self):
        """Reset the DUT in the middle of a test, with nothing in flight; the model follows."""
        await reset(self.dut)
        self.model.reset()
        self.coverage.reset()

    async def check_irq(self):
        """The irq output matches the model's."""
        await ClockCycles(self.dut.clk, 2)
        assert int(self.dut.irq.value) == int(self.model.irq), (
            f"irq {int(self.dut.irq.value)}, model says {int(self.model.irq)}")

    async def drain(self):
        """Let the monitor report the last transaction, then check that the
        scoreboard saw everything the driver issued."""
        await ClockCycles(self.dut.clk, 4)
        assert self.scoreboard.checked == self.driver.issued, (
            f"scoreboard checked {self.scoreboard.checked} of {self.driver.issued} transactions")
