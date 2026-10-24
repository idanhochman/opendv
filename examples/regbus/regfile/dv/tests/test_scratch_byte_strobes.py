import cocotb

from axi_lite_txn import OKAY
from regfile_env import RegfileEnv
from regfile_regs import SCRATCH


@cocotb.test()
async def test_scratch_byte_strobes(dut):
    """Partial writes touch only their byte lanes; the scoreboard's model
    predicts the merged value."""
    env = await RegfileEnv.start(dut)
    await env.driver.write(SCRATCH, 0x11223344)
    await env.driver.write_bytes(SCRATCH, 1, b"\xAA")  # lane 1 only
    assert await env.driver.read(SCRATCH) == (0x1122AA44, OKAY)
    await env.driver.write_bytes(SCRATCH, 2, b"\xBB\xCC")  # lanes 2 and 3
    assert await env.driver.read(SCRATCH) == (0xCCBBAA44, OKAY)
    await env.drain()
