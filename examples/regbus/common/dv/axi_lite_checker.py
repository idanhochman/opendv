"""Passive AXI4-Lite protocol checker.

Samples one interface at every falling clock edge, which is a settled view of what the next
rising edge will see (drivers and the DUT only change their outputs after a rising edge). An
access is a handshake when valid and ready are both high in a sample.

Rules, per interface:
  reset        every valid is low while reset has been held for more than one sample
  known        valid and ready are never X/Z outside reset; payload never is while valid is high
  stable       a valid that was not accepted stays high next cycle with an unchanged payload
  causality    bvalid only after both the AW and the W of that write were accepted, rvalid only
               after its AR was accepted (a response may not appear in the cycle of the handshake)
"""

import cocotb
from cocotb.triggers import FallingEdge

# channel -> (valid, ready, payload signals)
CHANNELS = {
    "aw": ("awvalid", "awready", ("awaddr", "awprot")),
    "w": ("wvalid", "wready", ("wdata", "wstrb")),
    "b": ("bvalid", "bready", ("bresp",)),
    "ar": ("arvalid", "arready", ("araddr", "arprot")),
    "r": ("rvalid", "rready", ("rdata", "rresp")),
}


class AxiLiteProtocolChecker:
    def __init__(self, bus, clock, reset_n, name=""):
        self.name = name
        self._clock, self._reset_n = clock, reset_n
        channels = {"aw": bus.write.aw, "w": bus.write.w, "b": bus.write.b, "ar": bus.read.ar, "r": bus.read.r}
        self._sig = {}
        for ch, (valid, ready, payload) in CHANNELS.items():
            handles = {s: getattr(channels[ch], s) for s in (valid, ready, *payload) if hasattr(channels[ch], s)}
            self._sig[ch] = (handles[valid], handles[ready], {s: h for s, h in handles.items() if s in payload})
        cocotb.start_soon(self._run())

    def _fail(self, rule: str, channel: str, detail: str):
        raise AssertionError(f"AXI-lite protocol [{rule}] on {self.name}.{channel}: {detail}")

    async def _run(self):
        accepted = {ch: 0 for ch in CHANNELS}  # handshakes seen in earlier samples
        prev = None                            # previous sample: (in_reset, {channel: (valid, ready, payload)})
        while True:
            await FallingEdge(self._clock)
            in_reset = not self._reset_n.value.is_resolvable or int(self._reset_n.value) == 0
            cur = {}
            for ch, (valid, ready, payload) in self._sig.items():
                v, r = valid.value, ready.value
                if not in_reset:
                    for label, val in (("valid", v), ("ready", r)):
                        if not val.is_resolvable:
                            self._fail("known", ch, f"{label} is {val}")
                v_on = v.is_resolvable and int(v) == 1
                if v_on:
                    for s, h in payload.items():
                        if not h.value.is_resolvable:
                            self._fail("known", ch, f"{s} is {h.value} while valid is high")
                cur[ch] = (v_on, r.is_resolvable and int(r) == 1, {s: int(h.value) for s, h in payload.items()} if v_on else None)

            if in_reset:
                if prev is not None and prev[0]:
                    for ch, (v_on, _, _) in cur.items():
                        if v_on:
                            self._fail("reset", ch, "valid is high during reset")
                accepted = {ch: 0 for ch in CHANNELS}
            else:
                if prev is not None and not prev[0]:
                    for ch, (v_on, _, payload) in cur.items():
                        p_valid, p_ready, p_payload = prev[1][ch]
                        if p_valid and not p_ready:
                            if not v_on:
                                self._fail("stable", ch, "valid dropped before the handshake")
                            if payload != p_payload:
                                self._fail("stable", ch, f"payload changed from {p_payload} to {payload} while valid was held")
                if cur["b"][0] and not (accepted["aw"] > accepted["b"] and accepted["w"] > accepted["b"]):
                    self._fail("causality", "b", "bvalid without an accepted AW and W for it")
                if cur["r"][0] and not accepted["ar"] > accepted["r"]:
                    self._fail("causality", "r", "rvalid without an accepted AR for it")
                for ch, (v_on, r_on, _) in cur.items():
                    if v_on and r_on:
                        accepted[ch] += 1
            prev = (in_reset, cur)
