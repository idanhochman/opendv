"""Fabric-level driver: (master, regfile, register) in, AXI-lite access out."""

from cocotbext.axi import AxiLiteBus

from regfile_driver import RegfileDriver
from regfile_item import RegfileItem


class FabricDriver:
    """One regfile driver per master port (s0, s1); the address window picks the regfile."""

    def __init__(self, dut, clock, reset_n):
        self.masters = [RegfileDriver(AxiLiteBus.from_prefix(dut, f"s{m}"), clock, reset_n) for m in range(2)]

    @property
    def issued(self) -> int:
        return sum(m.issued for m in self.masters)

    def set_response_backpressure(self, pause):
        for m in self.masters:
            m.set_response_backpressure(pause)

    async def drive(self, item: RegfileItem, master: int, regfile: int):
        await self.masters[master].drive(item, window=regfile)

    async def write(self, master: int, regfile: int, idx: int, value: int) -> int:
        return await self.masters[master].write(idx, value, window=regfile)

    async def write_bytes(self, master: int, regfile: int, idx: int, byte: int, data: bytes) -> int:
        return await self.masters[master].write_bytes(idx, byte, data, window=regfile)

    async def read(self, master: int, regfile: int, idx: int) -> tuple[int, int]:
        return await self.masters[master].read(idx, window=regfile)
