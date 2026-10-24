// AXI4-Lite 2x2 router: 2 slave ports (s0, s1) accept requests from masters,
// 2 master ports (m0, m1) forward them to downstream slaves. Destination is
// chosen by the top address bit: addr[ADDR_WIDTH-1]==0 -> m0, ==1 -> m1.
// Write and read are arbitrated independently (see axi_lite_write_arbiter /
// axi_lite_read_arbiter), one instance of each per output.
//
// Simplifying assumptions (fine for a router/arbitration verification spike,
// not a general-purpose interconnect):
//  - Each input has at most one outstanding write and one outstanding read
//    at a time. No per-master pipelining/reordering support is needed.
//  - No address translation: the full address is forwarded downstream
//    as-is, only the top bit is used to steer.
module axi_lite_router #(
    parameter int ADDR_WIDTH = 8,
    parameter int DATA_WIDTH = 32,
    parameter int STRB_WIDTH = DATA_WIDTH / 8
) (
    input logic clk,
    input logic rst_n,

    // Slave port 0 (from master 0)
    input  logic [ADDR_WIDTH-1:0] s0_awaddr,
    input  logic [           2:0] s0_awprot,
    input  logic                  s0_awvalid,
    output logic                  s0_awready,
    input  logic [DATA_WIDTH-1:0] s0_wdata,
    input  logic [STRB_WIDTH-1:0] s0_wstrb,
    input  logic                  s0_wvalid,
    output logic                  s0_wready,
    output logic [           1:0] s0_bresp,
    output logic                  s0_bvalid,
    input  logic                  s0_bready,
    input  logic [ADDR_WIDTH-1:0] s0_araddr,
    input  logic [           2:0] s0_arprot,
    input  logic                  s0_arvalid,
    output logic                  s0_arready,
    output logic [DATA_WIDTH-1:0] s0_rdata,
    output logic [           1:0] s0_rresp,
    output logic                  s0_rvalid,
    input  logic                  s0_rready,

    // Slave port 1 (from master 1)
    input  logic [ADDR_WIDTH-1:0] s1_awaddr,
    input  logic [           2:0] s1_awprot,
    input  logic                  s1_awvalid,
    output logic                  s1_awready,
    input  logic [DATA_WIDTH-1:0] s1_wdata,
    input  logic [STRB_WIDTH-1:0] s1_wstrb,
    input  logic                  s1_wvalid,
    output logic                  s1_wready,
    output logic [           1:0] s1_bresp,
    output logic                  s1_bvalid,
    input  logic                  s1_bready,
    input  logic [ADDR_WIDTH-1:0] s1_araddr,
    input  logic [           2:0] s1_arprot,
    input  logic                  s1_arvalid,
    output logic                  s1_arready,
    output logic [DATA_WIDTH-1:0] s1_rdata,
    output logic [           1:0] s1_rresp,
    output logic                  s1_rvalid,
    input  logic                  s1_rready,

    // Master port 0 (to slave 0)
    output logic [ADDR_WIDTH-1:0] m0_awaddr,
    output logic [           2:0] m0_awprot,
    output logic                  m0_awvalid,
    input  logic                  m0_awready,
    output logic [DATA_WIDTH-1:0] m0_wdata,
    output logic [STRB_WIDTH-1:0] m0_wstrb,
    output logic                  m0_wvalid,
    input  logic                  m0_wready,
    input  logic [           1:0] m0_bresp,
    input  logic                  m0_bvalid,
    output logic                  m0_bready,
    output logic [ADDR_WIDTH-1:0] m0_araddr,
    output logic [           2:0] m0_arprot,
    output logic                  m0_arvalid,
    input  logic                  m0_arready,
    input  logic [DATA_WIDTH-1:0] m0_rdata,
    input  logic [           1:0] m0_rresp,
    input  logic                  m0_rvalid,
    output logic                  m0_rready,

    // Master port 1 (to slave 1)
    output logic [ADDR_WIDTH-1:0] m1_awaddr,
    output logic [           2:0] m1_awprot,
    output logic                  m1_awvalid,
    input  logic                  m1_awready,
    output logic [DATA_WIDTH-1:0] m1_wdata,
    output logic [STRB_WIDTH-1:0] m1_wstrb,
    output logic                  m1_wvalid,
    input  logic                  m1_wready,
    input  logic [           1:0] m1_bresp,
    input  logic                  m1_bvalid,
    output logic                  m1_bready,
    output logic [ADDR_WIDTH-1:0] m1_araddr,
    output logic [           2:0] m1_arprot,
    output logic                  m1_arvalid,
    input  logic                  m1_arready,
    input  logic [DATA_WIDTH-1:0] m1_rdata,
    input  logic [           1:0] m1_rresp,
    input  logic                  m1_rvalid,
    output logic                  m1_rready
);

  // Destination decode: top address bit, 0 -> output 0, 1 -> output 1.
  wire s0_wr_req_m0 = s0_awvalid && !s0_awaddr[ADDR_WIDTH-1];
  wire s0_wr_req_m1 = s0_awvalid && s0_awaddr[ADDR_WIDTH-1];
  wire s1_wr_req_m0 = s1_awvalid && !s1_awaddr[ADDR_WIDTH-1];
  wire s1_wr_req_m1 = s1_awvalid && s1_awaddr[ADDR_WIDTH-1];

  wire s0_rd_req_m0 = s0_arvalid && !s0_araddr[ADDR_WIDTH-1];
  wire s0_rd_req_m1 = s0_arvalid && s0_araddr[ADDR_WIDTH-1];
  wire s1_rd_req_m0 = s1_arvalid && !s1_araddr[ADDR_WIDTH-1];
  wire s1_rd_req_m1 = s1_arvalid && s1_araddr[ADDR_WIDTH-1];

  // Per-output-arbiter contributions to each input's response signals.
  // Exactly one of the _m0 / _m1 variants can be active for a given input
  // at a time (an input's destination is single-valued at any moment), so
  // combining them with OR/mux below is safe.
  logic s0_awready_m0, s0_wready_m0, s0_bvalid_m0;
  logic [1:0] s0_bresp_m0;
  logic s1_awready_m0, s1_wready_m0, s1_bvalid_m0;
  logic [1:0] s1_bresp_m0;
  logic s0_awready_m1, s0_wready_m1, s0_bvalid_m1;
  logic [1:0] s0_bresp_m1;
  logic s1_awready_m1, s1_wready_m1, s1_bvalid_m1;
  logic [1:0] s1_bresp_m1;

  axi_lite_write_arbiter #(
      .ADDR_WIDTH(ADDR_WIDTH),
      .DATA_WIDTH(DATA_WIDTH),
      .STRB_WIDTH(STRB_WIDTH)
  ) wr_arb_m0 (
      .clk    (clk),
      .rst_n  (rst_n),
      .s0_req (s0_wr_req_m0),
      .s0_awaddr(s0_awaddr),
      .s0_awprot(s0_awprot),
      .s0_wvalid(s0_wvalid),
      .s0_wdata(s0_wdata),
      .s0_wstrb(s0_wstrb),
      .s0_bready(s0_bready),
      .s0_awready(s0_awready_m0),
      .s0_wready(s0_wready_m0),
      .s0_bvalid(s0_bvalid_m0),
      .s0_bresp(s0_bresp_m0),
      .s1_req (s1_wr_req_m0),
      .s1_awaddr(s1_awaddr),
      .s1_awprot(s1_awprot),
      .s1_wvalid(s1_wvalid),
      .s1_wdata(s1_wdata),
      .s1_wstrb(s1_wstrb),
      .s1_bready(s1_bready),
      .s1_awready(s1_awready_m0),
      .s1_wready(s1_wready_m0),
      .s1_bvalid(s1_bvalid_m0),
      .s1_bresp(s1_bresp_m0),
      .m_awaddr(m0_awaddr),
      .m_awprot(m0_awprot),
      .m_awvalid(m0_awvalid),
      .m_awready(m0_awready),
      .m_wdata(m0_wdata),
      .m_wstrb(m0_wstrb),
      .m_wvalid(m0_wvalid),
      .m_wready(m0_wready),
      .m_bresp(m0_bresp),
      .m_bvalid(m0_bvalid),
      .m_bready(m0_bready)
  );

  axi_lite_write_arbiter #(
      .ADDR_WIDTH(ADDR_WIDTH),
      .DATA_WIDTH(DATA_WIDTH),
      .STRB_WIDTH(STRB_WIDTH)
  ) wr_arb_m1 (
      .clk    (clk),
      .rst_n  (rst_n),
      .s0_req (s0_wr_req_m1),
      .s0_awaddr(s0_awaddr),
      .s0_awprot(s0_awprot),
      .s0_wvalid(s0_wvalid),
      .s0_wdata(s0_wdata),
      .s0_wstrb(s0_wstrb),
      .s0_bready(s0_bready),
      .s0_awready(s0_awready_m1),
      .s0_wready(s0_wready_m1),
      .s0_bvalid(s0_bvalid_m1),
      .s0_bresp(s0_bresp_m1),
      .s1_req (s1_wr_req_m1),
      .s1_awaddr(s1_awaddr),
      .s1_awprot(s1_awprot),
      .s1_wvalid(s1_wvalid),
      .s1_wdata(s1_wdata),
      .s1_wstrb(s1_wstrb),
      .s1_bready(s1_bready),
      .s1_awready(s1_awready_m1),
      .s1_wready(s1_wready_m1),
      .s1_bvalid(s1_bvalid_m1),
      .s1_bresp(s1_bresp_m1),
      .m_awaddr(m1_awaddr),
      .m_awprot(m1_awprot),
      .m_awvalid(m1_awvalid),
      .m_awready(m1_awready),
      .m_wdata(m1_wdata),
      .m_wstrb(m1_wstrb),
      .m_wvalid(m1_wvalid),
      .m_wready(m1_wready),
      .m_bresp(m1_bresp),
      .m_bvalid(m1_bvalid),
      .m_bready(m1_bready)
  );

  assign s0_awready = s0_awready_m0 | s0_awready_m1;
  assign s0_wready  = s0_wready_m0 | s0_wready_m1;
  assign s0_bvalid  = s0_bvalid_m0 | s0_bvalid_m1;
  assign s0_bresp   = s0_bvalid_m0 ? s0_bresp_m0 : s0_bresp_m1;

  assign s1_awready = s1_awready_m0 | s1_awready_m1;
  assign s1_wready  = s1_wready_m0 | s1_wready_m1;
  assign s1_bvalid  = s1_bvalid_m0 | s1_bvalid_m1;
  assign s1_bresp   = s1_bvalid_m0 ? s1_bresp_m0 : s1_bresp_m1;

  // Same pattern for the read side.
  logic s0_arready_m0, s0_rvalid_m0;
  logic [DATA_WIDTH-1:0] s0_rdata_m0;
  logic [1:0] s0_rresp_m0;
  logic s1_arready_m0, s1_rvalid_m0;
  logic [DATA_WIDTH-1:0] s1_rdata_m0;
  logic [1:0] s1_rresp_m0;
  logic s0_arready_m1, s0_rvalid_m1;
  logic [DATA_WIDTH-1:0] s0_rdata_m1;
  logic [1:0] s0_rresp_m1;
  logic s1_arready_m1, s1_rvalid_m1;
  logic [DATA_WIDTH-1:0] s1_rdata_m1;
  logic [1:0] s1_rresp_m1;

  axi_lite_read_arbiter #(
      .ADDR_WIDTH(ADDR_WIDTH),
      .DATA_WIDTH(DATA_WIDTH)
  ) rd_arb_m0 (
      .clk    (clk),
      .rst_n  (rst_n),
      .s0_req (s0_rd_req_m0),
      .s0_araddr(s0_araddr),
      .s0_arprot(s0_arprot),
      .s0_rready(s0_rready),
      .s0_arready(s0_arready_m0),
      .s0_rvalid(s0_rvalid_m0),
      .s0_rdata(s0_rdata_m0),
      .s0_rresp(s0_rresp_m0),
      .s1_req (s1_rd_req_m0),
      .s1_araddr(s1_araddr),
      .s1_arprot(s1_arprot),
      .s1_rready(s1_rready),
      .s1_arready(s1_arready_m0),
      .s1_rvalid(s1_rvalid_m0),
      .s1_rdata(s1_rdata_m0),
      .s1_rresp(s1_rresp_m0),
      .m_araddr(m0_araddr),
      .m_arprot(m0_arprot),
      .m_arvalid(m0_arvalid),
      .m_arready(m0_arready),
      .m_rdata(m0_rdata),
      .m_rresp(m0_rresp),
      .m_rvalid(m0_rvalid),
      .m_rready(m0_rready)
  );

  axi_lite_read_arbiter #(
      .ADDR_WIDTH(ADDR_WIDTH),
      .DATA_WIDTH(DATA_WIDTH)
  ) rd_arb_m1 (
      .clk    (clk),
      .rst_n  (rst_n),
      .s0_req (s0_rd_req_m1),
      .s0_araddr(s0_araddr),
      .s0_arprot(s0_arprot),
      .s0_rready(s0_rready),
      .s0_arready(s0_arready_m1),
      .s0_rvalid(s0_rvalid_m1),
      .s0_rdata(s0_rdata_m1),
      .s0_rresp(s0_rresp_m1),
      .s1_req (s1_rd_req_m1),
      .s1_araddr(s1_araddr),
      .s1_arprot(s1_arprot),
      .s1_rready(s1_rready),
      .s1_arready(s1_arready_m1),
      .s1_rvalid(s1_rvalid_m1),
      .s1_rdata(s1_rdata_m1),
      .s1_rresp(s1_rresp_m1),
      .m_araddr(m1_araddr),
      .m_arprot(m1_arprot),
      .m_arvalid(m1_arvalid),
      .m_arready(m1_arready),
      .m_rdata(m1_rdata),
      .m_rresp(m1_rresp),
      .m_rvalid(m1_rvalid),
      .m_rready(m1_rready)
  );

  assign s0_arready = s0_arready_m0 | s0_arready_m1;
  assign s0_rvalid  = s0_rvalid_m0 | s0_rvalid_m1;
  assign s0_rdata   = s0_rvalid_m0 ? s0_rdata_m0 : s0_rdata_m1;
  assign s0_rresp   = s0_rvalid_m0 ? s0_rresp_m0 : s0_rresp_m1;

  assign s1_arready = s1_arready_m0 | s1_arready_m1;
  assign s1_rvalid  = s1_rvalid_m0 | s1_rvalid_m1;
  assign s1_rdata   = s1_rvalid_m0 ? s1_rdata_m0 : s1_rdata_m1;
  assign s1_rresp   = s1_rvalid_m0 ? s1_rresp_m0 : s1_rresp_m1;

endmodule
