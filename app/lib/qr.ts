import { CategoryKey } from "./categories";

/**
 * Parse the robot's QR label format (src/pantrysort/perception/qr_payload.py):
 *   PS1|sku=BEANS-BLK-CAN|exp=2027-04-12|cat=canned|cal=330|alg=none
 * Any other barcode (UPC/EAN) is returned as a plain code with no facts.
 * Product names/pictures come from the catalog_items table (see findCatalogItem).
 */
export type ScannedLabel = {
  code: string;
  sku: string | null;
  /** App category from the label's `cat` field, if printed. */
  category: CategoryKey | null;
  expirationDate: string | null;
};

const APP_CATEGORY: Record<string, CategoryKey> = {
  canned: "protein",
  dry_goods: "grains",
  bakery: "grains",
  produce: "fruit_veg",
  frozen: "fruit_veg",
  dairy: "family_kids",
  beverage: "drinks",
  snack: "family_kids",
  condiment: "cooking_basics",
  baby: "baby",
  non_food: "household",
  unknown: "unknown",
};

/** Mirror of pantrysort.inventory.models.app_category. */
export function appCategory(robotCategory: string, name = ""): CategoryKey {
  const n = name.toLowerCase();
  if (robotCategory === "condiment" && /peanut butter|almond butter|nut butter/.test(n)) return "protein";
  if (robotCategory === "non_food" && /toothpaste|toothbrush|soap|shampoo|conditioner|deodorant|body wash/.test(n)) {
    return "personal_care";
  }
  return APP_CATEGORY[robotCategory] ?? (robotCategory as CategoryKey);
}

export function parseLabel(code: string): ScannedLabel {
  if (!code.startsWith("PS1|")) {
    return { code, sku: null, category: null, expirationDate: null };
  }
  const fields = Object.fromEntries(
    code.split("|").slice(1).map((kv) => kv.split("=") as [string, string]),
  );
  const sku = fields.sku ?? null;
  return {
    code: sku ?? code,
    sku,
    category: fields.cat ? appCategory(fields.cat) : null,
    expirationDate: fields.exp ?? null,
  };
}
