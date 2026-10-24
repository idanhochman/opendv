import cocotb

from axi_lite_txn import SLVERR
from fabric_env import FabricEnv
from regfile_regs import ID, UNMAPPED


@cocotb.test()
async def test_error_response_reaches_master(dut):
    """SLVERR generated in a regfile makes it back through the router."""
    env = await FabricEnv.start(dut)
    for rf in (0, 1):
        assert await env.driver.write(rf, rf, ID, 0) == SLVERR
        for idx in UNMAPPED:
            assert await env.driver.read(1 - rf, rf, idx) == (0, SLVERR)
    await env.drain()
