import cocotb

import router_stimulus
from dv_utils import random_pause, seed_test
from router_env import RouterEnv


@cocotb.test()
async def test_response_backpressure(dut):
    """The masters take responses late (bready/rready held low at random), so the router has to
    hold a response while the other master's access goes on. The protocol checkers watch every
    port; the scoreboard checks the traffic."""
    seed_test("test_response_backpressure")
    env = await RouterEnv.start(dut)
    env.driver.set_response_backpressure(lambda: random_pause(0.7))
    await router_stimulus.drive_rounds(env, 80)
    await env.drain()
