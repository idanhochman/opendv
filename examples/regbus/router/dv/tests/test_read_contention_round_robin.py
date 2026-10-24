import cocotb
from cocotb.triggers import Join

from router_env import RouterEnv


@cocotb.test()
async def test_read_contention_round_robin(dut):
    """Same as the write test, but for the AR/R path."""
    env = await RouterEnv.start(dut)

    await env.driver.write(master=0, output=1, offset=0x00, value=0x1234)
    await env.driver.write(master=0, output=1, offset=0x04, value=0x5678)

    for _ in range(6):
        t0 = cocotb.start_soon(env.driver.read(master=0, output=1, offset=0x00))
        t1 = cocotb.start_soon(env.driver.read(master=1, output=1, offset=0x04))
        await Join(t0)
        await Join(t1)

    winners = env.scoreboard.read_order[1][::2]
    assert winners == [0, 1, 0, 1, 0, 1] or winners == [1, 0, 1, 0, 1, 0], winners
    await env.drain()
