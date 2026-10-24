"""Generic AXI4-Lite slave: a byte memory that can reject accesses and be slow to accept and answer.

cocotbext-axi's AxiLiteRam always answers OKAY, so it cannot stand in for a slave that returns
errors; this one is built from the same channel classes."""

import cocotb
from cocotbext.axi.axil_channels import (
    AxiLiteARSink,
    AxiLiteAWSink,
    AxiLiteBSource,
    AxiLiteBTransaction,
    AxiLiteRSource,
    AxiLiteRTransaction,
    AxiLiteWSink,
)

from axi_lite_txn import LANES, OKAY


class AxiLiteSlave:
    """Serves one access at a time per direction. Addresses wrap at `size` bytes. If
    `error_resp(addr, is_write)` returns a response code, the access gets that code (SLVERR or
    DECERR) and does not touch the memory (a read returns 0); None means OKAY.
    `set_backpressure` slows the handshakes down."""

    def __init__(self, bus, clock, reset_n, size: int, error_resp=None):
        self.size = size
        self.mem = bytearray(size)
        self.error_resp = error_resp
        args = (clock, reset_n, False)
        self._aw = AxiLiteAWSink(bus.write.aw, *args)
        self._w = AxiLiteWSink(bus.write.w, *args)
        self._b = AxiLiteBSource(bus.write.b, *args)
        self._ar = AxiLiteARSink(bus.read.ar, *args)
        self._r = AxiLiteRSource(bus.read.r, *args)
        cocotb.start_soon(self._serve_writes())
        cocotb.start_soon(self._serve_reads())

    def set_backpressure(self, pause):
        """Every handshake on every channel stalls in the cycles where `pause()` (called once per
        channel) yields True: ready held low on AW, W and AR, valid held low on B and R. None
        removes it."""
        for channel in (self._aw, self._w, self._b, self._ar, self._r):
            channel.set_pause_generator(pause() if pause else None)

    def _response(self, addr: int, is_write: bool) -> int:
        code = self.error_resp(addr, is_write) if self.error_resp else None
        return OKAY if code is None else code

    async def _serve_writes(self):
        while True:
            aw = await self._aw.recv()
            w = await self._w.recv()
            addr = int(aw.awaddr)
            resp = self._response(addr, True)
            if resp == OKAY:
                base = addr % self.size // LANES * LANES
                for lane in range(LANES):
                    if int(w.wstrb) >> lane & 1:
                        self.mem[base + lane] = int(w.wdata) >> 8 * lane & 0xFF
            await self._b.send(AxiLiteBTransaction(bresp=resp))

    async def _serve_reads(self):
        while True:
            ar = await self._ar.recv()
            addr = int(ar.araddr)
            resp = self._response(addr, False)
            if resp != OKAY:
                await self._r.send(AxiLiteRTransaction(rdata=0, rresp=resp))
            else:
                base = addr % self.size // LANES * LANES
                await self._r.send(AxiLiteRTransaction(rdata=int.from_bytes(self.mem[base:base + LANES], "little"),
                                                       rresp=OKAY))
