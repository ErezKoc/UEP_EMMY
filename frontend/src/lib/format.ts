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
