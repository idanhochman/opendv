import cocotb
from cocotb.triggers import ClockCycles

from fabric_env import FabricEnv
from regfile_regs import IRQ_EN, IRQ_RAISE, IRQ_STATUS


@cocotb.test()
async def test_irq_routing(dut):
    """An interrupt raised in one regfile shows on its own irq output only, and both show at
    once when both are raised."""
    env = await FabricEnv.start(dut)
    for rf in (0, 1):
        other = 1 - rf
        await env.driver.write(0, rf, IRQ_RAISE, 0x08)
        await env.driver.write(1, rf, IRQ_EN, 0x08)
        await ClockCycles(dut.clk, 3)
        assert (env.irq(rf), env.irq(other)) == (1, 0), f"regfile{rf}: irq outputs wrong"
        await env.driver.write(1, rf, IRQ_STATUS, 0x08)
        await ClockCycles(dut.clk, 3)
        assert (env.irq(rf), env.irq(other)) == (0, 0)
    for rf in (0, 1):
        await env.driver.write(0, rf, IRQ_RAISE, 0x08)
        await env.driver.write(1, rf, IRQ_EN, 0x08)
    await ClockCycles(dut.clk, 3)
    assert (env.irq(0), env.irq(1)) == (1, 1)
    await env.drain()
