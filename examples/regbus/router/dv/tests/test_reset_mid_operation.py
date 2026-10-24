import cocotb
from cocotb.triggers import Join

from axi_lite_txn import OKAY
from router_env import RouterEnv


async def contended_write(env, i):
    """Both masters write the same output at once; returns which one the arbiter granted first."""
    first = len(env.scoreboard.write_order[0])
    t0 = cocotb.start_soon(env.driver.write(master=0, output=0, offset=0x00, value=0xA0 + i))
    t1 = cocotb.start_soon(env.driver.write(master=1, output=0, offset=0x04, value=0xB0 + i))
    await Join(t0)
    await Join(t1)
    return env.scoreboard.write_order[0][first]


@cocotb.test()
async def test_reset_mid_operation(dut):
    """A reset puts the arbiters back to their starting state: the first contended write after it
    goes to master 0, as after power-on, where without the reset the pointer would favor master 1.
    The slaves keep their contents, and traffic works as before."""
    env = await RouterEnv.start(dut)
    assert await contended_write(env, 0) == 0   # the first tie goes to master 0 ...
    # ... so the next one would go to master 1, unless a reset intervenes
    await env.reset()
    assert await contended_write(env, 1) == 0
    assert await env.driver.read(master=1, output=0, offset=0x00) == (0xA1, OKAY)
    await env.drain()
