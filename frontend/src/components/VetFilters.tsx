import { useEffect, useState } from "react";
import { getSpecialties } from "../api/client";
import type { SpecialtyOption } from "../types";

export interface VetFilterState {
  verifiedOnly: boolean;
  acceptingOnly: boolean;
  specialties: string[];
  openNow: boolean;
  maxFee: number | null;
  hasAvailability: boolean;
  radiusKm: number | null;
  sort: "relevance" | "distance" | "price" | "soonest";
}

export const EMPTY_FILTERS: VetFilterState = {
  verifiedOnly: false,
  acceptingOnly: false,
  specialties: [],
  openNow: false,
  maxFee: null,
  hasAvailability: false,
  radiusKm: null,
  sort: "relevance",
};

/** Where the searcher is, once they have said. */
export interface Position {
  lat: number;
  lng: number;
}

/*
 * The filters, and the sentence that has to sit under them.
 *
 * Every one of these narrows to practices that have PUBLISHED the thing being
 * filtered on, and that is not obvious from a tick-box. A clinic that never
 * entered its opening hours vanishes the moment somebody ticks "open now" —
 * not because it is shut, but because nobody can say. Silently dropping real
 * practices out of a directory an owner is searching in an emergency is the
 * worst thing this feature could do, so the panel says it out loud instead of
 * hoping nobody notices.
 */
export default function VetFilters({
  value,
  onChange,
  position,
  onLocate,
  locating,
  locationError,
}: {
  value: VetFilterState;
  onChange: (next: VetFilterState) => void;
  position: Position | null;
  onLocate: () => void;
  locating: boolean;
  locationError: string | null;
}) {
  const [specialties, setSpecialties] = useState<SpecialtyOption[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    // The catalogue comes from the server so this list can never drift from
    // the one the filter actually matches against.
    getSpecialties()
      .then(setSpecialties)
      .catch(() => setSpecialties([]));
  }, []);

  const set = <K extends keyof VetFilterState>(key: K, next: VetFilterState[K]) =>
    onChange({ ...value, [key]: next });

  const toggleSpecialty = (slug: string) =>
    set(
      "specialties",
      value.specialties.includes(slug)
        ? value.specialties.filter((item) => item !== slug)
        : [...value.specialties, slug],
    );

  const activeCount =
    (value.verifiedOnly ? 1 : 0) +
    (value.acceptingOnly ? 1 : 0) +
    value.specialties.length +
    (value.openNow ? 1 : 0) +
    (value.maxFee != null ? 1 : 0) +
    (value.hasAvailability ? 1 : 0) +
    (value.radiusKm != null ? 1 : 0);

  return (
    <section className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => setOpen((current) => !current)}
          aria-expanded={open}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-semibold text-slate-700"
        >
          Filters{activeCount > 0 ? ` (${activeCount})` : ""}
        </button>

        {/*
          Location is asked for, never taken. The browser prompts, and until
          somebody answers it the distance column simply does not exist — which
          is why the sort option below is disabled rather than silently doing
          nothing.
        */}
        <button
          type="button"
          onClick={onLocate}
          disabled={locating}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700 disabled:opacity-50"
        >
          {locating
            ? "Finding you…"
            : position
              ? "Update my location"
              : "Use my location"}
        </button>

        <span className="ml-auto flex items-center gap-2">
          <label htmlFor="vet-sort" className="text-xs text-slate-500">
            Sort
          </label>
          <select
            id="vet-sort"
            value={value.sort}
            onChange={(event) => set("sort", event.target.value as VetFilterState["sort"])}
            className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700"
          >
            <option value="relevance">Verified first</option>
            <option value="distance" disabled={!position}>
              Nearest {position ? "" : "(needs your location)"}
            </option>
            <option value="price">Lowest price</option>
            <option value="soonest">Soonest opening</option>
          </select>
        </span>
      </div>

      {locationError && (
        <p className="mt-2 text-xs text-amber-700" role="alert">
          {locationError}
        </p>
      )}
      {position && (
        <p className="mt-2 text-xs text-slate-500">
          Measuring from your device&apos;s location. Distances are straight-line, not
          driving distance.
        </p>
      )}

      {open && (
        <div className="mt-4 space-y-4 border-t border-slate-100 pt-4">
          <div className="flex flex-wrap gap-4 text-sm text-slate-700">
            <label className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={value.verifiedOnly}
                onChange={(event) => set("verifiedOnly", event.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-primary-600"
              />
              Verified only
            </label>
            <label className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={value.acceptingOnly}
                onChange={(event) => set("acceptingOnly", event.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-primary-600"
              />
              Taking appointment requests
            </label>
            <label className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={value.openNow}
                onChange={(event) => set("openNow", event.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-primary-600"
              />
              Open right now
            </label>
            <label className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={value.hasAvailability}
                onChange={(event) => set("hasAvailability", event.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-primary-600"
              />
              Has published times
            </label>
          </div>

          <div>
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Specialty
            </p>
            <div className="flex flex-wrap gap-2">
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

          <div className="flex flex-wrap gap-4">
            <label className="text-sm text-slate-700">
              <span className="block text-xs font-semibold uppercase tracking-wide text-slate-500">
                Within
              </span>
              <select
                value={value.radiusKm ?? ""}
                onChange={(event) =>
                  set("radiusKm", event.target.value ? Number(event.target.value) : null)
                }
                disabled={!position}
                className="mt-1 rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm disabled:bg-slate-50 disabled:text-slate-400"
              >
                <option value="">Any distance</option>
                <option value="5">5 km</option>
                <option value="10">10 km</option>
                <option value="25">25 km</option>
                <option value="50">50 km</option>
              </select>
              {!position && (
                <span className="mt-1 block text-xs text-slate-400">
                  Needs your location
                </span>
              )}
            </label>

            <label className="text-sm text-slate-700">
              <span className="block text-xs font-semibold uppercase tracking-wide text-slate-500">
                Consultation from, at most
              </span>
              <input
                type="number"
                min={0}
                step={50}
                value={value.maxFee ?? ""}
                onChange={(event) =>
                  set("maxFee", event.target.value === "" ? null : Number(event.target.value))
                }
                placeholder="Any price"
                className="mt-1 w-36 rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
              />
              {/*
                Named precisely. The filter compares the BOTTOM of each
                practice's range, because that is the only figure a clinic
                quoting "400-900" has committed to — and a box labelled just
                "max price" would promise the visit costs no more than this.
              */}
              <span className="mt-1 block text-xs text-slate-400">
                Matches the lowest price a practice quotes
              </span>
            </label>
          </div>

          <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-600">
            <span className="font-semibold">These filters narrow to practices that have
            published the detail.</span>{" "}
            A clinic that has not entered its opening hours is not a closed clinic, one with
            no address on file is not far away, and one with no published times is not fully
            booked — but each disappears while the matching filter is on. Clear the filters to
            see everyone.
          </p>

          {activeCount > 0 && (
            <button
              type="button"
              onClick={() => onChange({ ...EMPTY_FILTERS, sort: value.sort })}
              className="text-sm font-medium text-primary-600"
            >
              Clear filters
            </button>
          )}
        </div>
      )}
    </section>
  );
}
