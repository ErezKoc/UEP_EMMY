import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  completeOccurrence,
  createReminder,
  deleteReminder,
  getAnimals,
  getDuplicateReminders,
  getReminderOccurrences,
  getReminders,
  resolveDuplicateReminders,
  snoozeOccurrence,
  uncompleteOccurrence,
  unsnoozeOccurrence,
  updateReminder,
} from "../../api/client";
import { useSession } from "../../auth/SessionContext";
import type {
  Animal,
  DuplicateGroup,
  Reminder,
  ReminderOccurrence,
  ReminderPayload,
} from "../../types";
import { formatDate, formatMonthYear } from "../../lib/format";

const today = new Date();
const emptyForm = (): ReminderPayload => ({
  title: "",
  reminder_type: "vaccine",
  due_date: today.toISOString().slice(0, 10),
  recurrence: "none",
  // Present from the start so the interval box is a controlled input the
  // moment somebody switches away from "does not repeat".
  recurrence_interval: 1,
  repeat_until: null,
  notify_lead_days: null,
  notes: "",
  animal_id: "",
});

const labels = { vaccine: "Vaccine", checkup: "Check-up", other: "Other" } as const;
const colors = {
  vaccine: "bg-emerald-100 text-emerald-800",
  checkup: "bg-sky-100 text-sky-800",
  other: "bg-amber-100 text-amber-800",
} as const;

const startOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());

function isoDate(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

const TODAY_ISO = isoDate(today);

/*
 * Overdue means "still waiting, and the day has passed" — for any reminder,
 * repeating or not.
 *
 * It used to mean that only for one-offs, because a repeating reminder always
 * had a future occurrence to point at and so could never look late. That hid
 * exactly the case worth showing: a monthly treatment nobody has ticked off
 * since March. Now that instances can be marked done, "the next one you have
 * not done is in the past" is a question with a real answer.
 */
function isOverdue(reminder: Reminder) {
  return (
    !reminder.is_finished &&
    reminder.next_occurrence !== null &&
    new Date(`${reminder.next_occurrence}T00:00:00`) < startOfToday
  );
}

function googleCalendarUrl(reminder: Reminder) {
  const start = reminder.due_date.replaceAll("-", "");
  const endDate = new Date(`${reminder.due_date}T00:00:00`);
  endDate.setDate(endDate.getDate() + 1);
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: `${reminder.animal.name}: ${reminder.title}`,
    dates: `${start}/${isoDate(endDate).replaceAll("-", "")}`,
    details: reminder.notes || `${labels[reminder.reminder_type]} reminder`,
  });
  return `https://calendar.google.com/calendar/render?${params}`;
}

function downloadIcs(reminder: Reminder) {
  const start = reminder.due_date.replaceAll("-", "");
  const next = new Date(`${reminder.due_date}T00:00:00`);
  next.setDate(next.getDate() + 1);
  const rule = reminder.recurrence === "none" ? "" : `RRULE:FREQ=${reminder.recurrence.toUpperCase()}\r\n`;
  const safe = (value: string) => value.replaceAll("\\", "\\\\").replaceAll("\n", "\\n").replaceAll(",", "\\,");
  const body = `BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//UEP EMMY//Reminders//EN\r\nBEGIN:VEVENT\r\nUID:${reminder.id}@uep-emmy\r\nDTSTART;VALUE=DATE:${start}\r\nDTEND;VALUE=DATE:${isoDate(next).replaceAll("-", "")}\r\n${rule}SUMMARY:${safe(`${reminder.animal.name}: ${reminder.title}`)}\r\nDESCRIPTION:${safe(reminder.notes || labels[reminder.reminder_type])}\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n`;
  const url = URL.createObjectURL(new Blob([body], { type: "text/calendar;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `${reminder.title.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}.ics`;
  link.click();
  URL.revokeObjectURL(url);
}

export default function CalendarPage() {
  const { user } = useSession();
  const [month, setMonth] = useState(new Date(today.getFullYear(), today.getMonth(), 1));
  const [animals, setAnimals] = useState<Animal[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [occurrences, setOccurrences] = useState<ReminderOccurrence[]>([]);
  const [duplicates, setDuplicates] = useState<DuplicateGroup[]>([]);
  const [form, setForm] = useState<ReminderPayload>(emptyForm());
  const [editing, setEditing] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  /*
   * Collapsed by default, and the whole point of the complaint.
   *
   * A calendar showing every jab already given and every course already
   * finished is a calendar nobody can read. Finished reminders are kept - they
   * are the pet's history - but they are not what the page is for.
   */
  const [showFinished, setShowFinished] = useState(false);
  const [showDuplicates, setShowDuplicates] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);

  const days = useMemo(() => {
    const first = new Date(month);
    const offset = (first.getDay() + 6) % 7;
    const start = new Date(first);
    start.setDate(1 - offset);
    return Array.from({ length: 42 }, (_, index) => {
      const date = new Date(start);
      date.setDate(start.getDate() + index);
      return date;
    });
  }, [month]);

  const windowStart = days.length > 0 ? isoDate(days[0]!) : TODAY_ISO;
  const windowEnd = days.length > 0 ? isoDate(days[days.length - 1]!) : TODAY_ISO;

  const load = useCallback(async () => {
    try {
      const [pets, items, grid, dupes] = await Promise.all([
        getAnimals(),
        getReminders(),
        // The grid is asked for, not computed. One implementation of the
        // recurrence rules, on the side that also has to tell the email
        // scheduler the same thing.
        getReminderOccurrences(windowStart, windowEnd),
        getDuplicateReminders(),
      ]);
      setAnimals(pets);
      setReminders(items);
      setOccurrences(grid);
      setDuplicates(dupes);
      setForm((current) => ({ ...current, animal_id: current.animal_id || pets[0]?.id || "" }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load reminders.");
    }
  }, [windowStart, windowEnd]);

  useEffect(() => {
    void load();
  }, [load]);

  const byId = useMemo(
    () => new Map(reminders.map((item) => [item.id, item])),
    [reminders],
  );

  const matchesFilter = useCallback(
    (reminder: Reminder | undefined) =>
      reminder !== undefined && (!filter || reminder.animal_id === filter),
    [filter],
  );

  const visible = reminders.filter((item) => matchesFilter(item));
  const active = visible.filter((item) => !item.is_finished);
  const finished = visible.filter((item) => item.is_finished);

  const overdueCount = active.filter(isOverdue).length;
  const nextThirtyDays = new Date(startOfToday);
  nextThirtyDays.setDate(nextThirtyDays.getDate() + 30);
  const upcomingCount = active.filter((item) => {
    if (!item.next_occurrence) return false;
    const occurrence = new Date(`${item.next_occurrence}T00:00:00`);
    return occurrence >= startOfToday && occurrence <= nextThirtyDays;
  }).length;

  const duplicateCount = duplicates.reduce(
    (total, group) => total + group.duplicate_ids.length,
    0,
  );

  const run = async (key: string, action: () => Promise<unknown>) => {
    setBusy(key);
    setError("");
    try {
      await action();
      await load();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "That did not work.");
    } finally {
      setBusy(null);
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      if (editing) await updateReminder(editing, form);
      else await createReminder(form);
      setEditing(null);
      setShowAddForm(false);
      setForm({ ...emptyForm(), animal_id: animals[0]?.id || "" });
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save reminder.");
    } finally {
      setSaving(false);
    }
  };

  const edit = (item: Reminder) => {
    setEditing(item.id);
    setShowAddForm(true);
    setForm({
      title: item.title,
      reminder_type: item.reminder_type,
      due_date: item.due_date,
      recurrence: item.recurrence,
      recurrence_interval: item.recurrence_interval,
      repeat_until: item.repeat_until,
      notify_lead_days: item.notify_lead_days,
      notes: item.notes,
      animal_id: item.animal_id,
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const formOpen = showAddForm || editing !== null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-primary-600">Pet health planner</p>
          <h1 className="text-3xl font-bold text-slate-900">Calendar &amp; reminders</h1>
          <p className="mt-1 text-slate-600">Plan vaccinations and routine check-ups, including recurring visits.</p>
        </div>
        {/*
          The form is behind a button now. It used to sit permanently across the
          top of the page — nine controls a returning owner has to scroll past
          every time to reach the thing they came for, which is what their
          reminders are doing this week.
        */}
        <button
          type="button"
          onClick={() => {
            setShowAddForm((open) => !open);
            if (editing) {
              setEditing(null);
              setForm({ ...emptyForm(), animal_id: animals[0]?.id || "" });
            }
          }}
          className="rounded-lg bg-primary-600 px-4 py-2 font-semibold text-white"
        >
          {formOpen ? "Close" : "Add a reminder"}
        </button>
      </div>

      {duplicateCount > 0 && (
        <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm font-semibold text-amber-900">
              {duplicateCount === 1
                ? "1 duplicate reminder is cluttering this calendar."
                : `${duplicateCount} duplicate reminders are cluttering this calendar.`}
            </p>
            <button
              type="button"
              onClick={() => setShowDuplicates((open) => !open)}
              className="rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-sm font-medium text-amber-900"
            >
              {showDuplicates ? "Hide" : "Review them"}
            </button>
          </div>
          {/*
            Shown before anything is deleted, never tidied away silently. The
            obvious version of this feature removes the extras on its own, and
            the one time it is wrong somebody loses the reminder for a booster
            they will now miss.
          */}
          {showDuplicates && (
            <div className="mt-4 space-y-3">
              {duplicates.map((group) => (
                <div key={group.keep_id} className="rounded-xl bg-white p-3">
                  <p className="text-sm font-semibold text-slate-800">
                    {group.animal_name}: {group.title}
                  </p>
                  <p className="text-xs text-slate-500">
                    {labels[group.reminder_type]} · {formatDate(group.due_date)} ·{" "}
                    {group.reminders.length} copies
                  </p>
                  <p className="mt-2 text-xs text-slate-600">
                    Keeping the oldest — it is the one carrying any notes and anything
                    already ticked off. {group.duplicate_ids.length}{" "}
                    {group.duplicate_ids.length === 1 ? "copy" : "copies"} would be deleted.
                  </p>
                  <button
                    type="button"
                    disabled={busy === `dupe-${group.keep_id}`}
                    onClick={() =>
                      void run(`dupe-${group.keep_id}`, () =>
                        resolveDuplicateReminders(group.duplicate_ids),
                      )
                    }
                    className="mt-2 rounded-lg border border-rose-200 px-3 py-1.5 text-sm font-medium text-rose-700 disabled:opacity-50"
                  >
                    Remove the extra {group.duplicate_ids.length === 1 ? "copy" : "copies"}
                  </button>
                </div>
              ))}
              {duplicates.length > 1 && (
                <button
                  type="button"
                  disabled={busy === "dupe-all"}
                  onClick={() =>
                    void run("dupe-all", () =>
                      resolveDuplicateReminders(
                        duplicates.flatMap((group) => group.duplicate_ids),
                      ),
                    )
                  }
                  className="rounded-lg bg-rose-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
                >
                  Remove all {duplicateCount} extra copies
                </button>
              )}
            </div>
          )}
        </section>
      )}

      {formOpen && (
        <form onSubmit={submit} className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:grid-cols-3">
          <input required aria-label="Title" placeholder="e.g. Rabies vaccine" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2" />
          <select required aria-label="Pet" value={form.animal_id} onChange={(e) => setForm({ ...form, animal_id: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2">
            <option value="">Select pet</option>{animals.map((pet) => <option key={pet.id} value={pet.id}>{pet.name}</option>)}
          </select>
          <select aria-label="Type" value={form.reminder_type} onChange={(e) => setForm({ ...form, reminder_type: e.target.value as ReminderPayload["reminder_type"] })} className="rounded-lg border border-slate-300 px-3 py-2">
            <option value="vaccine">Vaccine</option><option value="checkup">Check-up</option><option value="other">Other</option>
          </select>
          <input required aria-label="Due date" type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2" />
          <select aria-label="Repeat" value={form.recurrence} onChange={(e) => setForm({ ...form, recurrence: e.target.value as ReminderPayload["recurrence"] })} className="rounded-lg border border-slate-300 px-3 py-2">
            <option value="none">Does not repeat</option>
            <option value="daily">Every N days</option>
            <option value="weekly">Every N weeks</option>
            <option value="monthly">Every N months</option>
            <option value="yearly">Every N years</option>
          </select>
          {/*
            Both only appear once something repeats. An interval box beside "does
            not repeat" is a control with no meaning, and an end date for a one-off
            is a second way to say the same thing as the due date.
          */}
          {form.recurrence !== "none" && (
            <input
              required
              aria-label="Repeat every"
              type="number"
              min={1}
              max={365}
              value={form.recurrence_interval ?? 1}
              onChange={(e) => setForm({ ...form, recurrence_interval: Math.max(1, Number(e.target.value) || 1) })}
              className="rounded-lg border border-slate-300 px-3 py-2"
              placeholder="Repeat every"
            />
          )}
          {form.recurrence !== "none" && (
            <input
              aria-label="Repeat until"
              type="date"
              value={form.repeat_until ?? ""}
              onChange={(e) => setForm({ ...form, repeat_until: e.target.value || null })}
              className="rounded-lg border border-slate-300 px-3 py-2"
              title="Stop repeating after this date (optional)"
            />
          )}
          {/*
            Per reminder, because one lead time for everything is the wrong
            shape: a booster needs a week's warning because it needs an
            appointment, and tonight's tablet needs none because there is
            nothing to arrange. Blank keeps the account default, so changing
            that still moves everything which never asked for anything else.
          */}
          <label className="flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600">
            <span className="whitespace-nowrap">Warn me</span>
            <input
              aria-label="Days of warning"
              type="number"
              min={0}
              max={90}
              placeholder={String(user?.notify_lead_days ?? 1)}
              value={form.notify_lead_days ?? ""}
              onChange={(e) =>
                setForm({
                  ...form,
                  notify_lead_days: e.target.value === "" ? null : Math.max(0, Number(e.target.value) || 0),
                })
              }
              className="w-16 rounded border border-slate-200 px-2 py-1"
            />
            <span className="whitespace-nowrap">days ahead</span>
          </label>
          <input aria-label="Notes" placeholder="Notes (optional)" value={form.notes || ""} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 md:col-span-2" />
          <div className="flex gap-2 md:col-span-3">
            <button disabled={saving || animals.length === 0} className="rounded-lg bg-primary-600 px-4 py-2 font-semibold text-white disabled:opacity-50">{saving ? "Saving…" : editing ? "Update reminder" : "Add reminder"}</button>
            <button type="button" onClick={() => { setEditing(null); setShowAddForm(false); setForm({ ...emptyForm(), animal_id: animals[0]?.id || "" }); }} className="rounded-lg border border-slate-300 px-4 py-2">Cancel</button>
          </div>
          {animals.length === 0 && <p className="text-sm text-amber-700 md:col-span-3">Add a pet before creating a reminder.</p>}
        </form>
      )}

      {error && (
        <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
          {error}
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-primary-100 bg-primary-50 p-4">
          <p className="text-sm font-medium text-primary-700">Due in the next 30 days</p>
          <p className="mt-1 text-2xl font-bold text-primary-900">{upcomingCount}</p>
        </div>
        <div className={`rounded-xl border p-4 ${overdueCount > 0 ? "border-rose-200 bg-rose-50" : "border-slate-200 bg-white"}`}>
          <p className={`text-sm font-medium ${overdueCount > 0 ? "text-rose-700" : "text-slate-600"}`}>Overdue reminders</p>
          <p className={`mt-1 text-2xl font-bold ${overdueCount > 0 ? "text-rose-800" : "text-slate-800"}`}>{overdueCount}</p>
        </div>
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))} className="rounded-lg border px-3 py-2" aria-label="Previous month">←</button>
          <h2 className="min-w-48 text-center text-lg font-bold">{formatMonthYear(month)}</h2>
          <button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))} className="rounded-lg border px-3 py-2" aria-label="Next month">→</button>
          <button
            type="button"
            onClick={() => setMonth(new Date(today.getFullYear(), today.getMonth(), 1))}
            disabled={month.getFullYear() === today.getFullYear() && month.getMonth() === today.getMonth()}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 disabled:cursor-default disabled:opacity-40"
          >
            Today
          </button>
          <select aria-label="Filter by pet" value={filter} onChange={(e) => setFilter(e.target.value)} className="ml-auto rounded-lg border border-slate-300 px-3 py-2"><option value="">All pets</option>{animals.map((pet) => <option key={pet.id} value={pet.id}>{pet.name}</option>)}</select>
        </div>
        <div className="mb-3 flex flex-wrap gap-x-4 gap-y-2 text-xs text-slate-600" aria-label="Reminder color legend">
          {(["vaccine", "checkup", "other"] as const).map((type) => <span key={type} className="inline-flex items-center gap-1.5"><span className={`h-2.5 w-2.5 rounded-full ${type === "vaccine" ? "bg-emerald-500" : type === "checkup" ? "bg-sky-500" : "bg-amber-500"}`} />{labels[type]}</span>)}
          <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-rose-500" />Overdue</span>
          <span className="inline-flex items-center gap-1.5"><span className="text-slate-400">✓</span>Done</span>
          <span className="inline-flex items-center gap-1.5"><span className="text-slate-400">→</span>Snoozed to here</span>
        </div>
        <div className="grid grid-cols-7 text-center text-xs font-semibold uppercase text-slate-500">{["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day) => <div key={day} className="py-2">{day}</div>)}</div>
        <div className="grid grid-cols-7 border-l border-t border-slate-200">
          {days.map((date) => {
            const iso = isoDate(date);
            const entries = occurrences.filter(
              (item) => item.date === iso && matchesFilter(byId.get(item.reminder_id)),
            );
            const current = date.getMonth() === month.getMonth();
            return <div key={iso} className={`min-h-28 border-b border-r border-slate-200 p-1.5 ${current ? "bg-white" : "bg-slate-50 text-slate-400"}`}>
              <span className={`inline-flex h-7 w-7 items-center justify-center rounded-full text-sm ${iso === TODAY_ISO ? "bg-primary-600 text-white" : ""}`}>{date.getDate()}</span>
              <div className="space-y-1">{entries.map((entry) => {
                const item = byId.get(entry.reminder_id);
                if (!item) return null;
                const late = !entry.done && iso < TODAY_ISO;
                return (
                  <button
                    key={`${entry.reminder_id}-${entry.scheduled_date}`}
                    onClick={() => edit(item)}
                    title={[
                      `${item.animal.name} — ${labels[item.reminder_type]}`,
                      entry.done ? "Done" : "",
                      entry.snoozed ? `Snoozed from ${formatDate(entry.scheduled_date)}` : "",
                      item.notes,
                    ]
                      .filter(Boolean)
                      .join("\n")}
                    className={`block w-full truncate rounded px-1.5 py-1 text-left text-xs font-medium ${
                      entry.done
                        ? // Kept visible but plainly settled. Removing done
                          // instances from the grid would make the month a
                          // record of what is left rather than what happened.
                          "bg-slate-100 text-slate-400 line-through"
                        : late
                          ? "bg-rose-100 text-rose-800"
                          : colors[item.reminder_type]
                    }`}
                  >
                    {entry.done ? "✓ " : entry.snoozed ? "→ " : ""}
                    {item.animal.name}: {item.title}
                  </button>
                );
              })}</div>
            </div>;
          })}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-bold">Saved reminders</h2>
        {active.map((item) => (
          <ReminderRow
            key={item.id}
            item={item}
            busy={busy}
            onRun={run}
            onEdit={edit}
            onReload={load}
          />
        ))}
        {active.length === 0 && <p className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-slate-500">Nothing outstanding. {finished.length > 0 ? "Everything here has been done." : "No reminders yet."}</p>}

        {/*
          Finished reminders are history, not clutter — kept, but not in the
          way. A vaccination record is worth having; it is not worth scrolling
          past every week.
        */}
        {finished.length > 0 && (
          <div>
            <button
              type="button"
              onClick={() => setShowFinished((open) => !open)}
              aria-expanded={showFinished}
              className="text-sm font-medium text-primary-600"
            >
              {showFinished ? "Hide" : "Show"} {finished.length} finished{" "}
              {finished.length === 1 ? "reminder" : "reminders"}
            </button>
            {showFinished && (
              <div className="mt-3 space-y-3">
                {finished.map((item) => (
                  <ReminderRow
                    key={item.id}
                    item={item}
                    busy={busy}
                    onRun={run}
                    onEdit={edit}
                    onReload={load}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

function ReminderRow({
  item,
  busy,
  onRun,
  onEdit,
  onReload,
}: {
  item: Reminder;
  busy: string | null;
  onRun: (key: string, action: () => Promise<unknown>) => Promise<void>;
  onEdit: (item: Reminder) => void;
  onReload: () => Promise<void>;
}) {
  const overdue = isOverdue(item);
  // Every done/snooze call is keyed on the SCHEDULED date, not the date the
  // instance currently sits on — a snoozed one still answers to the day the
  // rule gave it, which is the day the rule will keep giving it.
  const scheduled = item.next_scheduled_date;
  const key = `${item.id}-${scheduled ?? "none"}`;
  const working = busy === key;

  return (
    <article className={`flex flex-col gap-3 rounded-xl border bg-white p-4 ${overdue ? "border-rose-200" : item.is_finished ? "border-slate-100 opacity-70" : "border-slate-200"}`}>
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full px-2 py-1 text-xs font-semibold ${colors[item.reminder_type]}`}>{labels[item.reminder_type]}</span>
            {overdue && <span className="rounded-full bg-rose-100 px-2 py-1 text-xs font-semibold text-rose-700">Overdue</span>}
            {item.is_finished && <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-600">Finished</span>}
            {item.next_is_snoozed && <span className="rounded-full bg-violet-100 px-2 py-1 text-xs font-semibold text-violet-700">Snoozed</span>}
            <strong className={`truncate ${item.is_finished ? "text-slate-500 line-through" : ""}`}>{item.title}</strong>
          </div>
          <p className={`mt-1 text-sm ${overdue ? "font-medium text-rose-700" : "text-slate-600"}`}>
            {item.animal.name} ·{" "}
            {item.next_occurrence ? (
              <>
                next due {formatDate(item.next_occurrence)}
                {item.next_is_snoozed && scheduled && (
                  <span className="text-violet-700"> (snoozed from {formatDate(scheduled)})</span>
                )}
              </>
            ) : (
              "nothing outstanding"
            )}
            {item.recurrence !== "none" ? ` · ${item.recurrence_description}` : ""}
            {item.completed_count > 0 ? ` · ${item.completed_count} done` : ""}
          </p>
          {item.notify_lead_days !== null && (
            <p className="mt-0.5 text-xs text-slate-500">
              Warns {item.notify_lead_days === 0 ? "on the day" : `${item.notify_lead_days} days ahead`}
            </p>
          )}
        </div>
      </div>

      {/*
        Done and Snooze first and largest, because they are what somebody opens
        this page to press. The export links are for once a year.
      */}
      {scheduled && (
        <div className="flex flex-wrap gap-2 text-sm">
          <button
            disabled={working}
            onClick={() => void onRun(key, () => completeOccurrence(item.id, scheduled))}
            className="rounded-lg bg-emerald-600 px-3 py-2 font-semibold text-white disabled:opacity-50"
          >
            ✓ Mark done
          </button>
          {[1, 3, 7].map((days) => (
            <button
              key={days}
              disabled={working}
              onClick={() => void onRun(key, () => snoozeOccurrence(item.id, scheduled, { days }))}
              className="rounded-lg border border-slate-300 px-3 py-2 disabled:opacity-50"
            >
              Snooze {days}d
            </button>
          ))}
          {item.next_is_snoozed && (
            <button
              disabled={working}
              onClick={() => void onRun(key, () => unsnoozeOccurrence(item.id, scheduled))}
              className="rounded-lg border border-violet-200 px-3 py-2 text-violet-700 disabled:opacity-50"
            >
              Undo snooze
            </button>
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-2 text-sm">
        {item.last_completed_date && (
          <button
            disabled={working}
            onClick={() =>
              // The date comes from the server. Reconstructing it here from
              // the recurrence rule would be the second implementation that
              // was just taken out of the month grid.
              void onRun(key, () =>
                uncompleteOccurrence(item.id, item.last_completed_date!),
              )
            }
            className="rounded-lg border px-3 py-2"
          >
            Undo last tick ({formatDate(item.last_completed_date)})
          </button>
        )}
        <a target="_blank" rel="noreferrer" href={googleCalendarUrl(item)} className="rounded-lg border px-3 py-2">Google Calendar</a>
        <button onClick={() => downloadIcs(item)} className="rounded-lg border px-3 py-2">Download .ics</button>
        <button onClick={() => onEdit(item)} className="rounded-lg border px-3 py-2">Edit</button>
        <button
          onClick={async () => {
            if (window.confirm(`Delete “${item.title}” for ${item.animal.name}? This removes the whole reminder, including anything already ticked off.`)) {
              await deleteReminder(item.id);
              await onReload();
            }
          }}
          className="rounded-lg border border-rose-200 px-3 py-2 text-rose-700"
        >
          Delete
        </button>
      </div>
    </article>
  );
}
