import cocotb
from cocotb.triggers import Join

from dv_utils import random_pause, seed_test
from fabric_env import FabricEnv
from fabric_sequences import disjoint_traffic


@cocotb.test()
async def test_response_backpressure(dut):
    """Both masters take responses late (bready/rready held low at random) while the other keeps
    going, so the router has to hold a response for one master while serving the other. The
    protocol checkers watch every interface; the scoreboards check the traffic."""
    seed_test("test_response_backpressure")
    env = await FabricEnv.start(dut)
    env.driver.set_response_backpressure(lambda: random_pause(0.7))
    tasks = [cocotb.start_soon(disjoint_traffic(env, m, 60)) for m in (0, 1)]
    for t in tasks:
        await Join(t)
    await env.drain()
