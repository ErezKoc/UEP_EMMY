import { Link } from "react-router-dom";
import { AlertTriangleIcon, CheckCircleIcon, ClockIcon } from "./ui";
import { formatDate } from "../lib/format";
import type { DashboardTask } from "../types";

const STYLE: Record<
  DashboardTask["severity"],
  { panel: string; chip: string; icon: (props: { className?: string }) => React.ReactNode }
> = {
  urgent: {
    panel: "border-rose-200 bg-rose-50",
    chip: "bg-rose-100 text-rose-800",
    icon: AlertTriangleIcon,
  },
  soon: {
    panel: "border-amber-200 bg-amber-50",
    chip: "bg-amber-100 text-amber-900",
    icon: ClockIcon,
  },
  info: {
    panel: "border-slate-200 bg-white",
    chip: "bg-slate-100 text-slate-600",
    icon: ClockIcon,
  },
};

const SEVERITY_WORD: Record<DashboardTask["severity"], string> = {
  urgent: "Needs you now",
  soon: "Has a deadline",
  info: "Worth knowing",
};

/*
 * What needs doing, in the order it needs doing.
 *
 * The ranking is the server's, not this component's, and deliberately so: the
 * same overdue reminder must not read as urgent here and routine on the
 * calendar. All this does is draw it.
 *
 * Only "urgent" is styled red, and only three things can be urgent — a recent
 * red symptom check, and a suggested appointment time waiting on an answer.
 * Everything else is amber or plain. A dashboard where every row shouts is a
 * dashboard nobody reads, and the cost of that is the one red row scrolling
 * past unnoticed.
 */
export default function UrgentTasks({ tasks }: { tasks: DashboardTask[] }) {
  if (tasks.length === 0) {
    return (
      <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4">
        <p className="flex items-center gap-2 text-sm font-medium text-emerald-900">
          <CheckCircleIcon className="h-5 w-5" />
          Nothing needs your attention.
        </p>
        <p className="mt-1 text-xs text-emerald-900/80">
          No overdue care, no appointments waiting on an answer, and no recent symptom
          check that asked for a vet.
        </p>
      </section>
    );
  }

  const urgent = tasks.filter((task) => task.severity === "urgent").length;

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-bold text-slate-800">Needs you</h2>
        <p className="text-xs text-slate-500">
          {urgent > 0
            ? `${urgent} needing attention now, ${tasks.length - urgent} other${
                tasks.length - urgent === 1 ? "" : "s"
              }`
            : `${tasks.length} thing${tasks.length === 1 ? "" : "s"} to keep an eye on`}
        </p>
      </div>

      <ul className="mt-3 space-y-2">
        {tasks.map((task, index) => {
          const style = STYLE[task.severity];
          const Icon = style.icon;
          return (
            <li key={`${task.kind}-${task.pet_name ?? ""}-${index}`}>
              <Link
                to={task.link}
                className={`flex items-start gap-3 rounded-xl border p-3 transition hover:shadow-sm ${style.panel}`}
              >
                <span className="mt-0.5 text-slate-500">
                  <Icon className="h-4 w-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-slate-800">{task.title}</span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-semibold ${style.chip}`}
                    >
                      {SEVERITY_WORD[task.severity]}
                    </span>
                  </span>
                  <span className="mt-0.5 block text-xs leading-relaxed text-slate-600">
                    {task.detail}
                    {/*
                      The date is repeated here rather than only inside the
                      sentence, because a list scanned quickly is scanned for
                      dates.
                    */}
                    {task.due ? ` · ${formatDate(task.due)}` : ""}
                  </span>
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
