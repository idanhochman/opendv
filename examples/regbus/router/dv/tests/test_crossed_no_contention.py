import cocotb
from cocotb.triggers import Join

from axi_lite_txn import OKAY
from router_env import RouterEnv


@cocotb.test()
async def test_crossed_no_contention(dut):
    """Master 0 -> output 1 and master 1 -> output 0 concurrently: different
    outputs, so both should complete without waiting on each other."""
    env = await RouterEnv.start(dut)

    t0 = cocotb.start_soon(env.driver.write(master=0, output=1, offset=0x04, value=0x11111111))
    t1 = cocotb.start_soon(env.driver.write(master=1, output=0, offset=0x08, value=0x22222222))
    await Join(t0)
    await Join(t1)

    assert await env.driver.read(master=0, output=1, offset=0x04) == (0x11111111, OKAY)
    assert await env.driver.read(master=1, output=0, offset=0x08) == (0x22222222, OKAY)
    await env.drain()
