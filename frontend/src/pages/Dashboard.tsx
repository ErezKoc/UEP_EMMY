import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, getDashboard, getReminders } from "../api/client";
import { useSession } from "../auth/SessionContext";
import AnalysisCard from "../components/AnalysisCard";
import CommunityFeed from "../components/CommunityFeed";
import GettingStarted from "../components/GettingStarted";
import ImageUpload from "../components/ImageUpload";
import PetHealthCard from "../components/PetHealthCard";
import UpcomingReminders from "../components/UpcomingReminders";
import UrgentTasks from "../components/UrgentTasks";
import { CalendarIcon, PawIcon, Spinner } from "../components/ui";
import { formatDate } from "../lib/format";
import type { AnalysisResponse, DashboardData, Reminder } from "../types";

export default function Dashboard() {
  const { user } = useSession();
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  /*
   * One request for the whole page, and one more for the reminders the two
   * panels below share.
   *
   * The per-pet summaries, the task list and the next appointment all come
   * from `/v1/dashboard`. Assembling them here would have meant a call per pet
   * on a page that was already over the browser's six-connection budget — the
   * getting-started checks had been made sequential for exactly that reason.
   * More importantly, "urgent" is a judgement, and it is made once on the
   * server so this page and the calendar cannot disagree about it.
   */
  const [data, setData] = useState<DashboardData | null>(null);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const [dashboard, items] = await Promise.all([getDashboard(), getReminders()]);
      setData(dashboard);
      setReminders(items);
    } catch (reason) {
      setLoadError(
        reason instanceof ApiError ? reason.message : "Could not load your dashboard.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const firstName = user?.display_name.split(" ")[0] ?? "";
  const next = data?.next_appointment ?? null;

  return (
    <div className="space-y-6">
      {/*
        Named, and only on the dashboard. "Welcome back, Alex" on every page
        would be wallpaper; here it is the one place the page is about them.
      */}
      <div>
        <h1 className="text-2xl font-bold text-slate-800">
          {firstName ? `Welcome back, ${firstName}` : "Your pets"}
        </h1>
        {next && (
          <p className="mt-1 text-sm text-slate-600">
            <CalendarIcon className="mr-1 inline h-4 w-4 text-slate-400" />
            Next appointment{next.pet_name ? ` for ${next.pet_name}` : ""}:{" "}
            <span className="font-medium text-slate-800">
              {next.scheduled_date ? formatDate(next.scheduled_date) : "date to confirm"}
              {next.scheduled_time ? ` at ${next.scheduled_time.slice(0, 5)}` : ""}
            </span>{" "}
            at {next.practice}
            {next.move_pending && (
              <span className="ml-1 font-medium text-amber-800">
                — a new time is being discussed
              </span>
            )}
          </p>
        )}
      </div>

      <GettingStarted reminderCount={reminders.length} />

      {loading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {!loading && loadError && (
        <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
          {loadError}{" "}
          <button onClick={() => void load()} className="font-medium underline">
            Retry
          </button>
        </div>
      )}

      {/*
        The task list comes before the pet cards and before the photo upload.
        A dashboard's first screenful should answer "is anything wrong?", and
        the previous one led with a box asking for a photograph.

        Hidden entirely for somebody with no pets: "nothing needs your
        attention" is true but reads as a system with nothing in it, and the
        getting-started checklist above is already telling them what to do.
      */}
      {!loading && !loadError && data && data.pets.length > 0 && (
        <UrgentTasks tasks={data.tasks} />
      )}

      {!loading && !loadError && data && data.pets.length > 0 && (
        <section>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-lg font-bold text-slate-800">
              <PawIcon className="mr-1 inline h-5 w-5 text-slate-400" />
              Your pets
            </h2>
            <Link to="/pets" className="text-sm font-medium text-primary-600">
              Manage pets
            </Link>
          </div>
          <div className="mt-3 grid gap-4 md:grid-cols-2">
            {data.pets.map((summary) => (
              <PetHealthCard key={summary.animal.id} summary={summary} />
            ))}
          </div>
        </section>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <ImageUpload onAnalysisComplete={setAnalysis} />
          <AnalysisCard analysis={analysis} />
          <UpcomingReminders items={reminders} />
        </div>

        <CommunityFeed compact />
      </div>
    </div>
  );
}
