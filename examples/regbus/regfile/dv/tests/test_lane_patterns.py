import cocotb

from dv_utils import seed_test
from regfile_env import RegfileEnv
from regfile_sequences import lane_sweep


@cocotb.test()
async def test_lane_patterns(dut):
    """Every contiguous byte-lane write pattern against every writable register, each read back;
    the model predicts the merged value and the register's implemented bits."""
    seed_test("test_lane_patterns")
    env = await RegfileEnv.start(dut)
    await lane_sweep(env)
    await env.drain()
