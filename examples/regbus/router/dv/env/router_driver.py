"""Router-level driver: (master, output, offset) in, AXI-lite access out."""

from cocotbext.axi import AxiLiteBus

from axi_lite_driver import AxiLiteDriver
from router_addr import addr


class RouterDriver:
    """Owns one AxiLiteDriver per input port (s0, s1). Pure stimulus -- no checking; see
    RouterScoreboard for that."""

    def __init__(self, dut, clock, reset_n):
        self.masters = [
            AxiLiteDriver(AxiLiteBus.from_prefix(dut, f"s{i}"), clock, reset_n)
            for i in range(2)
        ]

    @property
    def issued(self) -> int:
        return sum(m.issued for m in self.masters)

    def set_response_backpressure(self, pause):
        for m in self.masters:
            m.set_response_backpressure(pause)

    async def write(self, master: int, output: int, offset: int, value: int, byte: int = 0, length: int = 4,
                    prot: int = 0) -> int:
        """Write `length` bytes (the low ones of `value`) at lane `byte` of the word at `offset`."""
        target = addr(output, offset)
        if length < 4:
            lanes = (value & ((1 << 8 * length) - 1)).to_bytes(length, "little")
            return await self.masters[master].write_bytes(target + byte, lanes, prot)
        return await self.masters[master].write(target, value, prot)

    async def read(self, master: int, output: int, offset: int, byte: int = 0, length: int = 4,
                   prot: int = 0) -> tuple[int, int]:
        """Read `length` bytes at lane `byte` of the word at `offset`; the value is those bytes."""
        return await self.masters[master].read(addr(output, offset) + byte, length, prot)
