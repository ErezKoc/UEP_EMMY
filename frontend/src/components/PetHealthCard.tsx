import { Link } from "react-router-dom";
import { Avatar } from "./ui";
import { capitalize, formatAge, formatDate } from "../lib/format";
import type { PetSummary } from "../types";

/*
 * The triage vocabulary, in the owner's words rather than ours.
 *
 * `unassessed` is deliberately not called "unknown" or left blank: the checker
 * abstaining is a real answer that means "go and ask a person", and a blank
 * reads as "nothing found".
 */
const CHECK_STYLE: Record<string, { label: string; className: string }> = {
  red: { label: "Needs a vet now", className: "bg-rose-100 text-rose-800" },
  amber: { label: "Should be seen", className: "bg-amber-100 text-amber-900" },
  green: { label: "Home care was reasonable", className: "bg-emerald-100 text-emerald-800" },
  unassessed: { label: "Could not be assessed", className: "bg-slate-200 text-slate-700" },
};

/** "09:00:00" → "09:00". */
function clock(value: string | null): string {
  return value ? value.slice(0, 5) : "";
}

/*
 * One pet, and the four things an owner actually wants to know about them.
 *
 * Written so that a pet with nothing recorded still gets a card that says
 * something useful. The obvious version of this panel is a wall of empty rows
 * — "no reminders", "no appointments", "no checks" — which is three ways of
 * telling somebody they have not used the app yet. Each row here either
 * carries a fact or is absent, and the card falls back to a single line
 * pointing at the one thing worth doing first.
 */
export default function PetHealthCard({ summary }: { summary: PetSummary }) {
  const { animal } = summary;
  const check = summary.last_check_level
    ? CHECK_STYLE[summary.last_check_level] ?? {
        // A stored verdict from a build that knew a level this one does not.
        label: "Checked",
        className: "bg-slate-200 text-slate-700",
      }
    : null;

  const hasAnything =
    summary.overdue_reminders > 0 ||
    summary.next_reminder_date !== null ||
    summary.next_appointment !== null ||
    check !== null;

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex items-start gap-3">
        <Avatar name={animal.name} src={animal.photo_url} size="md" />
        <div className="min-w-0 flex-1">
          <Link
            to={`/pets/${animal.id}`}
            className="font-semibold text-slate-800 hover:text-primary-600"
          >
            {animal.name}
          </Link>
          <p className="text-xs text-slate-500">
            {[
              capitalize(animal.species),
              animal.breed,
              animal.birth_date ? formatAge(animal.birth_date) : null,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        {summary.overdue_reminders > 0 && (
          <span className="shrink-0 rounded-full bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-800">
            {summary.overdue_reminders} overdue
          </span>
        )}
      </div>

      {check && (
        <p className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <span className={`rounded-full px-2 py-0.5 font-semibold ${check.className}`}>
            {check.label}
          </span>
          <span className="text-slate-500">
            {summary.last_check_headline ?? "Last symptom check"}
            {summary.last_check_at ? ` · ${formatDate(summary.last_check_at)}` : ""}
          </span>
        </p>
      )}

      <dl className="mt-3 space-y-1.5 text-sm">
        {summary.next_appointment && (
          <div className="flex flex-wrap gap-x-2">
            <dt className="font-medium text-slate-600">Next appointment:</dt>
            <dd className="text-slate-800">
              {summary.next_appointment.scheduled_date
                ? formatDate(summary.next_appointment.scheduled_date)
                : "date to confirm"}
              {clock(summary.next_appointment.scheduled_time)
                ? ` at ${clock(summary.next_appointment.scheduled_time)}`
                : ""}{" "}
              <span className="text-slate-500">— {summary.next_appointment.practice}</span>
              {/*
                A date presented as settled while a move is waiting on an answer
                is how somebody turns up on a day that changed.
              */}
              {summary.next_appointment.move_pending && (
                <span className="ml-1 font-medium text-amber-800">
                  (a new time is being discussed)
                </span>
              )}
            </dd>
          </div>
        )}

        {summary.next_reminder_date && (
          <div className="flex flex-wrap gap-x-2">
            <dt className="font-medium text-slate-600">Next due:</dt>
            <dd className="text-slate-800">
              {summary.next_reminder_title} · {formatDate(summary.next_reminder_date)}
            </dd>
          </div>
        )}
      </dl>

      {summary.profile_conflicts > 0 && (
        <p className="mt-2 text-xs text-slate-500">
          The latest photo analysis does not match this profile.{" "}
          <Link to="/analysis/history" className="font-medium text-primary-600">
            Take a look
          </Link>
        </p>
      )}

      {!hasAnything && (
        <p className="mt-3 text-sm text-slate-500">
          Nothing recorded yet.{" "}
          <Link to="/calendar" className="font-medium text-primary-600">
            Add a reminder
          </Link>{" "}
          or{" "}
          <Link to="/symptom-check" className="font-medium text-primary-600">
            check symptoms
          </Link>
          .
        </p>
      )}
    </article>
  );
}
