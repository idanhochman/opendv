import cocotb

from axi_lite_txn import OKAY
from fabric_env import FabricEnv
from regfile_regs import SCRATCH


@cocotb.test()
async def test_window_isolation(dut):
    """The same register in the two regfiles holds independent values, from
    either master."""
    env = await FabricEnv.start(dut)
    await env.driver.write(0, 0, SCRATCH, 0x0000_AAAA)
    await env.driver.write(1, 1, SCRATCH, 0x0000_BBBB)
    for master in (0, 1):
        assert await env.driver.read(master, 0, SCRATCH) == (0x0000_AAAA, OKAY)
        assert await env.driver.read(master, 1, SCRATCH) == (0x0000_BBBB, OKAY)
    await env.drain()
