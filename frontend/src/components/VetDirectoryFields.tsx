import { useEffect, useState } from "react";
import { getSpecialties } from "../api/client";
import { Input } from "./ui";
import type { CurrentUser, SpecialtyOption } from "../types";

const DAYS: Array<{ key: string; label: string }> = [
  { key: "mon", label: "Mon" },
  { key: "tue", label: "Tue" },
  { key: "wed", label: "Wed" },
  { key: "thu", label: "Thu" },
  { key: "fri", label: "Fri" },
  { key: "sat", label: "Sat" },
  { key: "sun", label: "Sun" },
];

export interface DirectoryFieldState {
  specialties: string[];
  feeMin: string;
  feeMax: string;
  feeCurrency: string;
  latitude: string;
  longitude: string;
  timezone: string;
  grid: Record<string, string[][]>;
}

export function initialDirectoryState(user: CurrentUser): DirectoryFieldState {
  return {
    specialties: user.specialties ?? [],
    feeMin: user.consultation_fee_min?.toString() ?? "",
    feeMax: user.consultation_fee_max?.toString() ?? "",
    feeCurrency: user.fee_currency ?? "",
    latitude: user.clinic_latitude?.toString() ?? "",
    longitude: user.clinic_longitude?.toString() ?? "",
    timezone: user.clinic_timezone ?? "",
    grid: (user.clinic_hours_grid as Record<string, string[][]>) ?? {},
  };
}

/** What the form sends. Empty strings become nulls, never zeroes. */
export function directoryPayload(state: DirectoryFieldState) {
  const number = (value: string) => (value.trim() === "" ? null : Number(value));
  return {
    specialties: state.specialties,
    consultation_fee_min: number(state.feeMin),
    consultation_fee_max: number(state.feeMax),
    fee_currency: state.feeCurrency.trim() || null,
    clinic_latitude: number(state.latitude),
    clinic_longitude: number(state.longitude),
    clinic_timezone: state.timezone.trim() || null,
    clinic_hours_grid: Object.keys(state.grid).length > 0 ? state.grid : null,
  };
}

/*
 * The details that make a practice findable, filled in by the practice.
 *
 * Every one of these is optional and every one is a filter, which is the trade
 * this panel has to be honest about: leaving a field blank does not hide the
 * practice from the directory, but it does hide them from anybody who filters
 * on it. So each group says what it buys rather than just asking for data.
 *
 * The coordinates are typed rather than geocoded from the address, because
 * geocoding needs a service this deployment does not have — and a pin the
 * platform guessed wrongly is worse than one the practice placed itself. The
 * "use my current location" button is for the common case of somebody filling
 * this in while sitting in the clinic.
 */
export default function VetDirectoryFields({
  value,
  onChange,
}: {
  value: DirectoryFieldState;
  onChange: (next: DirectoryFieldState) => void;
}) {
  const [specialties, setSpecialties] = useState<SpecialtyOption[]>([]);
  const [locating, setLocating] = useState(false);

  useEffect(() => {
    getSpecialties()
      .then(setSpecialties)
      .catch(() => setSpecialties([]));
  }, []);

  const set = <K extends keyof DirectoryFieldState>(key: K, next: DirectoryFieldState[K]) =>
    onChange({ ...value, [key]: next });

  const toggleSpecialty = (slug: string) =>
    set(
      "specialties",
      value.specialties.includes(slug)
        ? value.specialties.filter((item) => item !== slug)
        : [...value.specialties, slug],
    );

  const periodsFor = (day: string) => value.grid[day] ?? [];

  const setPeriod = (day: string, index: number, which: 0 | 1, clock: string) => {
    const periods = periodsFor(day).map((pair, at) =>
      at === index ? ((which === 0 ? [clock, pair[1]] : [pair[0], clock]) as string[]) : pair,
    );
    set("grid", { ...value.grid, [day]: periods });
  };

  const addPeriod = (day: string) =>
    set("grid", { ...value.grid, [day]: [...periodsFor(day), ["09:00", "17:00"]] });

  const removePeriod = (day: string, index: number) => {
    const periods = periodsFor(day).filter((_, at) => at !== index);
    const next = { ...value.grid };
    if (periods.length === 0) delete next[day];
    else next[day] = periods;
    set("grid", next);
  };

  const useCurrentLocation = () => {
    if (!navigator.geolocation) return;
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (found) => {
        onChange({
          ...value,
          latitude: found.coords.latitude.toFixed(6),
          longitude: found.coords.longitude.toFixed(6),
        });
        setLocating(false);
      },
      () => setLocating(false),
      { timeout: 10_000 },
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-semibold text-slate-800">What you treat</h3>
        <p className="mt-0.5 text-xs text-slate-500">
          Owners filter by these. Leaving them blank keeps you in the directory but out of
          every specialty search.
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          {specialties.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => toggleSpecialty(option.value)}
              aria-pressed={value.specialties.includes(option.value)}
              className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${
                value.specialties.includes(option.value)
                  ? "bg-primary-600 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-slate-800">Consultation fee</h3>
        <p className="mt-0.5 text-xs text-slate-500">
          A range, not a single price — a consultation is rarely one figure. Owners filtering
          by price are matched on the lower number.
        </p>
        <div className="mt-2 grid gap-3 sm:grid-cols-3">
          <Input
            label="From"
            type="number"
            min={0}
            value={value.feeMin}
            onChange={(event) => set("feeMin", event.target.value)}
          />
          <Input
            label="To (optional)"
            type="number"
            min={0}
            value={value.feeMax}
            onChange={(event) => set("feeMax", event.target.value)}
          />
          <Input
            label="Currency"
            value={value.feeCurrency}
            onChange={(event) => set("feeCurrency", event.target.value)}
            placeholder="TRY"
            maxLength={8}
          />
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-slate-800">Where you are</h3>
        <p className="mt-0.5 text-xs text-slate-500">
          Coordinates, so owners can sort by distance. We do not look these up from your
          address — a pin we guessed wrongly is worse than one you placed.
        </p>
        <div className="mt-2 grid gap-3 sm:grid-cols-2">
          <Input
            label="Latitude"
            value={value.latitude}
            onChange={(event) => set("latitude", event.target.value)}
            placeholder="41.0082"
          />
          <Input
            label="Longitude"
            value={value.longitude}
            onChange={(event) => set("longitude", event.target.value)}
            placeholder="28.9784"
          />
        </div>
        <button
          type="button"
          onClick={useCurrentLocation}
          disabled={locating}
          className="mt-2 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 disabled:opacity-50"
        >
          {locating ? "Finding…" : "Use this device's location"}
        </button>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-slate-800">Opening hours grid</h3>
        {/*
          Said plainly, because the sentence above it in the form is the one
          that matters. A grid cannot express alternate Saturdays or a seasonal
          closure; the written hours stay the thing a human reads, and this is
          only what makes "open now" answerable.
        */}
        <p className="mt-0.5 text-xs text-slate-500">
          Optional, and it does not replace the written hours above — it only lets the
          directory answer &ldquo;open now&rdquo;. Add a second period for a lunch break.
          Leave a day empty if you are closed.
        </p>
        <Input
          label="Timezone"
          value={value.timezone}
          onChange={(event) => set("timezone", event.target.value)}
          placeholder={Intl.DateTimeFormat().resolvedOptions().timeZone}
          hint="Without this the grid is read in UTC, which is unlikely to be your clock."
          className="mt-2"
        />
        <div className="mt-3 space-y-2">
          {DAYS.map((day) => (
            <div key={day.key} className="flex flex-wrap items-center gap-2">
              <span className="w-10 text-xs font-semibold uppercase text-slate-500">
                {day.label}
              </span>
              {periodsFor(day.key).map((pair, index) => (
                <span key={index} className="flex items-center gap-1">
                  <input
                    aria-label={`${day.label} period ${index + 1} opens`}
                    type="time"
                    value={pair[0]}
                    onChange={(event) => setPeriod(day.key, index, 0, event.target.value)}
                    className="rounded border border-slate-300 px-2 py-1 text-xs"
                  />
                  <span className="text-slate-400">–</span>
                  <input
                    aria-label={`${day.label} period ${index + 1} closes`}
                    type="time"
                    value={pair[1]}
                    onChange={(event) => setPeriod(day.key, index, 1, event.target.value)}
                    className="rounded border border-slate-300 px-2 py-1 text-xs"
                  />
                  <button
                    type="button"
                    onClick={() => removePeriod(day.key, index)}
                    aria-label={`Remove ${day.label} period ${index + 1}`}
                    className="px-1 text-slate-400 hover:text-rose-600"
                  >
                    ×
                  </button>
                </span>
              ))}
              <button
                type="button"
                onClick={() => addPeriod(day.key)}
                className="rounded border border-dashed border-slate-300 px-2 py-1 text-xs text-slate-500"
              >
                + period
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
