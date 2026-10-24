import cocotb

from axi_lite_txn import OKAY
from router_env import RouterEnv


@cocotb.test()
async def test_basic_write_read(dut):
    """Each master talks to its own output, no contention: sanity check the
    plumbing (address decode, per-output RAM) before stressing arbitration."""
    env = await RouterEnv.start(dut)

    await env.driver.write(master=0, output=0, offset=0x10, value=0xCAFEF00D)
    assert await env.driver.read(master=0, output=0, offset=0x10) == (0xCAFEF00D, OKAY)

    await env.driver.write(master=1, output=1, offset=0x20, value=0xDEADBEEF)
    assert await env.driver.read(master=1, output=1, offset=0x20) == (0xDEADBEEF, OKAY)
    await env.drain()
