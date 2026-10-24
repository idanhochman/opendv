"""Address map of axi_lite_router: the top address bit steers to output 0 or 1."""

ADDR_WIDTH = 8
RAM_SIZE = 2 ** (ADDR_WIDTH - 1)  # 128B: local size of each output's window
OUT1_BASE = 1 << (ADDR_WIDTH - 1)


def addr(output: int, offset: int) -> int:
    assert 0 <= offset < RAM_SIZE
    return offset if output == 0 else OUT1_BASE + offset


def decode(full_addr: int) -> tuple[int, int]:
    """Inverse of addr(): (output, offset) from a full router-side address."""
    output = 1 if full_addr & OUT1_BASE else 0
    return output, full_addr & (RAM_SIZE - 1)
