import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { ApiError, getVetSlots, publishSlots, withdrawSlot } from "../api/client";
import { Button, Card, Input, Spinner, useToast } from "./ui";
import { formatDate } from "../lib/format";
import type { AvailabilitySlot } from "../types";

function todayValue(): string {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

/*
 * A practice publishing the times it has free.
 *
 * The wording here never says "your diary" or "your calendar", because this is
 * not connected to either. It is a list the practice chooses to advertise on
 * this platform, and an owner picking one still sends a request that gets
 * answered — publishing a time is not agreeing to it in advance.
 *
 * Repeating weekly is offered up front rather than as an advanced option,
 * because publishing one slot at a time is the reason a practice would fill
 * this in once and never again.
 */
export default function PublishedSlotsCard({ vetId }: { vetId: string }) {
  const { toast } = useToast();
  const [slots, setSlots] = useState<AvailabilitySlot[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [slotDate, setSlotDate] = useState(todayValue());
  const [startTime, setStartTime] = useState("09:00");
  const [endTime, setEndTime] = useState("09:30");
  const [capacity, setCapacity] = useState(1);
  const [note, setNote] = useState("");
  const [repeatWeeks, setRepeatWeeks] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      // `days` covers the full window a practice may publish into, so the list
      // shows everything they have advertised rather than the next fortnight.
      setSlots(await getVetSlots(vetId, 180));
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Could not load your times.");
    } finally {
      setLoading(false);
    }
  }, [vetId]);

  useEffect(() => {
    void load();
  }, [load]);

  const publish = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const created = await publishSlots({
        slot_date: slotDate,
        start_time: startTime,
        end_time: endTime,
        capacity,
        note: note.trim() || null,
        repeat_weeks: repeatWeeks,
      });
      toast(
        created.length === 0
          ? "Those times were already published."
          : `Published ${created.length} ${created.length === 1 ? "time" : "times"}.`,
        "success",
      );
      setNote("");
      await load();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Could not publish that.");
    } finally {
      setSaving(false);
    }
  };

  const withdraw = async (slot: AvailabilitySlot) => {
    try {
      await withdrawSlot(slot.id);
      await load();
    } catch (reason) {
      toast(reason instanceof ApiError ? reason.message : "Could not withdraw that.", "error");
    }
  };

  return (
    <Card
      title="Times you have published"
      description="Openings owners can pick from when they send you a request. This is not linked to your own calendar — it is only what you choose to advertise here."
    >
      <form onSubmit={publish} className="mt-4 grid gap-3 sm:grid-cols-2">
        <Input
          label="Date"
          type="date"
          value={slotDate}
          min={todayValue()}
          onChange={(event) => setSlotDate(event.target.value)}
          required
        />
        <Input
          label="Repeat weekly for"
          type="number"
          min={0}
          max={26}
          value={repeatWeeks}
          onChange={(event) => setRepeatWeeks(Math.max(0, Number(event.target.value) || 0))}
          hint="0 publishes just this one."
        />
        <Input
          label="From"
          type="time"
          value={startTime}
          onChange={(event) => setStartTime(event.target.value)}
          required
        />
        <Input
          label="To"
          type="time"
          value={endTime}
          onChange={(event) => setEndTime(event.target.value)}
          required
        />
        <Input
          label="How many can you see?"
          type="number"
          min={1}
          max={50}
          value={capacity}
          onChange={(event) => setCapacity(Math.max(1, Number(event.target.value) || 1))}
          hint="More than 1 for an open surgery where several owners are told the same hour."
        />
        <Input
          label="Note (optional)"
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder="Vaccinations only"
          maxLength={200}
        />
        <div className="sm:col-span-2">
          <Button type="submit" loading={saving}>
            Publish
          </Button>
        </div>
        {error && (
          <p className="text-sm text-rose-600 sm:col-span-2" role="alert">
            {error}
          </p>
        )}
      </form>

      <div className="mt-5">
        {loading && (
          <div className="flex justify-center py-6">
            <Spinner />
          </div>
        )}
        {!loading && slots.length === 0 && (
          <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-500">
            Nothing published. Owners can still send you a request describing when suits
            them — publishing times just saves that conversation.
          </p>
        )}
        {!loading && slots.length > 0 && (
          <ul className="space-y-2">
            {slots.map((slot) => (
              <li
                key={slot.id}
                className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 px-3 py-2 text-sm"
              >
                <span className="font-medium text-slate-800">
                  {formatDate(slot.slot_date)}
                </span>
                <span className="text-slate-600">
                  {slot.start_time.slice(0, 5)}–{slot.end_time.slice(0, 5)}
                </span>
                {slot.capacity > 1 && (
                  <span className="text-xs text-slate-500">
                    {slot.taken} of {slot.capacity} taken
                  </span>
                )}
                {slot.note && <span className="text-xs text-slate-500">{slot.note}</span>}
                <button
                  type="button"
                  onClick={() => void withdraw(slot)}
                  className="ml-auto text-xs font-medium text-rose-600 hover:text-rose-700"
                >
                  Withdraw
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
