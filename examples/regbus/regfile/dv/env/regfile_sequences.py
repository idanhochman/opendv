"""Sequences for the regfile: generators of items that run them through the env's driver."""

import random

from regfile_item import RegfileItem
from regfile_regs import CTRL, IRQ_EN, IRQ_RAISE, IRQ_STATUS, SCRATCH

WRITABLE = (SCRATCH, CTRL, IRQ_RAISE, IRQ_STATUS, IRQ_EN)
LANE_PATTERNS = [(byte, length) for byte in range(4) for length in range(1, 5 - byte)]  # the 10 contiguous ones


async def random_traffic(env, count: int):
    """`count` random items over all registers (mapped, read-only, unmapped), lanes and idle
    gaps. Now and then the irq output is compared with the model's."""
    for _ in range(count):
        item = RegfileItem()
        item.randomize()
        await env.driver.drive(item)
        if random.random() < 0.1:
            await env.check_irq()


async def lane_sweep(env):
    """Every contiguous byte-lane pattern written to every writable register, each read back."""
    for idx in WRITABLE:
        for byte, length in LANE_PATTERNS:
            await env.driver.drive(RegfileItem(write=True, idx=idx, data=random.getrandbits(32), byte=byte, length=length))
            await env.driver.drive(RegfileItem(write=False, idx=idx))
