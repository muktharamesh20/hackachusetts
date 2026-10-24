// Deep imports from the qrcode package (core + SVG renderer, no Node deps).
declare module "qrcode/lib/core/qrcode" {
  const QRCodeCore: { create(text: string, options?: { errorCorrectionLevel?: "L" | "M" | "Q" | "H" }): unknown };
  export default QRCodeCore;
}
declare module "qrcode/lib/renderer/svg-tag" {
  const SvgRenderer: {
    render(qrData: unknown, options?: { margin?: number; color?: { dark?: string; light?: string } }): string;
  };
  export default SvgRenderer;
}
