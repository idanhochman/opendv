import cocotb

import router_stimulus
from dv_utils import random_pause, seed_test
from router_env import RouterEnv


@cocotb.test()
async def test_random_coverage_closure(dut):
    """Constrained-random rounds until router.* functional coverage is full (see
    router_stimulus.py), against slaves that are slow and reject the top of their window (SLVERR, then DECERR). The
    round cap makes a stuck bin fail loudly instead of hanging."""
    seed_test("test_random_coverage_closure")
    env = await RouterEnv.start(dut)
    env.set_slave_errors(router_stimulus.SLVERR_FROM, router_stimulus.DECERR_FROM)
    for slave in env.slaves:
        slave.set_backpressure(lambda: random_pause(0.3))
    rounds = await router_stimulus.drive_until_closed(env)
    missing = router_stimulus.holes()
    dut._log.info(f"coverage closure: {rounds} rounds, holes={missing}")
    assert not missing, f"coverage holes after {rounds} rounds: {missing}"
    await env.drain()
