"""Seeds: a regression's master seed and the per-test seeds drawn from it."""

import random


def new_master_seed() -> int:
    return random.SystemRandom().randrange(1, 2**31)


def draw_seeds(master: int, target: str, n: int) -> list[int]:
    """n distinct seeds, a pure function of (master seed, name) so a whole
    regression can be replayed from its master seed. `target` is any key; the
    regress passes 'target:test' so every test draws its own seeds."""
    return sorted(random.Random(f"{master}:{target}").sample(range(1, 2**31), n))
