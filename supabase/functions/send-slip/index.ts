// Email a donor their drop-off slip (QR + item list) via Resend.
// POST { batchId } with the donor's Supabase session (Authorization: Bearer <jwt>).
// The bag is read with the caller's own token, so RLS only lets donors slip their own bags.
import { createClient } from "npm:@supabase/supabase-js@2.57.4";
import QRCode from "npm:qrcode@1.5.4";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });

const esc = (s: string) =>
  s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: "POST only" }, 405);

  const auth = req.headers.get("Authorization") ?? "";
  const supabase = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!, {
    global: { headers: { Authorization: auth } },
  });

  const { data: userData, error: userError } = await supabase.auth.getUser();
  const user = userData?.user;
  if (userError || !user?.email) return json({ error: "Sign in first" }, 401);

  const { batchId } = await req.json().catch(() => ({}));
  if (typeof batchId !== "string" || !batchId) return json({ error: "batchId required" }, 400);

  const { data: rows, error: bagError } = await supabase
    .from("dropoff_items")
    .select("name,quantity,expiration_date,pantry_id,donor_name,created_at")
    .eq("batch_id", batchId)
    .eq("donor_id", user.id)
    .order("id");
  if (bagError) return json({ error: bagError.message }, 500);
  if (!rows?.length) return json({ error: "Bag not found" }, 404);

  const { data: pantry } = await supabase
    .from("pantries")
    .select("name,address,city")
    .eq("id", rows[0].pantry_id)
    .single();
  const pantryName = pantry?.name ?? "the pantry";
  const pantryAddress = [pantry?.address, pantry?.city].filter(Boolean).join(", ");
  const donorName = rows[0].donor_name ?? user.email;
  const units = rows.reduce((n, r) => n + r.quantity, 0);
  const date = new Date(rows[0].created_at).toLocaleDateString("en-US");

  // Same payload staff Scan recognizes (app/lib/slip.ts SLIP_PREFIX).
  const qrPng: Uint8Array = await QRCode.toBuffer(`STASH-DROP|${batchId}`, {
    errorCorrectionLevel: "M",
    margin: 2,
    scale: 8,
  });
  let binary = "";
  qrPng.forEach((b) => (binary += String.fromCharCode(b)));
  const qrBase64 = btoa(binary);

  const itemRows = rows
    .map(
      (r) => `<tr>
        <td style="padding:9px 0;border-bottom:1px solid #EADFCC;font-weight:700;width:48px">${r.quantity}</td>
        <td style="padding:9px 0;border-bottom:1px solid #EADFCC">${esc(r.name)}</td>
        <td style="padding:9px 0;border-bottom:1px solid #EADFCC;color:#8C7565;width:120px">${r.expiration_date ?? "—"}</td>
      </tr>`,
    )
    .join("");

  const html = `<div style="font-family:-apple-system,Helvetica,Arial,sans-serif;color:#3E2A1E;max-width:640px;margin:0 auto;padding:24px;background:#FFFFFF">
  <h1 style="font-family:Georgia,serif;font-size:32px;margin:0 0 6px">Stash drop-off</h1>
  <p style="margin:2px 0;color:#8C7565;font-size:14px"><b>${esc(pantryName)}</b>${pantryAddress ? ` &middot; ${esc(pantryAddress)}` : ""}</p>
  <p style="margin:2px 0 16px;color:#8C7565;font-size:14px">From ${esc(donorName)} &middot; ${date} &middot; ${units} item${units === 1 ? "" : "s"}</p>
  <p style="margin:0 0 16px"><img src="cid:stash-qr" width="240" height="240" alt="Drop-off QR code" style="display:block;border:3px solid #3E2A1E;border-radius:16px"></p>
  <div style="background:#FBF5EA;border-radius:14px;padding:14px 18px;margin:0 0 22px;font-size:15px">
    <b>Print this and put it in your box.</b> Volunteers scan the code with the Stash app (Pantry &rarr; Scan) to check everything in.
  </div>
  <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:15px">
    <tr>
      <th align="left" style="color:#8C7565;font-size:12px;text-transform:uppercase;padding:6px 0;border-bottom:2px solid #EADFCC">Qty</th>
      <th align="left" style="color:#8C7565;font-size:12px;text-transform:uppercase;padding:6px 0;border-bottom:2px solid #EADFCC">Item</th>
      <th align="left" style="color:#8C7565;font-size:12px;text-transform:uppercase;padding:6px 0;border-bottom:2px solid #EADFCC">Expires</th>
    </tr>${itemRows}
  </table>
  <p style="margin-top:22px;font-size:12px;color:#8C7565">Bag ${esc(batchId.slice(0, 8))} &middot; Thank you for supporting your neighbors.</p>
</div>`;

  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${Deno.env.get("RESEND_API_KEY")}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      from: Deno.env.get("SLIP_FROM") ?? "Stash <onboarding@resend.dev>",
      to: [user.email],
      subject: `Your Stash drop-off slip for ${pantryName}`,
      html,
      attachments: [{ filename: "stash-dropoff-qr.png", content: qrBase64, content_id: "stash-qr" }],
    }),
  });
  const sent = await res.json().catch(() => ({}));
  if (!res.ok) return json({ error: sent?.message ?? "Email failed", detail: sent }, 502);
  return json({ ok: true, id: sent.id, to: user.email });
});
