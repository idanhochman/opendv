"""Constrained-random stimulus for the router, built on cocotb-coverage's
Randomized, and a closure loop that keeps generating rounds until the
functional coverage in router_coverage.py is full (or a cap is hit).

A *round* is one transaction per master, started together after a random
idle gap. Two shapes:
  contend      both masters hit the same output with the same direction at
               the same instant -> forces an arbitration tie
  independent  each master draws its own transaction and idle time
"""

import random

import cocotb
from cocotb.triggers import ClockCycles, Join
from cocotb_coverage.coverage import CoverCross, CoverPoint, coverage_db
from cocotb_coverage.crv import Randomized

from router_addr import RAM_SIZE
from router_env import RouterEnv

OFFSETS = list(range(0, RAM_SIZE, 4))  # word-aligned, spans all 4 offset buckets
IDLES = [0, 1, 2, 4, 8, 16]            # cycles of idle before issuing
SLVERR_FROM = 0x70                     # where the closure test's slaves start answering SLVERR ...
DECERR_FROM = 0x78                     # ... and DECERR
FULL_WORD_PROBABILITY = 2 / 3


class TxnItem(Randomized):
    def __init__(self, written: set):
        super().__init__()
        self.direction = "write"
        self.output = 0
        self.offset = 0
        self.idle = 0
        self.byte = 0
        self.length = 4
        self.prot = 0
        self.add_rand("direction", ["write", "read"])
        self.add_rand("output", [0, 1])
        self.add_rand("offset", OFFSETS)
        self.add_rand("idle", IDLES)
        self.add_rand("byte", [0, 1, 2, 3])
        self.add_rand("length", [1, 2, 3, 4])
        self.add_rand("prot", [*range(8)])
        self.add_constraint(lambda byte, length: byte + length <= 4)
        # Reads are only legal where a write has already completed: the
        # scoreboard has no expected value for never-written addresses.
        # `written` is shared, live state -- re-evaluated on every solve.
        self.add_constraint(
            lambda direction, offset, output: direction == "write" or (output, offset) in written
        )

    def post_randomize(self):
        """The solver is uniform over the lane patterns; most accesses should be full words."""
        if random.random() < FULL_WORD_PROBABILITY:
            self.byte, self.length = 0, 4

    def __repr__(self):
        return (f"{self.direction} out{self.output}+0x{self.offset:02x} lanes {self.byte}..{self.byte + self.length - 1} "
                f"prot={self.prot} idle={self.idle}")


def make_round(written: set, p_contend: float) -> tuple[TxnItem, TxnItem]:
    """The two masters run concurrently, so they must not touch the same
    address if either one writes: a read racing a write may legitimately
    return the old or the new value, and the scoreboard has no single answer
    to check it against."""
    a, b = TxnItem(written), TxnItem(written)
    a.randomize()
    contend = random.random() < p_contend

    def no_race(direction, offset, output):
        return (output, offset) != (a.output, a.offset) or (direction, a.direction) == ("read", "read")

    if contend:
        # Same output, same direction, same start cycle as `a`; only the offset is free.
        b.randomize_with(
            lambda direction, idle, offset, output: direction == a.direction
            and idle == a.idle
            and output == a.output
            and no_race(direction, offset, output)
        )
    else:
        # cocotb-coverage keeps one constraint per set of variables: a second
        # (direction, offset, output) constraint would silently replace the
        # "reads only where written" one in TxnItem, so state both together.
        b.randomize_with(
            lambda direction, offset, output: (direction == "write" or (output, offset) in written)
            and no_race(direction, offset, output)
        )
    return a, b


async def run_item(env: RouterEnv, master: int, item: TxnItem, written: set):
    await ClockCycles(env.dut.clk, item.idle)
    if item.direction == "write":
        await env.driver.write(master, item.output, item.offset, random.getrandbits(32), item.byte, item.length, item.prot)
        written.add((item.output, item.offset))
    else:
        await env.driver.read(master, item.output, item.offset, item.byte, item.length, item.prot)


def holes(prefix: str = "router.") -> list[str]:
    """Un-hit bins across every leaf CoverPoint/CoverCross under `prefix`."""
    missing = []
    for name in coverage_db:
        item = coverage_db[name]
        if not name.startswith(prefix) or not isinstance(item, (CoverPoint, CoverCross)):
            continue
        for bin_, hits in item.detailed_coverage.items():
            if hits < item.at_least:
                missing.append(f"{name} {bin_}")
    return missing


async def run_round(env: RouterEnv, written: set, p_contend: float):
    a, b = make_round(written, p_contend)
    t0 = cocotb.start_soon(run_item(env, 0, a, written))
    t1 = cocotb.start_soon(run_item(env, 1, b, written))
    await Join(t0)
    await Join(t1)


async def drive_rounds(env: RouterEnv, rounds: int, p_contend: float = 0.5):
    """`rounds` rounds of constrained-random traffic."""
    written: set = set()
    for _ in range(rounds):
        await run_round(env, written, p_contend)


async def drive_until_closed(env: RouterEnv, max_rounds: int = 400, p_contend: float = 0.5) -> int:
    """Generate rounds until all router.* coverage groups are full.
    Returns the number of rounds used."""
    written: set = set()
    for n in range(1, max_rounds + 1):
        await run_round(env, written, p_contend)
        if not holes():
            return n
    return max_rounds
