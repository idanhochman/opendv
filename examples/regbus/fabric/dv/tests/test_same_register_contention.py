import random

import cocotb
from cocotb.triggers import Join

from axi_lite_txn import OKAY
from dv_utils import seed_test
from fabric_env import FabricEnv
from regfile_regs import SCRATCH


@cocotb.test()
async def test_same_register_contention(dut):
    """Both masters write the same register at the same time. Either value may win, but a read
    afterwards must return one of them; the scoreboard checks it against what the regfile saw last."""
    seed_test("test_same_register_contention")
    env = await FabricEnv.start(dut)
    for i in range(20):
        a, b = random.getrandbits(32), random.getrandbits(32)
        t0 = cocotb.start_soon(env.driver.write(0, 0, SCRATCH, a))
        t1 = cocotb.start_soon(env.driver.write(1, 0, SCRATCH, b))
        await Join(t0)
        await Join(t1)
        value, resp = await env.driver.read(i % 2, 0, SCRATCH)
        assert resp == OKAY and value in (a, b), f"round {i}: {value:#x} not in {{{a:#x}, {b:#x}}}"
    await env.drain()
