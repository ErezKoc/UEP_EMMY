import { useEffect, useState } from "react";
import { ApiError, getVetSlots } from "../api/client";
import { Spinner } from "./ui";
import { formatDate } from "../lib/format";
import type { AvailabilitySlot, Veterinarian } from "../types";

/** "09:00:00" → "09:00". */
function clock(value: string): string {
  return value.slice(0, 5);
}

/*
 * The times a practice has published here.
 *
 * The heading says "published by the practice" and not "available times", and
 * that wording is the feature. This app has no connection to whatever software
 * runs a clinic's diary; what it has is the practice saying, on this platform,
 * that these hours are free. Presenting that as a live view of their calendar
 * would be the same lie the appointment flow was built to avoid — an owner who
 * believes a time is reserved and finds a closed door.
 *
 * A practice with nothing published gets a sentence saying so, never an empty
 * list that reads as "fully booked". Most practices publish nothing at all,
 * and they are still perfectly able to see your animal.
 */
export default function VetAvailability({
  vet,
  onPick,
  canRequest,
}: {
  vet: Veterinarian;
  /** Called with the slot the owner chose, to open the request dialog on it. */
  onPick?: (slot: AvailabilitySlot) => void;
  canRequest: boolean;
}) {
  const [slots, setSlots] = useState<AvailabilitySlot[] | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!expanded || slots !== null) return;
    getVetSlots(vet.id, 30)
      .then(setSlots)
      .catch((reason) =>
        setError(reason instanceof ApiError ? reason.message : "Could not load times."),
      );
  }, [expanded, slots, vet.id]);

  if (vet.published_slot_count === 0) {
    return (
      <p className="mt-3 text-xs text-slate-500">
        No times published here. That does not mean they are full — most practices arrange
        appointments by request rather than publishing a diary.
      </p>
    );
  }

  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={() => setExpanded((current) => !current)}
        aria-expanded={expanded}
        className="text-sm font-medium text-primary-600 hover:text-primary-700"
      >
        {expanded ? "Hide" : "Show"} {vet.published_slot_count} published{" "}
        {vet.published_slot_count === 1 ? "time" : "times"}
      </button>

      {expanded && (
        <div className="mt-2">
          {slots === null && !error && (
            <div className="flex justify-center py-4">
              <Spinner />
            </div>
          )}
          {error && (
            <p className="text-xs text-rose-600" role="alert">
              {error}
            </p>
          )}
          {slots !== null && (
            <>
              <p className="mb-2 text-xs text-slate-500">
                Published by the practice. Picking one still sends a request they answer —
                it tells them exactly which time you want.
              </p>
              <ul className="flex flex-wrap gap-2">
                {slots.map((slot) => (
                  <li key={slot.id}>
                    <button
                      type="button"
                      disabled={!canRequest || !onPick}
                      onClick={() => onPick?.(slot)}
                      title={
                        canRequest
                          ? slot.note ?? "Request this time"
                          : "Sign in to request a time"
                      }
                      className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-left text-xs text-slate-700 hover:border-primary-400 hover:bg-primary-50 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      <span className="block font-semibold">{formatDate(slot.slot_date)}</span>
                      <span className="block">
                        {clock(slot.start_time)}–{clock(slot.end_time)}
                      </span>
                      {/*
                        Only shown for an open surgery. "0 of 1 taken" on a
                        normal appointment is noise; "2 of 6 taken" is the
                        thing somebody needs to judge whether to turn up.
                      */}
                      {slot.capacity > 1 && (
                        <span className="block text-slate-400">
                          {slot.taken} of {slot.capacity} taken
                        </span>
                      )}
                      {slot.note && <span className="block text-slate-400">{slot.note}</span>}
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}
