import { useRouter } from "expo-router";
import { ScanFlow } from "@/components/ScanFlow";
import { useStaffPantryId } from "@/context/ProfileContext";
import { parseSlipCode } from "@/lib/slip";
import { logItem } from "@/lib/stash";

/** Staff scan: items go straight into stock as new lots; drop-off slips open the donor's bag. */
export default function Scan() {
  const pantryId = useStaffPantryId();
  const router = useRouter();
  return (
    <ScanFlow
      pantryId={pantryId}
      hint="Scan a barcode, QR label, or donor drop-off slip"
      // A donor's printed drop-off slip opens that bag for check-in.
      onCode={(code) => {
        const batch = parseSlipCode(code);
        if (batch) router.push(`/dropoffs/${batch}`);
        return Boolean(batch);
      }}
      submitLabel="Log new items"
      onSubmit={async (d) => {
        const item = await logItem({
          pantryId,
          name: d.name,
          category: d.category!,
          quantity: d.quantity,
          expirationDate: d.expirationDate || null,
          barcode: d.barcode,
        });
        const label = d.quantity > 1 ? `${item.name} (${d.quantity})` : item.name;
        return { title: "All stashed!", body: `${label} added to inventory.` };
      }}
    />
  );
}
