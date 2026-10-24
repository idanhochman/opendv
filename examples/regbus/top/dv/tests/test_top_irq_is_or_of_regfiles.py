"""Chip top's own check; the fabric's tests run unchanged against the top (see opendv.yaml)."""

import cocotb
from cocotb.triggers import ClockCycles

from fabric_env import FabricEnv
from regfile_regs import IRQ_EN, IRQ_RAISE, IRQ_STATUS


@cocotb.test()
async def test_top_irq_is_or_of_regfiles(dut):
    env = await FabricEnv.start(dut)
    for rf in (0, 1):
        await env.driver.write(0, rf, IRQ_EN, 0x01)
    expected = {(0, 0): 0, (1, 0): 1, (0, 1): 1, (1, 1): 1}
    for (r0, r1), want in expected.items():
        for rf, raised in ((0, r0), (1, r1)):
            await env.driver.write(1, rf, IRQ_STATUS, 0xFF)  # clear
            if raised:
                await env.driver.write(1, rf, IRQ_RAISE, 0x01)
        await ClockCycles(dut.clk, 3)
        assert int(dut.irq.value) == want, f"raised={(r0, r1)}: irq={int(dut.irq.value)}, expected {want}"
    await env.drain()
