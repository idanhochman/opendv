import cocotb
from cocotb.triggers import ClockCycles

from axi_lite_txn import OKAY
from fabric_env import FabricEnv
from regfile_regs import CTRL, IRQ_EN, IRQ_RAISE, SCRATCH


@cocotb.test()
async def test_reset_mid_operation(dut):
    """A reset after both regfiles hold state and raise interrupts returns both to their reset
    values and both irq outputs to 0; both are reachable from both masters afterwards."""
    env = await FabricEnv.start(dut)
    for rf in (0, 1):
        await env.driver.write(0, rf, SCRATCH, 0xDEAD_0000 + rf)
        await env.driver.write(1, rf, CTRL, 0x5A)
        await env.driver.write(0, rf, IRQ_EN, 0xFF)
        await env.driver.write(1, rf, IRQ_RAISE, 0x01)
    await ClockCycles(dut.clk, 3)
    assert (env.irq(0), env.irq(1)) == (1, 1)

    await env.reset()
    assert (env.irq(0), env.irq(1)) == (0, 0)
    for master in (0, 1):
        for rf in (0, 1):
            for idx in (SCRATCH, CTRL, IRQ_EN):
                assert await env.driver.read(master, rf, idx) == (0, OKAY)
    await env.drain()
