import cocotb

from axi_lite_txn import OKAY
from regfile_env import RegfileEnv
from regfile_regs import CTRL, ID, IRQ_EN, IRQ_RAISE, IRQ_STATUS, SCRATCH


@cocotb.test()
async def test_reset_mid_operation(dut):
    """A reset after the registers have been written and an interrupt is active returns every
    register to its reset value and the irq output to 0; the regfile then works as before."""
    env = await RegfileEnv.start(dut)
    await env.driver.write(SCRATCH, 0xFFFF_FFFF)
    await env.driver.write(CTRL, 0xA5)
    await env.driver.write(IRQ_EN, 0xFF)
    await env.driver.write(IRQ_RAISE, 0x0F)
    await env.check_irq()
    assert int(dut.irq.value) == 1

    await env.reset()
    assert int(dut.irq.value) == 0
    assert await env.driver.read(ID) == (env.model.id, OKAY)
    for idx in (SCRATCH, CTRL, IRQ_RAISE, IRQ_STATUS, IRQ_EN):
        assert await env.driver.read(idx) == (0, OKAY)

    await env.driver.write(SCRATCH, 0x1234_5678)
    assert await env.driver.read(SCRATCH) == (0x1234_5678, OKAY)
    await env.drain()
