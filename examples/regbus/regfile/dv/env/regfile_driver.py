"""Register-level driver for axi_lite_regfile: register index in, AXI-lite access out."""

from cocotb.triggers import ClockCycles

from axi_lite_driver import AxiLiteDriver
from regfile_item import RegfileItem
from regfile_regs import reg_addr


class RegfileDriver:
    """Pure stimulus; the scoreboard does the checking. `window` selects the address
    window upstream of the regfile (0 when the regfile is the DUT)."""

    def __init__(self, bus, clock, reset_n):
        self._clock = clock
        self._axi = AxiLiteDriver(bus, clock, reset_n)

    @property
    def issued(self) -> int:
        return self._axi.issued

    def set_response_backpressure(self, pause):
        self._axi.set_response_backpressure(pause)

    async def drive(self, item: RegfileItem, window: int | None = None):
        """Execute one item: its idle gap, then the access. `window` overrides the item's."""
        if window is None:
            window = item.window
        if item.idle:
            await ClockCycles(self._clock, item.idle)
        if not item.write:
            await self.read(item.idx, window, item.alias, item.byte, item.length, item.prot)
        elif item.length < 4:
            lanes = (item.data & ((1 << 8 * item.length) - 1)).to_bytes(item.length, "little")
            await self.write_bytes(item.idx, item.byte, lanes, window, item.alias, item.prot)
        else:
            await self.write(item.idx, item.data, window, item.alias, item.prot)

    async def write(self, idx: int, value: int, window: int = 0, alias: int = 0, prot: int = 0) -> int:
        return await self._axi.write(reg_addr(idx, window=window, alias=alias), value, prot)

    async def write_bytes(self, idx: int, byte: int, data: bytes, window: int = 0, alias: int = 0, prot: int = 0) -> int:
        return await self._axi.write_bytes(reg_addr(idx, byte, window, alias), data, prot)

    async def read(self, idx: int, window: int = 0, alias: int = 0, byte: int = 0, length: int = 4,
                   prot: int = 0) -> tuple[int, int]:
        """Read `length` bytes at lane `byte`; the value is those bytes, little-endian."""
        return await self._axi.read(reg_addr(idx, byte, window, alias), length, prot)
