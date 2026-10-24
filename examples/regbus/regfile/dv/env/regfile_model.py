"""Reference model of axi_lite_regfile: plain Python, no simulator. Reused at subsystem level."""

from axi_lite_txn import OKAY, SLVERR, merge_lanes as merge
from regfile_regs import CTRL, ID, IRQ_EN, IRQ_RAISE, IRQ_STATUS, SCRATCH


class RegfileModel:
    def __init__(self, reg_id: int):
        self.id = reg_id
        self.reset()

    def reset(self):
        self.scratch = self.ctrl = self.irq_status = self.irq_en = 0

    def write(self, idx: int, data: int, strb: int) -> int:
        if idx == SCRATCH:
            self.scratch = merge(self.scratch, data, strb)
        elif idx == CTRL:
            self.ctrl = merge(self.ctrl, data, strb) & 0xFF
        elif idx == IRQ_RAISE:
            self.irq_status |= merge(0, data, strb) & 0xFF
        elif idx == IRQ_STATUS:
            self.irq_status &= ~merge(0, data, strb) & 0xFFFFFFFF
        elif idx == IRQ_EN:
            self.irq_en = merge(self.irq_en, data, strb) & 0xFF
        else:  # ID is read-only, 6 and 7 are unmapped
            return SLVERR
        return OKAY

    def read(self, idx: int) -> tuple[int, int]:
        regs = {ID: self.id, SCRATCH: self.scratch, CTRL: self.ctrl, IRQ_RAISE: 0,
                IRQ_STATUS: self.irq_status, IRQ_EN: self.irq_en}
        if idx in regs:
            return regs[idx], OKAY
        return 0, SLVERR

    @property
    def irq(self) -> bool:
        return bool(self.irq_status & self.irq_en & 0xFF)
