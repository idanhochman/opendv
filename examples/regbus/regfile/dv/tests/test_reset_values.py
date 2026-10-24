import cocotb

from axi_lite_txn import OKAY
from regfile_env import RegfileEnv
from regfile_regs import CTRL, ID, IRQ_EN, IRQ_RAISE, IRQ_STATUS, SCRATCH


@cocotb.test()
async def test_reset_values(dut):
    """Everything reads 0 after reset except the ID."""
    env = await RegfileEnv.start(dut)
    assert await env.driver.read(ID) == (env.model.id, OKAY)
    for idx in (SCRATCH, CTRL, IRQ_RAISE, IRQ_STATUS, IRQ_EN):
        assert await env.driver.read(idx) == (0, OKAY)
    await env.check_irq()
    await env.drain()
