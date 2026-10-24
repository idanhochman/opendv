"""Generic AXI4-Lite master driver, built on cocotbext-axi's AxiLiteMaster."""

from cocotbext.axi import AxiLiteMaster, AxiProt


class AxiLiteDriver:
    """Drives accesses and reports what came back. It does not judge the responses (that is the
    scoreboard's job) and counts what it issued, so an env can check that every access was seen."""

    def __init__(self, bus, clock, reset_n):
        self._master = AxiLiteMaster(bus, clock, reset_n, reset_active_level=False)
        self.issued = 0

    def set_response_backpressure(self, pause):
        """Hold bready and rready low whenever `pause()` (called once per channel) yields True for
        the cycle; None removes it. Exercises slaves whose responses are not taken at once."""
        self._master.write_if.b_channel.set_pause_generator(pause() if pause else None)
        self._master.read_if.r_channel.set_pause_generator(pause() if pause else None)

    async def write(self, addr: int, data: int, prot: int = 0) -> int:
        self.issued += 1
        resp = await self._master.write(addr, data.to_bytes(4, "little"), prot=AxiProt(prot))
        return resp.resp

    async def write_bytes(self, addr: int, data: bytes, prot: int = 0) -> int:
        """Partial write: only the byte lanes covered by [addr, addr+len(data))
        get their wstrb bit set."""
        self.issued += 1
        resp = await self._master.write(addr, data, prot=AxiProt(prot))
        return resp.resp

    async def read(self, addr: int, length: int = 4, prot: int = 0) -> tuple[int, int]:
        """Read `length` bytes from `addr`; the value is those bytes, little-endian."""
        self.issued += 1
        resp = await self._master.read(addr, length, prot=AxiProt(prot))
        return int.from_bytes(resp.data, "little"), resp.resp
