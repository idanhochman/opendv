"""Functional coverage for axi_lite_regfile, built on cocotb-coverage.

Sampled from the monitor's transactions, after the scoreboard has applied each to the model:

  regfile.access  every access: register x direction (including the read-only, write-only and
                  unmapped ones, which answer differently)
  regfile.lanes   every write to a writable register: which byte lanes it covered (the 10
                  contiguous patterns) x register
  regfile.irq     every write to a register that moves the interrupt: which register x the
                  irq output before and after (a raise cannot clear it, a clear cannot set it)
"""

from cocotb_coverage.coverage import CoverCross, CoverPoint

from axi_lite_monitor import AxiLiteMonitor
from axi_lite_txn import WriteTxn
from regfile_model import RegfileModel
from regfile_regs import CTRL, IRQ_EN, IRQ_RAISE, IRQ_STATUS, SCRATCH, reg_index

WRITABLE = (SCRATCH, CTRL, IRQ_RAISE, IRQ_STATUS, IRQ_EN)
LANE_STROBES = [0x1, 0x2, 0x4, 0x8, 0x3, 0x6, 0xC, 0x7, 0xE, 0xF]  # contiguous lane patterns
IRQ_WRITES = (IRQ_RAISE, IRQ_STATUS, IRQ_EN)
IRQ_MOVES = [(0, 0), (0, 1), (1, 0), (1, 1)]  # irq before, after


@CoverPoint("regfile.access.register", xf=lambda r, d: r, bins=list(range(8)))
@CoverPoint("regfile.access.direction", xf=lambda r, d: d, bins=["write", "read"])
@CoverCross("regfile.access.register_x_direction", items=["regfile.access.register", "regfile.access.direction"])
def sample_access(register, direction):
    pass


@CoverPoint("regfile.lanes.register", xf=lambda r, s: r, bins=list(WRITABLE))
@CoverPoint("regfile.lanes.strobe", xf=lambda r, s: s, bins=LANE_STROBES)
@CoverCross("regfile.lanes.register_x_strobe", items=["regfile.lanes.register", "regfile.lanes.strobe"])
def sample_lanes(register, strobe):
    pass


@CoverPoint("regfile.irq.register", xf=lambda r, b, a: r, bins=list(IRQ_WRITES))
@CoverPoint("regfile.irq.move", xf=lambda r, b, a: (b, a), bins=IRQ_MOVES, bins_labels=["0>0", "0>1", "1>0", "1>1"])
# A raise only sets status bits and a clear only clears them, so neither can move the irq the
# other way; enabling and masking can do both.
@CoverCross("regfile.irq.register_x_move", items=["regfile.irq.register", "regfile.irq.move"],
            ign_bins=[(IRQ_RAISE, "1>0"), (IRQ_STATUS, "0>1")])
def sample_irq(register, before, after):
    pass


class RegfileCoverage:
    """Must be connected after the scoreboard, so the model already includes the transaction."""

    def __init__(self, model: RegfileModel, monitor: AxiLiteMonitor):
        self._model = model
        self._irq = int(model.irq)
        monitor.add_callback(self._on_txn)

    def reset(self):
        self._irq = int(self._model.irq)

    def _on_txn(self, txn):
        idx = reg_index(txn.addr)
        write = isinstance(txn, WriteTxn)
        sample_access(idx, "write" if write else "read")
        irq = int(self._model.irq)
        if write:
            sample_lanes(idx, txn.strb)
            sample_irq(idx, self._irq, irq)
        self._irq = irq
