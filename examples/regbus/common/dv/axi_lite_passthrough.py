"""Scoreboard for a block that routes AXI4-Lite accesses from several masters to several slaves
without changing them (a router, or a fabric made of one)."""

from collections import deque

from axi_lite_monitor import AxiLiteMonitor
from axi_lite_txn import WriteTxn


class AxiLitePassthroughScoreboard:
    """Pairs each access seen on a master port (tagged with its master) with the access it became
    on a slave port, one FIFO per slave and direction -- valid because the block never reorders
    within a slave port. A block that forwards AW/W and the response in the same cycle lets either
    side's monitor report first; whichever arrives first waits for its counterpart.

    Checks on every pair: the address, data and strobes were forwarded unchanged, and the slave's
    response and read data were handed back to the master unchanged. `write_order` / `read_order`
    record which master was granted on each slave port, in the order the grants reached it.
    Subclasses add checks in `on_pair`.

    `route` maps an address to the slave port it must reach."""

    def __init__(self, route, slave_count: int):
        self.route = route
        self.checked = 0
        self.write_order = {s: [] for s in range(slave_count)}
        self.read_order = {s: [] for s in range(slave_count)}
        # (direction, slave) -> accesses waiting for their counterpart
        self._upstream = {(d, s): deque() for d in ("write", "read") for s in range(slave_count)}
        self._downstream = {(d, s): deque() for d in ("write", "read") for s in range(slave_count)}

    def connect(self, masters: list[AxiLiteMonitor], slaves: list[AxiLiteMonitor]):
        for master, mon in enumerate(masters):
            mon.add_callback(lambda txn, master=master: self._on_upstream(master, txn))
        for slave, mon in enumerate(slaves):
            mon.add_callback(lambda txn, slave=slave: self._on_downstream(slave, txn))

    @property
    def pending(self) -> int:
        """Accesses seen on one side only."""
        return sum(len(q) for q in (*self._upstream.values(), *self._downstream.values()))

    @staticmethod
    def _direction(txn) -> str:
        return "write" if isinstance(txn, WriteTxn) else "read"

    def _on_upstream(self, master: int, txn):
        key = (self._direction(txn), self.route(txn.addr))
        if self._downstream[key]:
            self._check(key, master, txn, self._downstream[key].popleft())
        else:
            self._upstream[key].append((master, txn))

    def _on_downstream(self, slave: int, txn):
        key = (self._direction(txn), slave)
        if self._upstream[key]:
            master, up = self._upstream[key].popleft()
            self._check(key, master, up, txn)
        else:
            self._downstream[key].append(txn)

    def _check(self, key, master: int, up, down):
        direction, slave = key
        where = f"slave{slave} {direction} from master{master} @0x{up.addr:02x}"
        assert down.addr == up.addr, f"{where}: forwarded address 0x{down.addr:02x}"
        assert down.prot == up.prot, f"{where}: prot {up.prot}, forwarded {down.prot}"
        assert down.resp == up.resp, f"{where}: slave responded {down.resp}, master got {up.resp}"
        if direction == "write":
            assert down.data == up.data, f"{where}: sent {up.data:#x}, forwarded {down.data:#x}"
            assert down.strb == up.strb, f"{where}: strobes {up.strb:#x}, forwarded {down.strb:#x}"
            self.write_order[slave].append(master)
        else:
            assert up.data == down.data, f"{where}: slave returned {down.data:#x}, master got {up.data:#x}"
            self.read_order[slave].append(master)
        self.on_pair(direction, slave, master, up, down, where)
        self.checked += 1

    def on_pair(self, direction: str, slave: int, master: int, up, down, where: str):
        """Hook for checks beyond passthrough; called with each matched pair."""
