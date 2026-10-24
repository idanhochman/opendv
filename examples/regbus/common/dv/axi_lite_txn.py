"""Whole AXI4-Lite transactions, as the driver reports them and the monitor observes them."""

from dataclasses import dataclass

OKAY, SLVERR, DECERR = 0, 2, 3  # the response codes AXI4-Lite has (no EXOKAY)
LANES = 4


def merge_lanes(old: int, new: int, strb: int) -> int:
    """`old` with the byte lanes selected by `strb` replaced from `new`."""
    out = old
    for lane in range(LANES):
        if strb >> lane & 1:
            mask = 0xFF << (8 * lane)
            out = (out & ~mask) | (new & mask)
    return out


@dataclass
class WriteTxn:
    addr: int
    data: int
    strb: int
    resp: int
    prot: int = 0


@dataclass
class ReadTxn:
    addr: int
    data: int
    resp: int
    prot: int = 0
