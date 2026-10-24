import { ImageSourcePropType } from "react-native";

/**
 * Generated illustrations, keyed by asset name (see the design spec's asset list).
 * Until an image exists, <Art> renders a labeled placeholder in its slot.
 * To add one: drop the PNG in assets/images/ and register it here, e.g.
 *   "hazel-wave": require("@/assets/images/hazel-wave.png"),
 */
export const ART: Record<string, ImageSourcePropType> = {
  "cat-baby": require("@/assets/images/cat-baby.png"),
  "cat-cooking": require("@/assets/images/cat-cooking.png"),
  "cat-family": require("@/assets/images/cat-family.png"),
  "cat-fruit-veg": require("@/assets/images/cat-fruit-veg.png"),
  "cat-grains": require("@/assets/images/cat-grains.png"),
  "cat-household": require("@/assets/images/cat-household.png"),
  "cat-personal-care": require("@/assets/images/cat-personal-care.png"),
  "cat-protein": require("@/assets/images/cat-protein.png"),
  "hazel-acorn-hug": require("@/assets/images/hazel-acorn-hug.png"),
  "hazel-cheer": require("@/assets/images/hazel-cheer.png"),
  "hazel-heart": require("@/assets/images/hazel-heart.png"),
  "hazel-robot-hat": require("@/assets/images/hazel-robot-hat.png"),
  "hazel-sleepy": require("@/assets/images/hazel-sleepy.png"),
  "hazel-wave": require("@/assets/images/hazel-wave.png"),
  "hazel-worried": require("@/assets/images/hazel-worried.png"),
  "illus-donate-food": require("@/assets/images/illus-donate-food.png"),
  "illus-give-money": require("@/assets/images/illus-give-money.png"),
  "illus-megaphone": require("@/assets/images/illus-megaphone.png"),
  "illus-pantry-storefront": require("@/assets/images/illus-pantry-storefront.png"),
  "illus-rescue-bag": require("@/assets/images/illus-rescue-bag.png"),
  "illus-robot-arm": require("@/assets/images/illus-robot-arm.png"),
  "illus-scan": require("@/assets/images/illus-scan.png"),
  "item-applesauce": require("@/assets/images/item-applesauce.png"),
  "item-baby-food": require("@/assets/images/item-baby-food.png"),
  "item-brown-rice": require("@/assets/images/item-brown-rice.png"),
  "item-canned-beans": require("@/assets/images/item-canned-beans.png"),
  "item-canned-chicken": require("@/assets/images/item-canned-chicken.png"),
  "item-canned-peaches": require("@/assets/images/item-canned-peaches.png"),
  "item-canned-tuna": require("@/assets/images/item-canned-tuna.png"),
  "item-canned-veg": require("@/assets/images/item-canned-veg.png"),
  "item-cereal": require("@/assets/images/item-cereal.png"),
  "item-crackers": require("@/assets/images/item-crackers.png"),
  "item-detergent": require("@/assets/images/item-detergent.png"),
  "item-diapers": require("@/assets/images/item-diapers.png"),
  "item-feminine": require("@/assets/images/item-feminine.png"),
  "item-flour": require("@/assets/images/item-flour.png"),
  "item-formula": require("@/assets/images/item-formula.png"),
  "item-granola-bars": require("@/assets/images/item-granola-bars.png"),
  "item-juice": require("@/assets/images/item-juice.png"),
  "item-lentils": require("@/assets/images/item-lentils.png"),
  "item-oats": require("@/assets/images/item-oats.png"),
  "item-olive-oil": require("@/assets/images/item-olive-oil.png"),
  "item-pancake-mix": require("@/assets/images/item-pancake-mix.png"),
  "item-pasta": require("@/assets/images/item-pasta.png"),
  "item-peanut-butter": require("@/assets/images/item-peanut-butter.png"),
  "item-shampoo": require("@/assets/images/item-shampoo.png"),
  "item-soap": require("@/assets/images/item-soap.png"),
  "item-spices": require("@/assets/images/item-spices.png"),
  "item-toilet-paper": require("@/assets/images/item-toilet-paper.png"),
  "item-toothpaste": require("@/assets/images/item-toothpaste.png"),
  "item-uht-milk": require("@/assets/images/item-uht-milk.png"),
  "onboard-donor": require("@/assets/images/onboard-donor.png"),
  "onboard-neighbor": require("@/assets/images/onboard-neighbor.png"),
  "onboard-pantry": require("@/assets/images/onboard-pantry.png"),
  "pantry-lakeside": require("@/assets/images/pantry-lakeside.jpg"),
  "pantry-maple-grove": require("@/assets/images/pantry-maple-grove.jpg"),
  "pantry-riverside": require("@/assets/images/pantry-riverside.jpg"),
};

// Items we can't identify reuse Hazel's "hmm?" pose.
ART["item-unknown"] = ART["hazel-worried"];

const BUCKET_URL = `${(process.env.EXPO_PUBLIC_SUPABASE_URL ?? "").trim()}/storage/v1/object/public/art/v1`;

/** Bundled image if we ship it, otherwise the copy in Supabase Storage (bucket "art", folder v1). */
export function artSource(name: string): ImageSourcePropType | null {
  if (ART[name]) return ART[name];
  if (!name || !BUCKET_URL.startsWith("http")) return null;
  return { uri: `${BUCKET_URL}/${name}.png` };
}
