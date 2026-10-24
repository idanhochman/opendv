// Round-robin 2:1 arbiter for one AXI4-Lite write channel triplet (AW/W/B).
// Grants one requester the output for a full AW+W+B transaction at a time
// (non-preemptive); on contention, the loser gets priority next time so
// neither input can starve. `s{n}_req` must be `s{n}_awvalid` already
// qualified by address decode (i.e. "input n wants *this* output").
//
// Assumes each input has at most one outstanding write at a time (the
// caller does not raise a new s{n}_req until this transaction's B has been
// accepted) — see rtl/axi_lite_router.sv for the destination decode and
// overall assumptions.
module axi_lite_write_arbiter #(
    parameter int ADDR_WIDTH = 8,
    parameter int DATA_WIDTH = 32,
    parameter int STRB_WIDTH = DATA_WIDTH / 8
) (
    input logic clk,
    input logic rst_n,

    // Input 0
    input  logic                  s0_req,
    input  logic [ADDR_WIDTH-1:0] s0_awaddr,
    input  logic [           2:0] s0_awprot,
    input  logic                  s0_wvalid,
    input  logic [DATA_WIDTH-1:0] s0_wdata,
    input  logic [STRB_WIDTH-1:0] s0_wstrb,
    input  logic                  s0_bready,
    output logic                  s0_awready,
    output logic                  s0_wready,
    output logic                  s0_bvalid,
    output logic [           1:0] s0_bresp,

    // Input 1
    input  logic                  s1_req,
    input  logic [ADDR_WIDTH-1:0] s1_awaddr,
    input  logic [           2:0] s1_awprot,
    input  logic                  s1_wvalid,
    input  logic [DATA_WIDTH-1:0] s1_wdata,
    input  logic [STRB_WIDTH-1:0] s1_wstrb,
    input  logic                  s1_bready,
    output logic                  s1_awready,
    output logic                  s1_wready,
    output logic                  s1_bvalid,
    output logic [           1:0] s1_bresp,

    // Output (towards the downstream slave)
    output logic [ADDR_WIDTH-1:0] m_awaddr,
    output logic [           2:0] m_awprot,
    output logic                  m_awvalid,
    input  logic                  m_awready,
    output logic [DATA_WIDTH-1:0] m_wdata,
    output logic [STRB_WIDTH-1:0] m_wstrb,
    output logic                  m_wvalid,
    input  logic                  m_wready,
    input  logic [           1:0] m_bresp,
    input  logic                  m_bvalid,
    output logic                  m_bready
);

  typedef enum logic [1:0] {
    IDLE,
    XFER,
    RESP
  } state_e;

  state_e state, state_nxt;
  logic sel, sel_nxt;  // 0 -> serving input 0, 1 -> serving input 1
  logic aw_done, aw_done_nxt;
  logic w_done, w_done_nxt;
  logic rr_prefer1, rr_prefer1_nxt;  // round-robin: who wins the next tie

  always_comb begin
    state_nxt = state;
    sel_nxt = sel;
    aw_done_nxt = aw_done;
    w_done_nxt = w_done;
    rr_prefer1_nxt = rr_prefer1;

    case (state)
      IDLE: begin
        aw_done_nxt = 1'b0;
        w_done_nxt  = 1'b0;
        if (s0_req && s1_req) begin
          sel_nxt        = rr_prefer1;
          rr_prefer1_nxt = ~rr_prefer1;  // flip so the loser wins the next tie
          state_nxt      = XFER;
        end else if (s0_req) begin
          sel_nxt   = 1'b0;
          state_nxt = XFER;
        end else if (s1_req) begin
          sel_nxt   = 1'b1;
          state_nxt = XFER;
        end
      end

      XFER: begin
        if (m_awvalid && m_awready) aw_done_nxt = 1'b1;
        if (m_wvalid && m_wready) w_done_nxt = 1'b1;
        if (aw_done_nxt && w_done_nxt) state_nxt = RESP;
      end

      RESP: begin
        if (m_bvalid && m_bready) begin
          state_nxt = IDLE;
        end
      end

      default: state_nxt = IDLE;
    endcase
  end

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state <= IDLE;
      sel <= 1'b0;
      aw_done <= 1'b0;
      w_done <= 1'b0;
      rr_prefer1 <= 1'b0;
    end else begin
      state <= state_nxt;
      sel <= sel_nxt;
      aw_done <= aw_done_nxt;
      w_done <= w_done_nxt;
      rr_prefer1 <= rr_prefer1_nxt;
    end
  end

  wire owns0 = (state != IDLE) && !sel;
  wire owns1 = (state != IDLE) && sel;

  // `req` already implies "still the right destination", so it's safe to
  // reuse it (rather than a separate awvalid) to gate m_awvalid here.
  assign m_awaddr  = sel ? s1_awaddr : s0_awaddr;
  assign m_awprot  = sel ? s1_awprot : s0_awprot;
  assign m_awvalid = (state == XFER) && !aw_done && (sel ? s1_req : s0_req);
  assign m_wdata    = sel ? s1_wdata : s0_wdata;
  assign m_wstrb    = sel ? s1_wstrb : s0_wstrb;
  assign m_wvalid   = (state == XFER) && !w_done && (sel ? s1_wvalid : s0_wvalid);
  assign m_bready   = (state == RESP) && (sel ? s1_bready : s0_bready);

  assign s0_awready = owns0 ? m_awready : 1'b0;
  assign s1_awready = owns1 ? m_awready : 1'b0;
  assign s0_wready  = owns0 ? m_wready : 1'b0;
  assign s1_wready  = owns1 ? m_wready : 1'b0;
  assign s0_bvalid  = (owns0 && state == RESP) ? m_bvalid : 1'b0;
  assign s1_bvalid  = (owns1 && state == RESP) ? m_bvalid : 1'b0;
  assign s0_bresp   = m_bresp;  // only meaningful while s0_bvalid is asserted
  assign s1_bresp   = m_bresp;  // only meaningful while s1_bvalid is asserted

endmodule
