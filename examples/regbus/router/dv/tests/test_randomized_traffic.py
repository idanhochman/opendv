import random

import cocotb
from cocotb.triggers import Join

from axi_lite_txn import OKAY
from dv_utils import seed_test
from router_env import RouterEnv

# Each master gets its own offsets, so no read can race another master's write to the same
# address; the masters still contend for the outputs.
OFFSETS = {0: (0x00, 0x04, 0x08), 1: (0x0C, 0x10)}


@cocotb.test()
async def test_randomized_traffic(dut):
    """Random reads and writes from both masters across both outputs. Each master checks its own
    reads against what it wrote; the scoreboard independently checks everything the router
    forwarded and returned."""
    seed_test("test_randomized_traffic")
    env = await RouterEnv.start(dut)

    async def worker(master):
        written = {}  # (output, offset) -> value
        for _ in range(30):
            output = random.choice([0, 1])
            offset = random.choice(OFFSETS[master])
            if random.random() < 0.5 or (output, offset) not in written:
                written[output, offset] = random.getrandbits(32)
                await env.driver.write(master, output, offset, written[output, offset])
            else:
                got = await env.driver.read(master, output, offset)
                assert got == (written[output, offset], OKAY), (
                    f"master{master} out{output}+0x{offset:02x}: got {got}, expected {written[output, offset]:#x}")

    t0 = cocotb.start_soon(worker(0))
    t1 = cocotb.start_soon(worker(1))
    await Join(t0)
    await Join(t1)
    await env.drain()
