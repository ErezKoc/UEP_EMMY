/**
 * The locale every date in this app is formatted in.
 *
 * Not the reader's. Every formatter here used to pass `undefined`, which means
 * "use the browser's locale" — so on a Turkish Windows machine the interface
 * rendered "23 Ağustos 2026" inside sentences written in English, and the
 * calendar put a Turkish month heading directly above hard-coded English
 * weekday columns. Half-translating an interface reads as a bug in every
 * language it touches.
 *
 * `en-GB` rather than `en-US` for two reasons: the interface is written in
 * English, so the month names should be; and it is day-first, which matches
 * both the backend's own `%d %b %Y` output and what a reader used to
 * 23.08.2026 expects from the ordering.
 *
 * When this app is genuinely translated, this constant is the thing that
 * changes — and everything below follows, because nothing formats a date
 * without going through here.
 */
export const UI_LOCALE = "en-GB";

export function formatPercent(confidence: number): string {
  return `${Math.round(confidence * 100)}%`;
}

export function formatYearsRange(minYears: number, maxYears: number): string {
  const fmt = (value: number) =>
    Number.isInteger(value) ? value.toString() : value.toFixed(1);
  if (minYears === 0) return `under ${fmt(maxYears)} yrs`;
  return `${fmt(minYears)}–${fmt(maxYears)} yrs`;
}

export function capitalize(value: string): string {
  return value.length === 0 ? value : value[0].toUpperCase() + value.slice(1);
}

/** "2021-03-14" → "14 Mar 2021" (kept in UTC so the date never shifts). */
export function formatDate(isoDate: string): string {
  return new Date(`${isoDate}T00:00:00Z`).toLocaleDateString(UI_LOCALE, {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

/** "2026-08-24T09:30:00Z" → "24 Aug 2026, 09:30". For stored timestamps. */
export function formatDateTime(isoTimestamp: string): string {
  return new Date(isoTimestamp).toLocaleString(UI_LOCALE, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** "24/08/2026". For places that want the compact numeric form. */
export function formatShortDate(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  return date.toLocaleDateString(UI_LOCALE);
}

/** "09:30". Clock time only, still on the app's locale rather than the reader's. */
export function formatTime(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  return date.toLocaleTimeString(UI_LOCALE, { hour: "2-digit", minute: "2-digit" });
}

/** "August 2026". The calendar's month heading. */
export function formatMonthYear(date: Date): string {
  return date.toLocaleDateString(UI_LOCALE, { month: "long", year: "numeric" });
}

/** Age from a birth date: "5 years", "1 year 3 months", "6 months", "3 weeks". */
export function formatAge(isoBirthDate: string): string {
  const birth = new Date(`${isoBirthDate}T00:00:00Z`);
  const now = new Date();
  let months =
    (now.getUTCFullYear() - birth.getUTCFullYear()) * 12 +
    (now.getUTCMonth() - birth.getUTCMonth());
  if (now.getUTCDate() < birth.getUTCDate()) months -= 1;

  if (months < 0) return "not born yet";
  if (months === 0) {
    const weeks = Math.floor((now.getTime() - birth.getTime()) / (7 * 24 * 3600 * 1000));
    return weeks <= 1 ? "newborn" : `${weeks} weeks`;
  }
  const years = Math.floor(months / 12);
  const rest = months % 12;
  const yearPart = years > 0 ? `${years} ${years === 1 ? "year" : "years"}` : "";
  const monthPart = rest > 0 ? `${rest} ${rest === 1 ? "month" : "months"}` : "";
  return [yearPart, monthPart].filter(Boolean).join(" ") || "under a month";
}

export function formatRelativeTime(isoTimestamp: string): string {
  const elapsedMs = Date.now() - new Date(isoTimestamp).getTime();
  const minutes = Math.floor(elapsedMs / 60_000);

  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;

  return formatShortDate(isoTimestamp);
}
