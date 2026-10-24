import { TextStyle } from "react-native";
import { Colors } from "./colors";

/** Font family names registered in app/_layout.tsx via useFonts. */
export const Fonts = {
  display: "Fraunces_700Bold",
  displayHeavy: "Fraunces_800ExtraBold",
  body: "Nunito_400Regular",
  bodySemi: "Nunito_600SemiBold",
  bodyBold: "Nunito_700Bold",
  bodyHeavy: "Nunito_800ExtraBold",
};

export const Type: Record<string, TextStyle> = {
  logo: { fontFamily: Fonts.displayHeavy, fontSize: 30, color: Colors.text, letterSpacing: -0.5 },
  h1: { fontFamily: Fonts.displayHeavy, fontSize: 28, color: Colors.text, lineHeight: 33 },
  h2: { fontFamily: Fonts.display, fontSize: 21, color: Colors.text },
  h3: { fontFamily: Fonts.bodyHeavy, fontSize: 16, color: Colors.text },
  body: { fontFamily: Fonts.body, fontSize: 15, color: Colors.text, lineHeight: 21 },
  bodySemi: { fontFamily: Fonts.bodySemi, fontSize: 15, color: Colors.text },
  muted: { fontFamily: Fonts.body, fontSize: 13, color: Colors.textMuted, lineHeight: 18 },
  stat: { fontFamily: Fonts.displayHeavy, fontSize: 30, color: Colors.text },
  label: { fontFamily: Fonts.bodyBold, fontSize: 12, color: Colors.textMuted },
};

export const Radii = { card: 20, button: 16, pill: 999 };
export const Space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32, gutter: 20 };

export const Shadow = {
  shadowColor: "#4A3426",
  shadowOpacity: 0.08,
  shadowRadius: 12,
  shadowOffset: { width: 0, height: 4 },
  elevation: 2,
};
