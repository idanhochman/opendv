import cocotb

from dv_utils import random_pause, seed_test
from regfile_env import RegfileEnv
from regfile_sequences import random_traffic


@cocotb.test()
async def test_response_backpressure(dut):
    """The master takes write and read responses late (bready/rready held low at random). The
    regfile must keep each response and its data stable until taken (the protocol checker
    watches that) and still return the right values (the scoreboard checks them)."""
    seed_test("test_response_backpressure")
    env = await RegfileEnv.start(dut)
    env.driver.set_response_backpressure(lambda: random_pause(0.7))
    await random_traffic(env, 100)
    await env.drain()
