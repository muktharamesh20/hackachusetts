import { requireOptionalNativeModule } from "expo-modules-core";

type TextReaderModule = { recognize(uri: string): Promise<string[]> };

const native = requireOptionalNativeModule<TextReaderModule>("TextReader");

/** Text lines in a photo (Apple Vision, on device). Empty if unavailable. */
export async function recognizeText(uri: string): Promise<string[]> {
  if (!native) return [];
  return native.recognize(uri);
}
