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

/** "2021-03-14" → "Mar 14, 2021" (kept in UTC so the date never shifts). */
export function formatDate(isoDate: string): string {
  return new Date(`${isoDate}T00:00:00Z`).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
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

  return new Date(isoTimestamp).toLocaleDateString();
}
