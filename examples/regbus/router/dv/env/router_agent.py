"""Everything that touches the router's ports: the driver and monitor on the master side, a slave
model on each output, and a protocol checker on each of the four ports."""

from cocotbext.axi import AxiLiteBus

from axi_lite_checker import AxiLiteProtocolChecker
from axi_lite_slave import AxiLiteSlave
from router_addr import RAM_SIZE
from router_driver import RouterDriver
from router_monitor import RouterMonitor


class RouterAgent:
    def __init__(self, dut, clock, reset_n):
        self.driver = RouterDriver(dut, clock, reset_n)
        self.monitor = RouterMonitor(dut, clock, reset_n)
        self.slaves = [AxiLiteSlave(AxiLiteBus.from_prefix(dut, f"m{i}"), clock, reset_n, size=RAM_SIZE)
                       for i in range(2)]
        self.checkers = [AxiLiteProtocolChecker(AxiLiteBus.from_prefix(dut, port), clock, reset_n, name=port)
                         for port in ("s0", "s1", "m0", "m1")]
