import cocotb

from dv_utils import seed_test
from regfile_env import RegfileEnv
from regfile_sequences import random_traffic


@cocotb.test()
async def test_random_traffic(dut):
    """Random reads and writes (all registers, lanes and idle gaps); the scoreboard checks every
    response against the model."""
    seed_test("test_random_traffic")
    env = await RegfileEnv.start(dut)
    await random_traffic(env, 300)
    await env.drain()
