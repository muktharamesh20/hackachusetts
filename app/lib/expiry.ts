/**
 * Find an expiration date in text read off a package (see modules/text-reader).
 * Handles the common US/EU print styles, e.g. "EXP 04/2028", "BEST BY 2027-08-20",
 * "BB 12 JAN 2027", "USE BY 01/15/27", "12JAN27". Prefers a date next to an
 * expiry keyword; ignores dates too far in the past or future to be an expiry.
 */
const MONTHS: Record<string, number> = {
  JAN: 1, FEB: 2, MAR: 3, APR: 4, MAY: 5, JUN: 6, JUL: 7, AUG: 8, SEP: 9, SEPT: 9, OCT: 10, NOV: 11, DEC: 12,
};
const KEYWORDS = /\b(EXP(IRES|IRY|IRATION)?|BEST\s*(BY|BEFORE|IF\s+USED\s+BY)|BB|BBE|USE\s*BY|SELL\s*BY|ENJOY\s*BY)\b/;

type Found = { iso: string; keyed: boolean };

const pad = (n: number) => String(n).padStart(2, "0");
const lastDay = (y: number, m: number) => new Date(y, m, 0).getDate();
const year4 = (y: number) => (y < 100 ? 2000 + y : y);

function toIso(y: number, m: number, d: number | null): string | null {
  y = year4(y);
  if (m < 1 || m > 12) return null;
  const day = d ?? lastDay(y, m); // month-only dates expire at month end
  if (day < 1 || day > lastDay(y, m)) return null;
  return `${y}-${pad(m)}-${pad(day)}`;
}

function datesIn(text: string): string[] {
  const t = text.toUpperCase().replace(/[.,]/g, " ");
  const out: (string | null)[] = [];
  let m: RegExpExecArray | null;
  const each = (re: RegExp, f: (m: RegExpExecArray) => string | null) => {
    re.lastIndex = 0;
    while ((m = re.exec(t))) out.push(f(m));
  };
  // 2027-08-20, 2027/08/20
  each(/\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b/g, (m) => toIso(+m[1], +m[2], +m[3]));
  // 08/20/2027, 08-20-27 (US month first)
  each(/\b(\d{1,2})[-/](\d{1,2})[-/](\d{2}|20\d{2})\b/g, (m) => toIso(+m[3], +m[1], +m[2]) ?? toIso(+m[3], +m[2], +m[1]));
  // 04/2028, 04/28 (month/year)
  each(/\b(\d{1,2})[-/](20\d{2}|\d{2})\b(?![-/]\d)/g, (m) => toIso(+m[2], +m[1], null));
  // 12 JAN 2027, 12JAN27, 12-JAN-2027
  each(/\b(\d{1,2})\s*-?\s*(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEPT?|OCT|NOV|DEC)[A-Z]*\s*-?\s*(20\d{2}|\d{2})\b/g, (m) =>
    toIso(+m[3], MONTHS[m[2]], +m[1]),
  );
  // JAN 12 2027, JAN 2027
  each(/\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEPT?|OCT|NOV|DEC)[A-Z]*\s+(\d{1,2})?\s*(20\d{2})\b/g, (m) =>
    toIso(+m[3], MONTHS[m[1]], m[2] ? +m[2] : null),
  );
  const dates = out.filter((d): d is string => Boolean(d));
  // "12 JAN 2027" also matches "JAN 2027": drop month-only (month-end) dates
  // when the same text has an exact day in that month.
  return dates.filter((d) => {
    const ym = d.slice(0, 7);
    const monthEnd = d.slice(8) === String(lastDay(+d.slice(0, 4), +d.slice(5, 7)));
    return !monthEnd || !dates.some((o) => o !== d && o.startsWith(ym));
  });
}

function plausible(iso: string, today = new Date()): boolean {
  const t = new Date(iso + "T12:00:00").getTime();
  const now = today.getTime();
  return t > now - 365 * 86400000 && t < now + 6 * 365 * 86400000;
}

export function findExpiry(lines: string[]): string | null {
  const found: Found[] = [];
  lines.forEach((line, i) => {
    const keyed = KEYWORDS.test(line.toUpperCase()) || (i > 0 && KEYWORDS.test(lines[i - 1].toUpperCase()));
    for (const iso of datesIn(line)) if (plausible(iso)) found.push({ iso, keyed });
  });
  if (!found.length) return null;
  const keyed = found.filter((f) => f.keyed);
  // Several candidates: the latest one is usually the expiry (vs. a pack date).
  const pick = (keyed.length ? keyed : found).map((f) => f.iso).sort();
  return pick[pick.length - 1];
}

/** today + days, as YYYY-MM-DD. */
export function addDays(days: number, from = new Date()): string {
  const d = new Date(from.getFullYear(), from.getMonth(), from.getDate() + days);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
