import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  createReminder,
  deleteReminder,
  getAnimals,
  getReminders,
  updateReminder,
} from "../../api/client";
import type { Animal, Reminder, ReminderPayload } from "../../types";

const today = new Date();
const emptyForm = (): ReminderPayload => ({
  title: "",
  reminder_type: "vaccine",
  due_date: today.toISOString().slice(0, 10),
  recurrence: "none",
  notes: "",
  animal_id: "",
});

const labels = { vaccine: "Vaccine", checkup: "Check-up", other: "Other" } as const;
const colors = {
  vaccine: "bg-emerald-100 text-emerald-800",
  checkup: "bg-sky-100 text-sky-800",
  other: "bg-amber-100 text-amber-800",
} as const;

function isoDate(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function occursOn(reminder: Reminder, date: Date) {
  const due = new Date(`${reminder.due_date}T00:00:00`);
  if (date < due) return false;
  if (reminder.recurrence === "none") return isoDate(date) === reminder.due_date;
  if (reminder.recurrence === "monthly") return date.getDate() === due.getDate();
  return date.getMonth() === due.getMonth() && date.getDate() === due.getDate();
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
  const [month, setMonth] = useState(new Date(today.getFullYear(), today.getMonth(), 1));
  const [animals, setAnimals] = useState<Animal[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [form, setForm] = useState<ReminderPayload>(emptyForm());
  const [editing, setEditing] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const [pets, items] = await Promise.all([getAnimals(), getReminders()]);
      setAnimals(pets);
      setReminders(items);
      setForm((current) => ({ ...current, animal_id: current.animal_id || pets[0]?.id || "" }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load reminders.");
    }
  };
  useEffect(() => { void load(); }, []);

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
  const visible = filter ? reminders.filter((item) => item.animal_id === filter) : reminders;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      if (editing) await updateReminder(editing, form);
      else await createReminder(form);
      setEditing(null);
      setForm({ ...emptyForm(), animal_id: animals[0]?.id || "" });
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save reminder.");
    } finally { setSaving(false); }
  };

  const edit = (item: Reminder) => {
    setEditing(item.id);
    setForm({ title: item.title, reminder_type: item.reminder_type, due_date: item.due_date, recurrence: item.recurrence, notes: item.notes, animal_id: item.animal_id });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-semibold text-primary-600">Pet health planner</p>
        <h1 className="text-3xl font-bold text-slate-900">Calendar & reminders</h1>
        <p className="mt-1 text-slate-600">Plan vaccinations and routine check-ups, including recurring visits.</p>
      </div>

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
          <option value="none">Does not repeat</option><option value="monthly">Monthly</option><option value="yearly">Yearly</option>
        </select>
        <input aria-label="Notes" placeholder="Notes (optional)" value={form.notes || ""} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2" />
        <div className="flex gap-2 md:col-span-3">
          <button disabled={saving || animals.length === 0} className="rounded-lg bg-primary-600 px-4 py-2 font-semibold text-white disabled:opacity-50">{saving ? "Saving…" : editing ? "Update reminder" : "Add reminder"}</button>
          {editing && <button type="button" onClick={() => { setEditing(null); setForm({ ...emptyForm(), animal_id: animals[0]?.id || "" }); }} className="rounded-lg border border-slate-300 px-4 py-2">Cancel</button>}
        </div>
        {animals.length === 0 && <p className="text-sm text-amber-700 md:col-span-3">Add a pet before creating a reminder.</p>}
        {error && <p className="text-sm text-rose-600 md:col-span-3">{error}</p>}
      </form>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))} className="rounded-lg border px-3 py-2" aria-label="Previous month">←</button>
          <h2 className="min-w-48 text-center text-lg font-bold">{month.toLocaleDateString(undefined, { month: "long", year: "numeric" })}</h2>
          <button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))} className="rounded-lg border px-3 py-2" aria-label="Next month">→</button>
          <select aria-label="Filter by pet" value={filter} onChange={(e) => setFilter(e.target.value)} className="ml-auto rounded-lg border border-slate-300 px-3 py-2"><option value="">All pets</option>{animals.map((pet) => <option key={pet.id} value={pet.id}>{pet.name}</option>)}</select>
        </div>
        <div className="grid grid-cols-7 text-center text-xs font-semibold uppercase text-slate-500">{["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day) => <div key={day} className="py-2">{day}</div>)}</div>
        <div className="grid grid-cols-7 border-l border-t border-slate-200">
          {days.map((date) => {
            const entries = visible.filter((item) => occursOn(item, date));
            const current = date.getMonth() === month.getMonth();
            return <div key={isoDate(date)} className={`min-h-28 border-b border-r border-slate-200 p-1.5 ${current ? "bg-white" : "bg-slate-50 text-slate-400"}`}>
              <span className={`inline-flex h-7 w-7 items-center justify-center rounded-full text-sm ${isoDate(date) === isoDate(today) ? "bg-primary-600 text-white" : ""}`}>{date.getDate()}</span>
              <div className="space-y-1">{entries.map((item) => <button key={item.id} onClick={() => edit(item)} title={`${item.animal.name} — ${labels[item.reminder_type]}`} className={`block w-full truncate rounded px-1.5 py-1 text-left text-xs font-medium ${colors[item.reminder_type]}`}>{item.animal.name}: {item.title}</button>)}</div>
            </div>;
          })}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-bold">Saved reminders</h2>
        {visible.map((item) => <article key={item.id} className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:flex-row sm:items-center">
          <div className="min-w-0 flex-1"><div className="flex items-center gap-2"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${colors[item.reminder_type]}`}>{labels[item.reminder_type]}</span><strong className="truncate">{item.title}</strong></div><p className="mt-1 text-sm text-slate-600">{item.animal.name} · {item.due_date}{item.recurrence !== "none" ? ` · ${item.recurrence}` : ""}</p></div>
          <div className="flex flex-wrap gap-2 text-sm"><a target="_blank" rel="noreferrer" href={googleCalendarUrl(item)} className="rounded-lg border px-3 py-2">Google Calendar</a><button onClick={() => downloadIcs(item)} className="rounded-lg border px-3 py-2">Download .ics</button><button onClick={() => edit(item)} className="rounded-lg border px-3 py-2">Edit</button><button onClick={async () => { if (window.confirm("Delete this reminder?")) { await deleteReminder(item.id); await load(); } }} className="rounded-lg border border-rose-200 px-3 py-2 text-rose-700">Delete</button></div>
        </article>)}
        {visible.length === 0 && <p className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-slate-500">No reminders yet.</p>}
      </section>
    </div>
  );
}
