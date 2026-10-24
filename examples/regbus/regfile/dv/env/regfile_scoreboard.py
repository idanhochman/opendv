"""Scoreboard for axi_lite_regfile: also connected to the wires between router and regfiles at fabric level."""

from axi_lite_monitor import AxiLiteMonitor
from axi_lite_txn import ReadTxn, WriteTxn
from regfile_model import RegfileModel
from regfile_regs import reg_index


class RegfileScoreboard:
    """Applies every transaction a monitor reports to the model, in the order
    the regfile completed them, and checks response and read data.

    The regfile serves one write and one read at a time, independently, so a read and a write
    racing on the same register may legally see either order. The stimulus must therefore never
    issue them concurrently to one register (the router's stimulus follows the same rule)."""

    def __init__(self, model: RegfileModel, name: str = "regfile"):
        self.model, self.name, self.checked = model, name, 0

    def connect(self, monitor: AxiLiteMonitor):
        monitor.add_callback(self._on_txn)

    def _on_txn(self, txn):
        idx = reg_index(txn.addr)
        if isinstance(txn, WriteTxn):
            exp = self.model.write(idx, txn.data, txn.strb)
            assert txn.resp == exp, (
                f"{self.name}: write idx {idx} data {txn.data:#x} strb {txn.strb:#x}: "
                f"resp {txn.resp}, expected {exp}")
        elif isinstance(txn, ReadTxn):
            data, resp = self.model.read(idx)
            assert (txn.data, txn.resp) == (data, resp), (
                f"{self.name}: read idx {idx}: got {txn.data:#x}/resp {txn.resp}, "
                f"expected {data:#x}/resp {resp}")
        self.checked += 1
