import cocotb

from axi_lite_txn import OKAY
from regfile_env import RegfileEnv
from regfile_regs import CTRL, IRQ_EN, IRQ_RAISE, IRQ_STATUS


@cocotb.test()
async def test_register_masks(dut):
    """CTRL, IRQ_STATUS and IRQ_EN only implement bits [7:0]."""
    env = await RegfileEnv.start(dut)
    for idx in (CTRL, IRQ_EN):
        await env.driver.write(idx, 0xFFFF_FFFF)
        assert await env.driver.read(idx) == (0xFF, OKAY)
    await env.driver.write(IRQ_RAISE, 0xFFFF_FFFF)
    assert await env.driver.read(IRQ_STATUS) == (0xFF, OKAY)
    await env.drain()
