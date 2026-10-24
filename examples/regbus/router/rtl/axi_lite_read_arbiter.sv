// Round-robin 2:1 arbiter for one AXI4-Lite read channel pair (AR/R).
// Same grant/fairness policy as axi_lite_write_arbiter, without the AW/W
// pairing (a read is just AR then R).
module axi_lite_read_arbiter #(
    parameter int ADDR_WIDTH = 8,
    parameter int DATA_WIDTH = 32
) (
    input logic clk,
    input logic rst_n,

    // Input 0
    input  logic                  s0_req,
    input  logic [ADDR_WIDTH-1:0] s0_araddr,
    input  logic [           2:0] s0_arprot,
    input  logic                  s0_rready,
    output logic                  s0_arready,
    output logic                  s0_rvalid,
    output logic [DATA_WIDTH-1:0] s0_rdata,
    output logic [           1:0] s0_rresp,

    // Input 1
    input  logic                  s1_req,
    input  logic [ADDR_WIDTH-1:0] s1_araddr,
    input  logic [           2:0] s1_arprot,
    input  logic                  s1_rready,
    output logic                  s1_arready,
    output logic                  s1_rvalid,
    output logic [DATA_WIDTH-1:0] s1_rdata,
    output logic [           1:0] s1_rresp,

    // Output (towards the downstream slave)
    output logic [ADDR_WIDTH-1:0] m_araddr,
    output logic [           2:0] m_arprot,
    output logic                  m_arvalid,
    input  logic                  m_arready,
    input  logic [DATA_WIDTH-1:0] m_rdata,
    input  logic [           1:0] m_rresp,
    input  logic                  m_rvalid,
    output logic                  m_rready
);

  typedef enum logic [1:0] {
    IDLE,
    XFER,
    RESP
  } state_e;

  state_e state, state_nxt;
  logic sel, sel_nxt;
  logic rr_prefer1, rr_prefer1_nxt;

  always_comb begin
    state_nxt = state;
    sel_nxt = sel;
    rr_prefer1_nxt = rr_prefer1;

    case (state)
      IDLE: begin
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
        if (m_arvalid && m_arready) state_nxt = RESP;
      end

      RESP: begin
        if (m_rvalid && m_rready) begin
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
      rr_prefer1 <= 1'b0;
    end else begin
      state <= state_nxt;
      sel <= sel_nxt;
      rr_prefer1 <= rr_prefer1_nxt;
    end
  end

  wire owns0 = (state != IDLE) && !sel;
  wire owns1 = (state != IDLE) && sel;

  assign m_araddr  = sel ? s1_araddr : s0_araddr;
  assign m_arprot  = sel ? s1_arprot : s0_arprot;
  assign m_arvalid = (state == XFER) && (sel ? s1_req : s0_req);
  assign m_rready   = (state == RESP) && (sel ? s1_rready : s0_rready);

  assign s0_arready = owns0 ? m_arready : 1'b0;
  assign s1_arready = owns1 ? m_arready : 1'b0;
  assign s0_rvalid  = (owns0 && state == RESP) ? m_rvalid : 1'b0;
  assign s1_rvalid  = (owns1 && state == RESP) ? m_rvalid : 1'b0;
  assign s0_rdata   = m_rdata;  // only meaningful while s0_rvalid is asserted
  assign s1_rdata   = m_rdata;  // only meaningful while s1_rvalid is asserted
  assign s0_rresp   = m_rresp;
  assign s1_rresp   = m_rresp;

endmodule
