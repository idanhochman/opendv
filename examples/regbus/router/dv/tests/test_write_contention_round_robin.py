import cocotb
from cocotb.triggers import Join

from axi_lite_txn import OKAY
from router_env import RouterEnv


@cocotb.test()
async def test_write_contention_round_robin(dut):
    """Both masters write the same output at the same time, repeatedly. The arbiter must
    serialize them without corrupting either transaction and alternate the winner on genuine
    contention. Who won each round is read from the scoreboard, which records grants as they
    reach the router's output port."""
    env = await RouterEnv.start(dut)

    for i in range(6):
        t0 = cocotb.start_soon(env.driver.write(master=0, output=0, offset=0x00, value=0xA0000000 + i))
        t1 = cocotb.start_soon(env.driver.write(master=1, output=0, offset=0x04, value=0xB0000000 + i))
        await Join(t0)
        await Join(t1)

        assert await env.driver.read(master=0, output=0, offset=0x00) == (0xA0000000 + i, OKAY)
        assert await env.driver.read(master=0, output=0, offset=0x04) == (0xB0000000 + i, OKAY)

    # write_order[0] lists the grants on that output in completion order -- winner, then loser,
    # each round -- so the winner of round i is every other entry.
    winners = env.scoreboard.write_order[0][::2]
    assert winners == [0, 1, 0, 1, 0, 1] or winners == [1, 0, 1, 0, 1, 0], winners
    await env.drain()
