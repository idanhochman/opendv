"""Agent for one regfile interface. Active: drives it and watches it (regfile as DUT, or a master
port of a subsystem). Passive: only watches (the wires between a router and a regfile). Either way
it carries a monitor for the scoreboards and a protocol checker."""

from axi_lite_checker import AxiLiteProtocolChecker
from axi_lite_monitor import AxiLiteMonitor
from regfile_driver import RegfileDriver


class RegfileAgent:
    def __init__(self, bus, clock, reset_n, name: str = "", active: bool = True):
        self.monitor = AxiLiteMonitor(bus, clock, reset_n, name=name)
        self.checker = AxiLiteProtocolChecker(bus, clock, reset_n, name=name)
        self.driver = RegfileDriver(bus, clock, reset_n) if active else None
