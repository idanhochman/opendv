import cocotb
from cocotb.triggers import Join

from dv_utils import seed_test
from fabric_env import FabricEnv
from fabric_sequences import disjoint_traffic


@cocotb.test()
async def test_concurrent_disjoint_random(dut):
    """Both masters run random traffic at the same time, each on registers nobody else changes.
    The routing scoreboard checks every access and response across the fabric, the regfile
    scoreboards check the register behavior, and at the end the irq outputs must match the models."""
    seed_test("test_concurrent_disjoint_random")
    env = await FabricEnv.start(dut)
    tasks = [cocotb.start_soon(disjoint_traffic(env, m, 120)) for m in (0, 1)]
    for t in tasks:
        await Join(t)
    await env.drain()
    assert (env.irq(0), env.irq(1)) == tuple(int(m.irq) for m in env.models)
