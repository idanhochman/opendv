import cocotb

from regfile_env import RegfileEnv
from regfile_regs import IRQ_EN, IRQ_RAISE, IRQ_STATUS


@cocotb.test()
async def test_irq(dut):
    """raise -> enable -> irq; W1C clears; only [7:0] exists."""
    env = await RegfileEnv.start(dut)
    await env.driver.write(IRQ_RAISE, 0x0000_01F0)  # bit 8 is out of range
    assert (await env.driver.read(IRQ_STATUS))[0] == 0xF0
    await env.check_irq()  # raised but not enabled
    assert int(dut.irq.value) == 0
    await env.driver.write(IRQ_EN, 0x10)
    await env.check_irq()
    assert int(dut.irq.value) == 1
    await env.driver.write(IRQ_STATUS, 0x10)  # W1C the enabled bit
    await env.check_irq()
    assert int(dut.irq.value) == 0
    assert (await env.driver.read(IRQ_STATUS))[0] == 0xE0
    await env.drain()
