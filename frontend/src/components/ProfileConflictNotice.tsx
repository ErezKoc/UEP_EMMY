import { Link } from "react-router-dom";
import { AlertTriangleIcon, QuestionCircleIcon } from "./ui";
import type { ProfileConflict } from "../types";

const FIELD_LABEL: Record<ProfileConflict["field"], string> = {
  species: "Species",
  breed: "Breed",
  age: "Age",
};

/*
 * "These two disagree", never "the AI found an error".
 *
 * The app holds two accounts of what an animal is — what the owner wrote down
 * and what a classifier saw in one photograph — and it cannot know which is
 * right. The profile may be a guess about a rescue; the model's accuracy, as
 * the line under every result says, has never been measured. So this panel
 * puts both claims side by side and offers both exits, and the one thing it
 * never does is tell somebody their pet is not the breed they think it is.
 *
 * The severity split is about consequence, not confidence. A species mismatch
 * changes what the symptom checker does; a breed mismatch changes nothing at
 * all and will happen forever with a mixed-breed rescue. Drawing them the same
 * way would teach owners to dismiss the panel, and the species one is the
 * whole reason it exists.
 */
export default function ProfileConflictNotice({
  conflicts,
  petName,
  petId,
  analysisId,
  onCorrect,
  className = "",
}: {
  conflicts: ProfileConflict[];
  petName: string;
  /** Set when the pet still exists, so "check the profile" can lead there. */
  petId?: string | null;
  /** Set on pages that are not the analysis itself, to link back to it. */
  analysisId?: string | null;
  /** Set on the analysis's own page, where correcting happens in place. */
  onCorrect?: () => void;
  className?: string;
}) {
  if (conflicts.length === 0) return null;

  const serious = conflicts.some((item) => item.severity === "high");

  return (
    <section
      // `alert` only for the serious ones. A screen reader interrupting
      // somebody to say a Labrador might be a mixed breed is the audible
      // version of crying wolf.
      role={serious ? "alert" : undefined}
      className={`rounded-xl border p-4 ${
        serious ? "border-amber-300 bg-amber-50" : "border-slate-200 bg-slate-50"
      } ${className}`}
    >
      <div className="flex items-start gap-3">
        <span className={serious ? "text-amber-700" : "text-slate-500"}>
          {serious ? (
            <AlertTriangleIcon className="h-5 w-5" />
          ) : (
            <QuestionCircleIcon className="h-5 w-5" />
          )}
        </span>
        <div className="min-w-0 flex-1">
          <h3
            className={`text-sm font-bold ${serious ? "text-amber-900" : "text-slate-800"}`}
          >
            {/*
              Counted, and named as a disagreement. "2 problems found" would be
              claiming we know something is wrong; we know only that two
              records do not match.
            */}
            {conflicts.length === 1
              ? `This result does not match ${petName}'s profile`
              : `This result does not match ${petName}'s profile in ${conflicts.length} ways`}
          </h3>
          <p className={`mt-1 text-xs ${serious ? "text-amber-900/80" : "text-slate-600"}`}>
            We cannot tell which is right — a profile can hold a guess, and the photo
            analysis has never had its accuracy measured. Both are shown so you can decide.
          </p>

          <ul className="mt-3 space-y-3">
            {conflicts.map((conflict) => (
              <li
                key={conflict.field}
                className="rounded-lg bg-white p-3 ring-1 ring-slate-200"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-bold uppercase tracking-wide text-slate-500">
                    {FIELD_LABEL[conflict.field]}
                  </span>
                  {conflict.severity === "high" ? (
                    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-900">
                      Worth checking now
                    </span>
                  ) : (
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
                      Common, worth a look
                    </span>
                  )}
                </div>

                {/*
                  The two claims as a pair, with the labels naming their
                  sources. A reader scanning this needs to see instantly which
                  half came from them and which from the app.
                */}
                <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                  <div>
                    <dt className="text-xs text-slate-500">Profile says</dt>
                    <dd className="text-sm font-semibold text-slate-800">
                      {conflict.profile_says}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">
                      {conflict.from_correction ? "You corrected it to" : "This analysis says"}
                    </dt>
                    <dd className="text-sm font-semibold text-slate-800">
                      {conflict.analysis_says}
                    </dd>
                  </div>
                </dl>

                <p className="mt-2 text-xs leading-relaxed text-slate-600">
                  {conflict.message}
                </p>
              </li>
            ))}
          </ul>

          {/*
            Both exits, side by side and equally weighted. Offering only "fix
            the analysis" would be assuming the profile is right, and offering
            only "edit the profile" would be assuming the opposite — and this
            component's whole claim is that it does not know.
          */}
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            {onCorrect && (
              <button
                type="button"
                onClick={onCorrect}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 font-semibold text-slate-700 hover:bg-slate-50"
              >
                Correct this analysis
              </button>
            )}
            {analysisId && !onCorrect && (
              <Link
                to={`/analysis/${analysisId}`}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 font-semibold text-slate-700 hover:bg-slate-50"
              >
                Correct this analysis
              </Link>
            )}
            {petId && (
              <Link
                to={`/pets/${petId}`}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 font-semibold text-slate-700 hover:bg-slate-50"
              >
                Check {petName}&apos;s profile
              </Link>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
