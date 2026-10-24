"""Env for axi_lite_router: wiring only. Components live in router_{addr,driver,monitor,agent,scoreboard,
coverage}.py; constrained-random stimulus is router_stimulus.py."""

from cocotb.triggers import ClockCycles

from axi_lite_txn import DECERR, SLVERR
from dv_utils import export_coverage_at_end, reset, start_clock
from router_addr import RAM_SIZE
from router_agent import RouterAgent
from router_coverage import RouterCoverage
from router_scoreboard import RouterScoreboard


class RouterEnv:
    def __init__(self, dut):
        self.dut = dut
        start_clock(dut)
        export_coverage_at_end()
        self.agent = RouterAgent(dut, dut.clk, dut.rst_n)
        self.driver = self.agent.driver
        self.slaves = self.agent.slaves
        self.scoreboard = RouterScoreboard()
        self.scoreboard.connect(self.agent.monitor)
        self.coverage = RouterCoverage(dut, self.agent.monitor)

    @classmethod
    async def start(cls, dut):
        """Build the env and bring the DUT out of reset: how every test begins."""
        env = cls(dut)
        await reset(dut)
        return env

    async def reset(self):
        """Reset the DUT in the middle of a test, with nothing in flight. The slaves keep their
        contents, so the scoreboard's model stays valid."""
        await reset(self.dut)
        self.coverage.reset()

    def set_slave_errors(self, slverr_from: int | None, decerr_from: int | None = None):
        """Each output slave answers SLVERR to accesses at and above offset `slverr_from` of its
        window, and DECERR at and above `decerr_from` (None: never)."""
        def respond(addr, is_write):
            offset = addr % RAM_SIZE
            if decerr_from is not None and offset >= decerr_from:
                return DECERR
            if slverr_from is not None and offset >= slverr_from:
                return SLVERR
            return None
        for slave in self.slaves:
            slave.error_resp = respond

    async def drain(self):
        """Let the monitors report the last transaction, then check that the scoreboard
        matched everything the driver issued, on both sides of the router."""
        await ClockCycles(self.dut.clk, 6)
        assert self.scoreboard.checked == self.driver.issued, (
            f"scoreboard checked {self.scoreboard.checked} of {self.driver.issued} transactions")
        assert not self.scoreboard.pending, f"{self.scoreboard.pending} access(es) seen on only one side of the router"
