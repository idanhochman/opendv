// Small AXI4-Lite slave with six 32-bit registers (word index = addr[4:2]):
//
//   0x00 ID          RO   parameter ID; a write gets SLVERR
//   0x04 SCRATCH     RW   32 bits, byte strobes honoured
//   0x08 CTRL        RW   [7:0]
//   0x0C IRQ_RAISE   WO   writing 1s sets those IRQ_STATUS bits (test hook); reads 0
//   0x10 IRQ_STATUS  W1C  [7:0]
//   0x14 IRQ_EN      RW   [7:0]
//
// irq = |(IRQ_STATUS & IRQ_EN). Word indexes 6 and 7 are unmapped: reads
// return 0 and both reads and writes respond SLVERR. Address bits above
// [4:2] are ignored, so a window selected upstream (e.g. by the router's
// top address bit) aliases onto the same registers.
//
// One outstanding write and one outstanding read at a time. AW and W are
// accepted together, in the same cycle, once both are valid.
module axi_lite_regfile #(
    parameter int ADDR_WIDTH = 8,
    parameter logic [31:0] ID = 32'h5EF0_0001
) (
    input logic clk,
    input logic rst_n,

    input  logic [ADDR_WIDTH-1:0] s_awaddr,
    input  logic [           2:0] s_awprot,
    input  logic                  s_awvalid,
    output logic                  s_awready,
    input  logic [          31:0] s_wdata,
    input  logic [           3:0] s_wstrb,
    input  logic                  s_wvalid,
    output logic                  s_wready,
    output logic [           1:0] s_bresp,
    output logic                  s_bvalid,
    input  logic                  s_bready,
    input  logic [ADDR_WIDTH-1:0] s_araddr,
    input  logic [           2:0] s_arprot,
    input  logic                  s_arvalid,
    output logic                  s_arready,
    output logic [          31:0] s_rdata,
    output logic [           1:0] s_rresp,
    output logic                  s_rvalid,
    input  logic                  s_rready,

    output logic irq
);

  localparam logic [1:0] OKAY = 2'b00;
  localparam logic [1:0] SLVERR = 2'b10;

  logic [31:0] scratch;
  logic [7:0] ctrl, irq_status, irq_en;  // only [7:0] exist; they read back zero-extended

  assign irq = |(irq_status & irq_en);

  // Lanes of `new_val` whose strobe bit is set replace the same lanes of `old`.
  function automatic logic [31:0] merge(input logic [31:0] old, input logic [31:0] new_val,
                                        input logic [3:0] strb);
    for (int i = 0; i < 4; i++) merge[8*i+:8] = strb[i] ? new_val[8*i+:8] : old[8*i+:8];
  endfunction

  // -- write channel: AW and W accepted together, B held until bready ----
  wire wr_fire = s_awvalid && s_wvalid && !s_bvalid;
  assign s_awready = wr_fire;
  assign s_wready  = wr_fire;
  wire [2:0] widx = s_awaddr[4:2];
  wire [31:0] wr_scratch = merge(scratch, s_wdata, s_wstrb);
  wire [31:0] wr_ctrl = merge({24'h0, ctrl}, s_wdata, s_wstrb);
  wire [31:0] wr_irq_en = merge({24'h0, irq_en}, s_wdata, s_wstrb);
  wire [31:0] wr_lanes = merge(32'h0, s_wdata, s_wstrb);  // the written lanes, others 0

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      scratch    <= 32'h0;
      ctrl       <= 8'h0;
      irq_status <= 8'h0;
      irq_en     <= 8'h0;
      s_bvalid   <= 1'b0;
      s_bresp    <= OKAY;
    end else begin
      if (s_bvalid && s_bready) s_bvalid <= 1'b0;
      if (wr_fire) begin
        s_bvalid <= 1'b1;
        s_bresp  <= OKAY;
        case (widx)
          3'd1: scratch <= wr_scratch;
          3'd2: ctrl <= wr_ctrl[7:0];
          3'd3: irq_status <= irq_status | wr_lanes[7:0];
          3'd4: irq_status <= irq_status & ~wr_lanes[7:0];
          3'd5: irq_en <= wr_irq_en[7:0];
          default: s_bresp <= SLVERR;  // ID is read-only, 6 and 7 are unmapped
        endcase
      end
    end
  end

  // -- read channel ------------------------------------------------------
  wire rd_fire = s_arvalid && !s_rvalid;
  assign s_arready = rd_fire;
  wire [2:0] ridx = s_araddr[4:2];

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      s_rvalid <= 1'b0;
      s_rdata  <= 32'h0;
      s_rresp  <= OKAY;
    end else begin
      if (s_rvalid && s_rready) s_rvalid <= 1'b0;
      if (rd_fire) begin
        s_rvalid <= 1'b1;
        s_rresp  <= OKAY;
        case (ridx)
          3'd0: s_rdata <= ID;
          3'd1: s_rdata <= scratch;
          3'd2: s_rdata <= {24'h0, ctrl};
          3'd3: s_rdata <= 32'h0;
          3'd4: s_rdata <= {24'h0, irq_status};
          3'd5: s_rdata <= {24'h0, irq_en};
          default: begin
            s_rdata <= 32'h0;
            s_rresp <= SLVERR;
          end
        endcase
      end
    end
  end

endmodule
