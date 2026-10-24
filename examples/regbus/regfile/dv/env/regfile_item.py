"""One access to the regfile: what a sequence hands to the driver."""

import random

from cocotb_coverage.crv import Randomized

IDLES = [0, 1, 2, 4, 8]  # idle cycles before the access
FULL_WORD_PROBABILITY = 2 / 3


class RegfileItem(Randomized):
    """A read or write of register `idx`, covering `length` byte lanes starting at lane `byte` (a
    full word is byte 0, length 4; a narrow read still returns the whole word on the bus). `alias`
    sets address bits [6:5] and `window` bit 7, which the regfile ignores (a subsystem uses bit 7
    to steer, so there the driver's `window` overrides it), and `prot` is the AXI protection
    field, which it also ignores. Randomizing picks a register (mapped, read-only or unmapped), the access,
    the lanes, alias, prot and the idle gap. The solver is uniform over the lane patterns, so
    afterwards most accesses are turned into full-word ones; `data` is random 32-bit and always
    set, since a 2**32 domain is not something to enumerate."""

    def __init__(self, write: bool = True, idx: int = 0, data: int = 0, byte: int = 0, length: int = 4,
                 idle: int = 0, alias: int = 0, window: int = 0, prot: int = 0):
        super().__init__()
        self.write, self.idx, self.data, self.byte, self.length, self.idle = write, idx, data, byte, length, idle
        self.alias, self.window, self.prot = alias, window, prot
        self.add_rand("write", [True, False])
        self.add_rand("idx", [*range(8)])
        self.add_rand("byte", [0, 1, 2, 3])
        self.add_rand("length", [1, 2, 3, 4])
        self.add_rand("idle", IDLES)
        self.add_rand("alias", [0, 1, 2, 3])
        self.add_rand("window", [0, 1])
        self.add_rand("prot", [*range(8)])
        self.add_constraint(lambda byte, length: byte + length <= 4)

    def post_randomize(self):
        self.data = random.getrandbits(32)
        if random.random() < FULL_WORD_PROBABILITY:
            self.byte, self.length = 0, 4

    def __repr__(self):
        lanes = f"lanes {self.byte}..{self.byte + self.length - 1}"
        what = f"write data={self.data:#010x}" if self.write else "read"
        return f"{what} reg{self.idx} {lanes} alias={self.alias} window={self.window} prot={self.prot} idle={self.idle}"
