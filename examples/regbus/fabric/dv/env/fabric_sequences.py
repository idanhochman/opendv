"""Sequences for the fabric: regfile items sent through one master to a random regfile."""

import random

from regfile_item import RegfileItem
from regfile_regs import CTRL, ID, IRQ_EN, IRQ_RAISE, IRQ_STATUS, SCRATCH, UNMAPPED

# The masters run at the same time, and a read racing a write to one register has no single right
# answer, so each master changes only registers the other never touches (the two interrupt status
# writers belong to one master). Both may access the read-only and unmapped ones (a write there
# is rejected and changes nothing).
OWNED = {0: (SCRATCH, IRQ_EN), 1: (CTRL, IRQ_RAISE, IRQ_STATUS)}


async def disjoint_traffic(env, master: int, count: int):
    """`count` random items from `master`, each to a random regfile, on its own registers plus
    the read-only and unmapped ones."""
    allowed = (*OWNED[master], ID, *UNMAPPED)
    for _ in range(count):
        item = RegfileItem()
        item.randomize_with(lambda idx: idx in allowed)
        await env.driver.drive(item, master, random.randrange(2))
