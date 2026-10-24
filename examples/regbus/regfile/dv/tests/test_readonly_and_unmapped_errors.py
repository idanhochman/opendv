import cocotb

from axi_lite_txn import OKAY, SLVERR
from regfile_env import RegfileEnv
from regfile_regs import ID, UNMAPPED


@cocotb.test()
async def test_readonly_and_unmapped_errors(dut):
    """Writing the ID, and any access to indexes 6/7, responds SLVERR and
    leaves state alone."""
    env = await RegfileEnv.start(dut)
    assert await env.driver.write(ID, 0xFFFFFFFF) == SLVERR
    assert await env.driver.read(ID) == (env.model.id, OKAY)
    for idx in UNMAPPED:
        assert await env.driver.write(idx, 0x1234) == SLVERR
        assert await env.driver.read(idx) == (0, SLVERR)
    await env.drain()
