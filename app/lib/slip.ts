import * as MailComposer from "expo-mail-composer";
import * as Print from "expo-print";
import * as Sharing from "expo-sharing";
import { supabase } from "./supabase";
// Core + SVG renderer only: the package's main entry pulls in Node-only modules.
import QRCodeCore from "qrcode/lib/core/qrcode";
import SvgRenderer from "qrcode/lib/renderer/svg-tag";

/** QR payload staff Scan recognizes as a donor's bag. */
export const SLIP_PREFIX = "STASH-DROP|";
export const slipCode = (batchId: string) => `${SLIP_PREFIX}${batchId}`;
export const parseSlipCode = (code: string) => (code.startsWith(SLIP_PREFIX) ? code.slice(SLIP_PREFIX.length) : null);

export type SlipItem = { name: string; quantity: number; expirationDate: string | null };
export type Slip = {
  batchId: string;
  pantryName: string;
  pantryAddress: string;
  donorName: string;
  items: SlipItem[];
  createdAt: Date;
};

const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

function slipHtml(slip: Slip): string {
  const qr = SvgRenderer.render(QRCodeCore.create(slipCode(slip.batchId), { errorCorrectionLevel: "M" }), {
    margin: 1,
    color: { dark: "#3E2A1E", light: "#FFFFFF" },
  });
  const units = slip.items.reduce((n, i) => n + i.quantity, 0);
  const rows = slip.items
    .map(
      (i) => `<tr><td class="qty">${i.quantity}</td><td>${esc(i.name)}</td><td class="exp">${
        i.expirationDate ? esc(i.expirationDate) : "—"
      }</td></tr>`,
    )
    .join("");
  return `<!doctype html><html><head><meta charset="utf-8" />
<style>
  @page { margin: 36px; }
  body { font-family: -apple-system, Helvetica, Arial, sans-serif; color: #3E2A1E; }
  .top { display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; }
  h1 { font-family: Georgia, serif; font-size: 34px; margin: 0 0 4px; }
  .muted { color: #8C7565; font-size: 14px; margin: 2px 0; }
  .qr { width: 190px; height: 190px; border: 3px solid #3E2A1E; border-radius: 16px; padding: 8px; }
  .qr svg { width: 100%; height: 100%; }
  .box { background: #FBF5EA; border-radius: 14px; padding: 14px 18px; margin: 22px 0; font-size: 15px; }
  table { width: 100%; border-collapse: collapse; font-size: 15px; }
  th { text-align: left; color: #8C7565; font-size: 12px; text-transform: uppercase; letter-spacing: .5px; padding: 6px 0; border-bottom: 2px solid #EADFCC; }
  td { padding: 9px 0; border-bottom: 1px solid #EADFCC; }
  .qty { width: 48px; font-weight: 700; }
  .exp { width: 120px; color: #8C7565; }
  .foot { margin-top: 26px; font-size: 12px; color: #8C7565; }
</style></head><body>
  <div class="top">
    <div>
      <h1>Stash drop-off</h1>
      <p class="muted"><b>${esc(slip.pantryName)}</b></p>
      <p class="muted">${esc(slip.pantryAddress)}</p>
      <p class="muted">From ${esc(slip.donorName)} · ${slip.createdAt.toLocaleDateString()}</p>
      <p class="muted">${units} item${units === 1 ? "" : "s"}</p>
    </div>
    <div class="qr">${qr}</div>
  </div>
  <div class="box"><b>Volunteers:</b> scan this code with the Stash app (Pantry → Scan) to check this box in.
  Everything below is already entered.</div>
  <table><thead><tr><th>Qty</th><th>Item</th><th>Expires</th></tr></thead><tbody>${rows}</tbody></table>
  <p class="foot">Bag ${esc(slip.batchId.slice(0, 8))} · Thank you for supporting your neighbors.</p>
</body></html>`;
}

/** Render the slip to a PDF file and return its local URI. */
export async function makeSlipPdf(slip: Slip): Promise<string> {
  const { uri } = await Print.printToFileAsync({ html: slipHtml(slip) });
  return uri;
}

/**
 * Email the slip to the signed-in donor from Supabase (Edge Function `send-slip` via Resend).
 * Returns the address it went to, or throws so callers can fall back to the Mail app.
 */
export async function sendSlipEmail(batchId: string): Promise<string> {
  const { data, error } = await supabase.functions.invoke("send-slip", { body: { batchId } });
  if (error) throw new Error((await error.context?.json?.().catch(() => null))?.error ?? error.message);
  if (!data?.ok) throw new Error(data?.error ?? "Email failed");
  return data.to as string;
}

/** Open an email to the donor with the slip attached (falls back to the share sheet). */
export async function emailSlip(slip: Slip, to: string | undefined): Promise<void> {
  const uri = await makeSlipPdf(slip);
  if (await MailComposer.isAvailableAsync()) {
    await MailComposer.composeAsync({
      recipients: to ? [to] : [],
      subject: `Your Stash drop-off slip for ${slip.pantryName}`,
      body:
        `Thanks for donating!\n\nPrint the attached slip and put it in your box when you drop it off at ` +
        `${slip.pantryName}. Volunteers scan the QR code to check everything in.\n`,
      attachments: [uri],
    });
  } else {
    await Sharing.shareAsync(uri, { mimeType: "application/pdf", dialogTitle: "Drop-off slip" });
  }
}

/** Send the slip straight to AirPrint. */
export async function printSlip(slip: Slip): Promise<void> {
  await Print.printAsync({ html: slipHtml(slip) });
}
