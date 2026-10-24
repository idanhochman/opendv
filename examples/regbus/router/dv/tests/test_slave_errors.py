import cocotb
from cocotb.triggers import Join

from axi_lite_txn import DECERR, OKAY, SLVERR
from router_env import RouterEnv

SLVERR_FROM = 0x70  # the top of each output's window answers SLVERR ...
DECERR_FROM = 0x78  # ... and the very top DECERR


@cocotb.test()
async def test_slave_errors(dut):
    """An output slave answers SLVERR, then DECERR, for the top of its window. The router must
    hand each error code back to the right master, leave accesses to the rest of the window
    unaffected, and keep arbitrating when both masters are rejected at once."""
    env = await RouterEnv.start(dut)

    # a value in each error region, written while the slave still accepts
    await env.driver.write(master=0, output=1, offset=SLVERR_FROM, value=0x600D0000)
    await env.driver.write(master=0, output=1, offset=DECERR_FROM, value=0x600D0001)
    await env.driver.write(master=0, output=0, offset=SLVERR_FROM, value=0x600D0002)
    await env.driver.write(master=0, output=0, offset=DECERR_FROM, value=0x600D0003)
    await env.driver.write(master=1, output=0, offset=0x10, value=0xCAFEF00D)

    env.set_slave_errors(SLVERR_FROM, DECERR_FROM)

    for master in (0, 1):  # each master gets each code, for a write and for a read, from each output
        for output in (0, 1):
            assert await env.driver.write(master, output, SLVERR_FROM, value=0xBAD0BAD0) == SLVERR
            assert await env.driver.write(master, output, DECERR_FROM, value=0xBAD0BAD1) == DECERR
            assert await env.driver.read(master, output, SLVERR_FROM + 4) == (0, SLVERR)
            assert await env.driver.read(master, output, DECERR_FROM + 4) == (0, DECERR)
    assert await env.driver.read(master=1, output=0, offset=0x10) == (0xCAFEF00D, OKAY)  # the rest of the window is fine

    for i in range(4):  # both masters rejected at once, on one output
        t0 = cocotb.start_soon(env.driver.write(master=0, output=0, offset=SLVERR_FROM, value=i))
        t1 = cocotb.start_soon(env.driver.read(master=1, output=0, offset=DECERR_FROM + 4))
        await Join(t0)
        await Join(t1)
        assert t0.result() == SLVERR and t1.result() == (0, DECERR)

    env.set_slave_errors(None)
    # the rejected writes changed nothing
    assert await env.driver.read(master=0, output=1, offset=SLVERR_FROM) == (0x600D0000, OKAY)
    assert await env.driver.read(master=0, output=1, offset=DECERR_FROM) == (0x600D0001, OKAY)
    assert await env.driver.read(master=0, output=0, offset=SLVERR_FROM) == (0x600D0002, OKAY)
    assert await env.driver.read(master=0, output=0, offset=DECERR_FROM) == (0x600D0003, OKAY)
    await env.drain()
