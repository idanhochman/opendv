import cocotb

from axi_lite_txn import OKAY
from fabric_env import FabricEnv
from regfile_regs import ID


@cocotb.test()
async def test_routing_and_ids(dut):
    """Every master reaches both regfiles and reads back that regfile's ID."""
    env = await FabricEnv.start(dut)
    for master in (0, 1):
        for rf in (0, 1):
            assert await env.driver.read(master, rf, ID) == (env.ids[rf], OKAY)
    await env.drain()
