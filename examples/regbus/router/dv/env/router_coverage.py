"""Functional coverage for the AXI-lite router, built on cocotb-coverage.

Six coverage groups, each sampled from a different source:

  router.txn         every upstream transaction (monitor callback):
                     direction x master x output x offset bucket, full or
                     partial (strobes / alignment), and the prot field
  router.gap         cycles between consecutive transactions of one
                     master/direction: back-to-back vs. stalled
  router.contention  every genuine tie broken by an arbiter (port-level
                     probe, since the scoreboard only sees completions):
                     direction x output x winner x previous winner
  router.overlap     cycles where an output has a write and a read in
                     flight at the same time (probe)
  router.resp        every upstream transaction's response:
                     direction x output x OKAY/SLVERR
  router.stall       a slave holding a request off (its ready low while the
                     router's valid is high): direction x output (probe)

coverage_db is process-global, so bins accumulate across all tests in a
simulator run -- which is the point: no single test is expected to hit
everything.
"""

import cocotb
from cocotb.triggers import FallingEdge
from cocotb.utils import get_sim_time
from cocotb_coverage.coverage import CoverCross, CoverPoint

from axi_lite_txn import DECERR, OKAY, SLVERR, WriteTxn
from dv_utils import CLOCK_PERIOD_NS
from router_addr import decode
from router_monitor import RouterMonitor

OFFSET_BUCKET_SHIFT = 5  # 128B window / 32 -> 4 buckets


# Gap = completion-to-completion spacing for one master/direction, so it
# includes the transaction's own latency. Measured floor with zero idle and
# no contention is 5 cycles (cocotbext-axi master + router FSM), hence the
# thresholds sit just above that rather than at "0-2 idle cycles".
def gap_bin(cycles: int) -> str:
    if cycles <= 6:
        return "back_to_back"
    if cycles <= 16:
        return "short_stall"
    return "long_stall"


@CoverPoint("router.txn.direction", xf=lambda d, m, o, off, p, pr: d, bins=["write", "read"])
@CoverPoint("router.txn.master", xf=lambda d, m, o, off, p, pr: m, bins=[0, 1])
@CoverPoint("router.txn.output", xf=lambda d, m, o, off, p, pr: o, bins=[0, 1])
@CoverPoint(
    "router.txn.offset_bucket",
    xf=lambda d, m, o, off, p, pr: off >> OFFSET_BUCKET_SHIFT,
    bins=[0, 1, 2, 3],
)
@CoverPoint("router.txn.access", xf=lambda d, m, o, off, p, pr: p, bins=["full", "partial"])
@CoverPoint("router.txn.prot", xf=lambda d, m, o, off, p, pr: pr, bins=list(range(8)))
@CoverCross(
    "router.txn.dir_x_master_x_output",
    items=["router.txn.direction", "router.txn.master", "router.txn.output"],
)
@CoverCross("router.txn.dir_x_access", items=["router.txn.direction", "router.txn.access"])
def sample_txn(direction, master, output, offset, access, prot):
    pass


@CoverPoint("router.gap.direction", xf=lambda d, m, g: d, bins=["write", "read"])
@CoverPoint(
    "router.gap.kind",
    xf=lambda d, m, g: gap_bin(g),
    bins=["back_to_back", "short_stall", "long_stall"],
)
@CoverCross("router.gap.dir_x_kind", items=["router.gap.direction", "router.gap.kind"])
def sample_gap(direction, master, gap_cycles):
    pass


@CoverPoint("router.contention.direction", xf=lambda d, o, w, p: d, bins=["write", "read"])
@CoverPoint("router.contention.output", xf=lambda d, o, w, p: o, bins=[0, 1])
@CoverPoint("router.contention.winner", xf=lambda d, o, w, p: w, bins=[0, 1])
# prev winner is None for the first tie on an output; that's a legitimate
# sample but not a bin we ask for -- the interesting bins are the repeats.
@CoverPoint("router.contention.prev_winner", xf=lambda d, o, w, p: p, bins=[0, 1])
@CoverCross(
    "router.contention.dir_x_output_x_winner",
    items=["router.contention.direction", "router.contention.output", "router.contention.winner"],
)
# The arbiter flips its pointer only on a genuine tie, so the same input can
# never win two consecutive ties on one arbiter. Hitting (0,0)/(1,1) is a
# fairness bug, not a coverage bin. cocotb-coverage has no illegal_bins,
# so the cross just ignores them and _contention_probe asserts the rule.
@CoverCross(
    "router.contention.winner_x_prev",
    items=["router.contention.winner", "router.contention.prev_winner"],
    ign_bins=[(0, 0), (1, 1)],
)
def sample_contention(direction, output, winner, prev_winner):
    pass


@CoverPoint("router.overlap.output", xf=lambda o: o, bins=[0, 1])
def sample_overlap(output):
    pass


@CoverPoint("router.resp.direction", xf=lambda d, o, r: d, bins=["write", "read"])
@CoverPoint("router.resp.output", xf=lambda d, o, r: o, bins=[0, 1])
@CoverPoint("router.resp.kind", xf=lambda d, o, r: r, bins=[OKAY, SLVERR, DECERR])
@CoverCross("router.resp.dir_x_output_x_kind", items=["router.resp.direction", "router.resp.output", "router.resp.kind"])
def sample_resp(direction, output, resp):
    pass


@CoverPoint("router.stall.direction", xf=lambda d, o: d, bins=["write", "read"])
@CoverPoint("router.stall.output", xf=lambda d, o: o, bins=[0, 1])
@CoverCross("router.stall.dir_x_output", items=["router.stall.direction", "router.stall.output"])
def sample_stall(direction, output):
    pass


class RouterCoverage:
    """Hooks coverage sampling up to a RouterMonitor and the DUT ports."""

    def __init__(self, dut, monitor: RouterMonitor):
        self.dut = dut
        self._last_txn_time: dict[tuple[str, int], int] = {}
        self._prev_winner: dict[tuple[str, int], int | None] = {}
        for master, mon in enumerate(monitor.upstream):
            mon.add_callback(lambda txn, master=master: self._on_upstream(master, txn))
        cocotb.start_soon(self._contention_probe())

    def reset(self):
        """Called after a reset with nothing in flight: the arbiters start over, with no previous winner."""
        self._prev_winner.clear()
        self._last_txn_time.clear()

    # -- transaction + gap coverage ------------------------------------
    def _on_upstream(self, master: int, txn):
        direction = "write" if isinstance(txn, WriteTxn) else "read"
        output, offset = decode(txn.addr)
        # a write is partial if its strobes are not all set, a read if it is not word-aligned
        partial = txn.strb != 0xF if isinstance(txn, WriteTxn) else txn.addr & 3 != 0
        sample_txn(direction, master, output, offset, "partial" if partial else "full", txn.prot)
        sample_resp(direction, output, txn.resp)

        now = get_sim_time("ns")
        last = self._last_txn_time.get((direction, master))
        if last is not None:
            sample_gap(direction, master, int((now - last) / CLOCK_PERIOD_NS))
        self._last_txn_time[(direction, master)] = now

    # -- contention + overlap coverage ---------------------------------
    # An arbiter decides in the one cycle it is idle and sees a request, whatever the slave is
    # doing, so a tie is two requests visible while no access is in flight on that arbiter.
    # Sampled at the falling edge, a settled view of what the next rising edge will see.
    def _high(self, name: str) -> bool:
        v = getattr(self.dut, name).value
        return v.is_resolvable and bool(int(v))

    def _req(self, direction: str, master: int, output: int) -> bool:
        """Master `master` is requesting `direction` toward `output` right now."""
        valid = "aw" if direction == "write" else "ar"
        a = getattr(self.dut, f"s{master}_{valid}addr").value
        return self._high(f"s{master}_{valid}valid") and a.is_resolvable and (int(a) >> 7) == output  # top bit of ADDR_WIDTH=8

    def _granted(self, direction: str, master: int) -> bool:
        return self._high(f"s{master}_{'awready' if direction == 'write' else 'arready'}")

    def _response_taken(self, direction: str, master: int) -> bool:
        resp = "b" if direction == "write" else "r"
        return self._high(f"s{master}_{resp}valid") and self._high(f"s{master}_{resp}ready")

    async def _contention_probe(self):
        in_flight = {(d, o): False for d in ("write", "read") for o in (0, 1)}
        tie_open = dict(in_flight)  # a tie was decided and its winner has not shown up yet
        while True:
            await FallingEdge(self.dut.clk)
            for output in (0, 1):
                for direction in ("write", "read"):
                    key = (direction, output)
                    req = [self._req(direction, m, output) for m in (0, 1)]
                    granted = [self._granted(direction, m) for m in (0, 1)]
                    valid = "awvalid" if direction == "write" else "arvalid"
                    ready = "awready" if direction == "write" else "arready"
                    if self._high(f"m{output}_{valid}") and not self._high(f"m{output}_{ready}"):
                        sample_stall(direction, output)
                    if not in_flight[key]:
                        if any(req):
                            in_flight[key] = True
                            tie_open[key] = all(req)
                    elif any(self._response_taken(direction, m) for m in (0, 1)):
                        in_flight[key] = False
                    if tie_open[key] and any(granted):
                        winner = 0 if granted[0] else 1
                        prev = self._prev_winner.get(key)
                        assert prev != winner, (
                            f"{direction} arbiter m{output}: master{winner} won two "
                            f"consecutive ties -- round-robin fairness violated"
                        )
                        sample_contention(direction, output, winner, prev)
                        self._prev_winner[key] = winner
                        tie_open[key] = False
                if in_flight[("write", output)] and in_flight[("read", output)]:
                    sample_overlap(output)

