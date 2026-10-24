/** Stash palette: warm & cozy (see design spec). */
export const Colors = {
  bg: "#FBF5EA",
  card: "#FFFDF8",
  cardAlt: "#F6EEDF",
  line: "#EADFCC",

  tomato: "#E2553D",
  tomatoDark: "#B93F2B",
  tomatoSoft: "#FBE3DC",
  mustard: "#E8B341",
  mustardSoft: "#FBEFCF",
  olive: "#6E9A3A",
  oliveDark: "#557A2B",
  oliveSoft: "#E6EFD6",
  sky: "#4F8FAE",
  skyDark: "#3B7491",
  skySoft: "#DDEBF1",

  text: "#3E2A1E",
  textMuted: "#8C7565",
  white: "#FFFFFF",
  danger: "#D6453B",

  // Legacy aliases used by older screens.
  primary: "#E2553D",
  primaryDark: "#B93F2B",
  accent: "#E8B341",
  border: "#EADFCC",
};

export type ViewMode = "pantry" | "neighbor" | "donor";

/** Accent per view: matches the active switcher pill + primary buttons. */
export const ModeColors: Record<ViewMode, { main: string; dark: string; soft: string }> = {
  pantry: { main: Colors.tomato, dark: Colors.tomatoDark, soft: Colors.tomatoSoft },
  neighbor: { main: Colors.sky, dark: Colors.skyDark, soft: Colors.skySoft },
  donor: { main: Colors.olive, dark: Colors.oliveDark, soft: Colors.oliveSoft },
};
