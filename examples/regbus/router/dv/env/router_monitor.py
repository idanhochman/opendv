"""Router-level monitor: both sides of the router, each port watched independently."""

from cocotbext.axi import AxiLiteBus

from axi_lite_monitor import AxiLiteMonitor


class RouterMonitor:
    """One AxiLiteMonitor per port: s0/s1 (upstream, one per master) and
    m0/m1 (downstream, one per output).
    """

    def __init__(self, dut, clock, reset_n):
        self.upstream = [
            AxiLiteMonitor(AxiLiteBus.from_prefix(dut, f"s{i}"), clock, reset_n, name=f"s{i}")
            for i in range(2)
        ]
        self.downstream = [
            AxiLiteMonitor(AxiLiteBus.from_prefix(dut, f"m{i}"), clock, reset_n, name=f"m{i}")
            for i in range(2)
        ]
