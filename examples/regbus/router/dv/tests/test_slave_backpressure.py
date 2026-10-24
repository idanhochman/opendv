import cocotb

import router_stimulus
from dv_utils import random_pause, seed_test
from router_env import RouterEnv


@cocotb.test()
async def test_slave_backpressure(dut):
    """The output slaves are slow: ready and valid are held low at random on every channel. The
    router must hold each request and response steady until it is taken (the protocol checkers
    watch that) and keep the masters' accesses straight (the scoreboard checks them)."""
    seed_test("test_slave_backpressure")
    env = await RouterEnv.start(dut)
    for slave in env.slaves:
        slave.set_backpressure(lambda: random_pause(0.5))
    await router_stimulus.drive_rounds(env, 80)
    await env.drain()
