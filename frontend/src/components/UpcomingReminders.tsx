import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getReminders } from "../api/client";
import type { Reminder } from "../types";

function nextOccurrence(item: Reminder): Date {
  const due = new Date(`${item.due_date}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  if (due >= today || item.recurrence === "none") return due;
  const next = new Date(due);
  if (item.recurrence === "monthly") {
    next.setFullYear(today.getFullYear(), today.getMonth(), due.getDate());
    if (next < today) next.setMonth(next.getMonth() + 1);
  } else {
    next.setFullYear(today.getFullYear());
    if (next < today) next.setFullYear(next.getFullYear() + 1);
  }
  return next;
}

export default function UpcomingReminders() {
  const [items, setItems] = useState<Reminder[]>([]);
  useEffect(() => { getReminders().then(setItems).catch(() => setItems([])); }, []);
  const upcoming = useMemo(() => [...items].sort((a, b) => +nextOccurrence(a) - +nextOccurrence(b)).slice(0, 3), [items]);

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between"><h2 className="font-bold text-slate-900">Upcoming care</h2><Link to="/calendar" className="text-sm font-semibold text-primary-600">Open calendar →</Link></div>
      {upcoming.length > 0 ? <div className="mt-3 divide-y divide-slate-100">{upcoming.map((item) => {
        const date = nextOccurrence(item);
        const overdue = item.recurrence === "none" && date < new Date(new Date().toDateString());
        return <div key={item.id} className="flex items-center gap-3 py-3"><span className={`h-2.5 w-2.5 rounded-full ${overdue ? "bg-rose-500" : item.reminder_type === "vaccine" ? "bg-emerald-500" : "bg-sky-500"}`} /><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold">{item.animal.name}: {item.title}</p><p className={`text-xs ${overdue ? "font-semibold text-rose-600" : "text-slate-500"}`}>{overdue ? "Overdue · " : ""}{date.toLocaleDateString()}</p></div></div>;
      })}</div> : <p className="mt-3 text-sm text-slate-500">No reminders yet. Add vaccinations or check-ups to your calendar.</p>}
    </section>
  );
}
