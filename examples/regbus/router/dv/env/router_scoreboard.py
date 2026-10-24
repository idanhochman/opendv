"""Scoreboard for axi_lite_router: the generic passthrough checks, plus the data the output slaves hold."""

from axi_lite_passthrough import AxiLitePassthroughScoreboard
from axi_lite_txn import LANES, OKAY, merge_lanes
from router_addr import decode
from router_monitor import RouterMonitor


class RouterScoreboard(AxiLitePassthroughScoreboard):
    """Also tracks what each output slave holds, built from the writes it accepted (answered OKAY,
    merged by byte strobe), and checks that every successful read returns the last value written
    to its word. A read of a word nothing has written is a bug in the test."""

    def __init__(self, output_count: int = 2):
        super().__init__(lambda addr: decode(addr)[0], output_count)
        self.model: dict[tuple[int, int], int] = {}

    def connect(self, monitor: RouterMonitor):
        super().connect(monitor.upstream, monitor.downstream)

    def on_pair(self, direction, slave, master, up, down, where):
        if up.resp != OKAY:
            return
        key = (slave, decode(up.addr)[1] // LANES * LANES)  # the word
        if direction == "write":
            self.model[key] = merge_lanes(self.model.get(key, 0), up.data, up.strb)
        else:
            assert key in self.model, f"{where}: read of a word nothing has written"
            assert down.data == self.model[key], f"{where}: slave returned {down.data:#x}, last write was {self.model[key]:#x}"
