"""Functional coverage for the fabric subsystem (and the chip top, which reuses its env): integration
only, since the regfile's own behavior is covered at the regfile target.

  fabric.route  every access seen on a master port: master x regfile (the window) x direction
  fabric.resp   every response returned to a master: regfile x OKAY/SLVERR (an error from either
                regfile has to make it back through the router)
  fabric.irq    after every access at a regfile: the two irq outputs together, so each
                regfile's interrupt is seen alone and both at once
"""

from cocotb_coverage.coverage import CoverCross, CoverPoint

from axi_lite_monitor import AxiLiteMonitor
from axi_lite_txn import OKAY, SLVERR, WriteTxn
from regfile_agent import RegfileAgent
from regfile_model import RegfileModel


def window(addr: int) -> int:
    return addr >> 7 & 1


@CoverPoint("fabric.route.master", xf=lambda m, r, d: m, bins=[0, 1])
@CoverPoint("fabric.route.regfile", xf=lambda m, r, d: r, bins=[0, 1])
@CoverPoint("fabric.route.direction", xf=lambda m, r, d: d, bins=["write", "read"])
@CoverCross("fabric.route.master_x_regfile_x_direction",
            items=["fabric.route.master", "fabric.route.regfile", "fabric.route.direction"])
def sample_route(master, regfile, direction):
    pass


@CoverPoint("fabric.resp.regfile", xf=lambda r, k: r, bins=[0, 1])
@CoverPoint("fabric.resp.kind", xf=lambda r, k: k, bins=[OKAY, SLVERR])
@CoverCross("fabric.resp.regfile_x_kind", items=["fabric.resp.regfile", "fabric.resp.kind"])
def sample_resp(regfile, kind):
    pass


@CoverPoint("fabric.irq.outputs", xf=lambda i0, i1: (i0, i1), bins=[(0, 0), (0, 1), (1, 0), (1, 1)],
            bins_labels=["none", "irq1 only", "irq0 only", "both"])
def sample_irq(irq0, irq1):
    pass


class FabricCoverage:
    """Must be connected after the regfile scoreboards, so the models already include the access."""

    def __init__(self, master_monitors: list[AxiLiteMonitor], agents: list[RegfileAgent], models: list[RegfileModel]):
        self._models = models
        for master, mon in enumerate(master_monitors):
            mon.add_callback(lambda txn, master=master: self._on_master(master, txn))
        for agent in agents:
            agent.monitor.add_callback(self._on_regfile)

    def _on_master(self, master: int, txn):
        regfile = window(txn.addr)
        sample_route(master, regfile, "write" if isinstance(txn, WriteTxn) else "read")
        sample_resp(regfile, txn.resp)

    def _on_regfile(self, txn):
        sample_irq(*(int(m.irq) for m in self._models))
