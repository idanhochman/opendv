"""Register map of axi_lite_regfile and the helpers every regfile-level component shares."""

# word index (addr[4:2]) of each register
ID, SCRATCH, CTRL, IRQ_RAISE, IRQ_STATUS, IRQ_EN = range(6)
UNMAPPED = (6, 7)


def reg_addr(idx: int, byte: int = 0, window: int = 0, alias: int = 0) -> int:
    """Byte address of register `idx` at byte offset `byte`. The regfile decodes only addr[4:2], so the
    bits above ([6:5], `alias`) alias onto the same registers; `window` is the top bit, used upstream
    to steer between regfiles."""
    return (window << 7) | (alias << 5) | (idx << 2) | byte


def reg_index(addr: int) -> int:
    return (addr >> 2) & 7
