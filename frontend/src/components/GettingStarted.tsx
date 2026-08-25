import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getAnalyses, getAnimals } from "../api/client";
import { useSession } from "../auth/SessionContext";
import { CameraIcon, CheckIcon, ClockIcon, PawIcon, StethoscopeIcon, XIcon } from "./ui";
import { isSupportedSpecies } from "../lib/species";
import type { Animal } from "../types";

const DISMISSED_KEY = "uep-emmy.getting-started-dismissed";

interface Step {
  id: string;
  title: string;
  description: string;
  href: string;
  cta: string;
  icon: (props: { className?: string }) => React.ReactNode;
  done: boolean;
  /** Set when a step cannot be completed by this account, with the reason. */
  unavailable?: string;
}

/*
 * The first thing a new account sees, instead of four widgets aimed at
 * somebody who already has pets.
 *
 * Every step's completion is DERIVED from data, never stored. A "has added a
 * pet" flag on the user would have to be written at the right moment, would
 * drift the first time somebody deleted their only pet, and would need a
 * migration for the accounts that already exist. Asking "do you have any
 * pets?" is always true, needs no backend change at all, and heals itself.
 *
 * The panel removes itself once everything is done, so it is onboarding rather
 * than furniture.
 */
export default function GettingStarted({ reminderCount }: { reminderCount: number }) {
  const { user } = useSession();
  const [pets, setPets] = useState<Animal[]>([]);
  const [analysisCount, setAnalysisCount] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const [dismissed, setDismissed] = useState(
    () => localStorage.getItem(DISMISSED_KEY) === "true",
  );

  useEffect(() => {
    if (!user || dismissed) return;
    let cancelled = false;

    /*
     * One at a time, on purpose — this used to be `Promise.allSettled` over
     * three parallel calls.
     *
     * A browser opens at most six connections per origin over HTTP/1.1. The
     * dashboard already fires the session check, the notification count, the
     * reminders list and the community feed on mount; three more in parallel
     * took it to seven, and the seventh sat queued in the browser until it hit
     * the request timeout. The community panel is fired last, so it was the one
     * that lost — reported as "no response after 20s" from a server that had
     * never been asked.
     *
     * This panel is secondary to the page's own content, so it takes one
     * connection slot at a time instead of three. Three sequential requests
     * this small are still well under a second, and nothing else has to wait.
     *
     * Each is caught individually: one failing costs that step's tick, not the
     * whole panel. A checklist that vanishes because one call failed is worse
     * than one showing a step as outstanding.
     */
    const check = async () => {
      try {
        const animals = await getAnimals();
        if (!cancelled) setPets(animals);
      } catch {
        /* leave the step outstanding */
      }
      try {
        // One row is enough to answer "has this account analysed anything?".
        const analyses = await getAnalyses(null, 1);
        if (!cancelled) setAnalysisCount(analyses.length);
      } catch {
        /* leave the step outstanding */
      }
      // No reminders call here: the Dashboard already has that list and passes
      // the count in, so this panel costs two requests rather than three.
      if (!cancelled) setLoaded(true);
    };

    void check();

    return () => {
      cancelled = true;
    };
  }, [user, dismissed]);

  if (!user || dismissed || !loaded) return null;

  const hasPets = pets.length > 0;
  // Somebody whose only pets are rabbits cannot complete the analysis step,
  // and a checklist that nags forever at a step the product refuses to perform
  // is worse than no checklist. It is marked unavailable, with the reason.
  const canAnalyse = !hasPets || pets.some((pet) => isSupportedSpecies(pet.species));

  const steps: Step[] = [
    {
      id: "pet",
      title: "Add your pet",
      description:
        "Their profile holds photos, health records and everything below. Any animal — dog, cat, rabbit, bird.",
      href: "/pets",
      cta: "Add a pet",
      icon: PawIcon,
      done: hasPets,
    },
    {
      id: "analysis",
      title: "Try photo analysis",
      description: "Upload a photo and get an estimate of the breed and age.",
      href: "/analyze",
      cta: "Analyze a photo",
      icon: CameraIcon,
      done: analysisCount > 0,
      unavailable: canAnalyse
        ? undefined
        : "Photo analysis covers dogs and cats, so this one is not available for your pets.",
    },
    {
      id: "reminder",
      title: "Set a reminder",
      description:
        "Vaccinations, treatments, check-ups — repeating as often as you need, and we will tell you before each one is due.",
      href: "/calendar",
      cta: "Add a reminder",
      icon: ClockIcon,
      done: reminderCount > 0,
    },
    {
      id: "vet",
      title: "Find a vet",
      description:
        "Contact details, opening hours and out-of-hours numbers — and you can request an appointment. Works for any pet.",
      href: "/vets",
      cta: "Browse vets",
      icon: StethoscopeIcon,
      done: false,
      // Never ticks. Deliberately last and deliberately open-ended: it is the
      // one thing here somebody might need on their first day or their
      // hundredth, and marking it "done" would be claiming something we cannot
      // know. It disappears with the panel once the real steps are finished.
    },
  ];

  const actionable = steps.filter((step) => !step.unavailable && step.id !== "vet");
  const completed = actionable.filter((step) => step.done).length;
  // Once the real steps are done the panel has nothing left to teach.
  if (completed === actionable.length) return null;

  const dismiss = () => {
    localStorage.setItem(DISMISSED_KEY, "true");
    setDismissed(true);
  };

  return (
    <section className="rounded-2xl border border-primary-200 bg-primary-50/50 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          {/*
            No longer greets by name. The dashboard above now opens with
            "Welcome back, Alex", and two greetings stacked one on top of the
            other reads as a page that has been assembled rather than designed.
            The panel keeps the count, which is the part that is its own.
          */}
          <h2 className="text-lg font-bold text-slate-800">Getting started</h2>
          <p className="mt-1 text-sm text-slate-600">
            {/*
              Not "four things": four are listed but only three are counted,
              because "Find a vet" never ticks. Saying a number that disagrees
              with the counter beside it makes the reader distrust both.
            */}
            A few things worth doing first. {completed} of {actionable.length} done.
          </p>
        </div>
        <button
          onClick={dismiss}
          aria-label="Hide the getting started checklist"
          title="Hide this"
          className="rounded-lg p-1.5 text-slate-400 hover:bg-white hover:text-slate-600"
        >
          <XIcon className="h-4 w-4" />
        </button>
      </div>

      <div
        className="mt-3 h-1.5 overflow-hidden rounded-full bg-white"
        role="progressbar"
        aria-valuenow={completed}
        aria-valuemin={0}
        aria-valuemax={actionable.length}
        aria-label="Getting started progress"
      >
        <div
          className="h-full rounded-full bg-primary-600 transition-all"
          style={{ width: `${(completed / actionable.length) * 100}%` }}
        />
      </div>

      <ol className="mt-4 space-y-3">
        {steps.map((step) => {
          const Icon = step.icon;
          return (
            <li
              key={step.id}
              className={`flex items-start gap-3 rounded-xl bg-white p-3 ${
                step.done ? "opacity-60" : ""
              }`}
            >
              <span
                className={`mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${
                  step.done
                    ? "bg-emerald-100 text-emerald-700"
                    : step.unavailable
                      ? "bg-slate-100 text-slate-400"
                      : "bg-primary-100 text-primary-700"
                }`}
              >
                {step.done ? <CheckIcon className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
              </span>

              <div className="min-w-0 flex-1">
                <p
                  className={`text-sm font-semibold text-slate-800 ${
                    step.done ? "line-through decoration-slate-400" : ""
                  }`}
                >
                  {step.title}
                </p>
                <p className="mt-0.5 text-sm leading-relaxed text-slate-600">
                  {step.unavailable ?? step.description}
                </p>
              </div>

              {!step.done && !step.unavailable && (
                <Link
                  to={step.href}
                  className="shrink-0 self-center rounded-lg bg-primary-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-primary-700"
                >
                  {step.cta}
                </Link>
              )}
            </li>
          );
        })}
      </ol>

      <p className="mt-3 text-xs text-slate-500">
        New to all this?{" "}
        <Link to="/new-owner-guide" className="font-medium text-primary-600 hover:text-primary-700">
          Read the new owner guide
        </Link>
        .
      </p>
    </section>
  );
}
