"""Generic AXI4-Lite interface monitor.

cocotbext-axi has monitors for the individual channels (AW, W, B, AR, R) but none for a whole
interface; this one composes them into whole write/read transactions."""

import cocotb
from cocotbext.axi.axil_channels import (
    AxiLiteARMonitor,
    AxiLiteAWMonitor,
    AxiLiteBMonitor,
    AxiLiteRMonitor,
    AxiLiteWMonitor,
)

from axi_lite_txn import ReadTxn, WriteTxn


class AxiLiteMonitor:
    """Passive observer of one AXI-lite interface. Pairs AW+W+B and AR+R first-in first-out into
    whole transactions and pushes each to every registered callback.

    The pairing is valid for an interface that completes its accesses in order, which holds for
    every interface in this example: each master has one outstanding access at a time."""

    def __init__(self, bus, clock, reset_n, name=""):
        self.name = name
        self._callbacks = []
        self._aw_mon = AxiLiteAWMonitor(bus.write.aw, clock, reset_n, reset_active_level=False)
        self._w_mon = AxiLiteWMonitor(bus.write.w, clock, reset_n, reset_active_level=False)
        self._b_mon = AxiLiteBMonitor(bus.write.b, clock, reset_n, reset_active_level=False)
        self._ar_mon = AxiLiteARMonitor(bus.read.ar, clock, reset_n, reset_active_level=False)
        self._r_mon = AxiLiteRMonitor(bus.read.r, clock, reset_n, reset_active_level=False)
        cocotb.start_soon(self._run_write())
        cocotb.start_soon(self._run_read())

    def add_callback(self, fn):
        self._callbacks.append(fn)

    def _emit(self, txn):
        for cb in self._callbacks:
            cb(txn)

    async def _run_write(self):
        while True:
            aw = await self._aw_mon.recv()
            w = await self._w_mon.recv()
            b = await self._b_mon.recv()
            self._emit(WriteTxn(int(aw.awaddr), int(w.wdata), int(w.wstrb), int(b.bresp), int(aw.awprot)))

    async def _run_read(self):
        while True:
            ar = await self._ar_mon.recv()
            r = await self._r_mon.recv()
            self._emit(ReadTxn(int(ar.araddr), int(r.rdata), int(r.rresp), int(ar.arprot)))
