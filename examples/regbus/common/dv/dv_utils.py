"""Small helpers shared by every testbench."""

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge
from cocotb_coverage.coverage import coverage_db

CLOCK_PERIOD_NS = 10


def seed_test(name: str):
    """Seed `random` from the simulator-wide RANDOM_SEED plus the test name,
    so a regression seed reaches every test but each test's stream is
    independent of which other tests ran (reproducible with TESTCASE=...)."""
    seed = f"{cocotb.RANDOM_SEED}:{name}"
    random.seed(seed)
    cocotb.log.info(f"random seed for {name}: {seed}")


def random_pause(probability: float):
    """A pause generator for cocotbext-axi channels: True (stall) with `probability` each cycle."""
    while True:
        yield random.random() < probability


def export_coverage_at_end(path: str = "coverage.yml"):
    """Write the functional coverage database to `path` when the simulation ends. Every test runs
    in its own simulator process, so its coverage_db is complete by then; the file is where the
    engine merges it from. cocotb has no public end-of-simulation hook, so this uses the one cocotb
    itself uses (the image pins cocotb)."""
    cocotb._shutdown.register(lambda: coverage_db.export_to_yaml(filename=path))


def start_clock(dut):
    cocotb.start_soon(Clock(dut.clk, CLOCK_PERIOD_NS, units="ns").start())


async def reset(dut, cycles: int = 5):
    """Hold the active-low reset for `cycles` clocks, then release it."""
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, cycles)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
