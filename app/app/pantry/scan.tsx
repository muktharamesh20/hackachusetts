import { ScanFlow } from "@/components/ScanFlow";
import { useStaffPantryId } from "@/context/ProfileContext";
import { logItem } from "@/lib/stash";

/** Staff scan: each item goes straight into this pantry's stock as a new lot. */
export default function Scan() {
  const pantryId = useStaffPantryId();
  return (
    <ScanFlow
      pantryId={pantryId}
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
