import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { ApiError, getAnalysis } from "../../api/client";
import AnalysisCard from "../../components/AnalysisCard";
import AnalysisControls from "../../components/AnalysisControls";
import TriageResultCard from "../../components/TriageResultCard";
import { ArrowLeftIcon, Badge, Button, Card, Spinner } from "../../components/ui";
import { capitalize, formatDateTime } from "../../lib/format";
import type { AnalysisDetail, AnalysisResponse, SymptomIntake } from "../../types";

// Was formatting in the reader's locale while the page around it is
// English. `formatDateTime` uses the app's one locale, like everything else.
const formatTimestamp = formatDateTime;

const FRIENDLY_VALUES: Record<string, string> = {
  h12_to_24h: "12 to 24 hours",
  under_12h: "Under 12 hours",
  over_24h: "Over 24 hours",
  days_2_7: "2 to 7 days",
  weeks_1_4: "1 to 4 weeks",
  over_month: "Over a month",
};

function humanize(value: string): string {
  const friendly = FRIENDLY_VALUES[value];
  if (friendly) return friendly;
  const spaced = value.replaceAll("_", " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function IntakeDetails({ intake }: { intake: SymptomIntake }) {
  const rows = [
    ["Main concern", humanize(intake.concern)],
    ["Body area", intake.body_area ? humanize(intake.body_area) : null],
    ["Duration", intake.duration ? humanize(intake.duration) : null],
    ["Trend", intake.trend ? humanize(intake.trend) : null],
    ["Time since eating", intake.time_since_eating ? humanize(intake.time_since_eating) : null],
    ["How much it bothers them", intake.itch_level ? humanize(intake.itch_level) : null],
    ["How widespread", intake.skin_spread ? humanize(intake.skin_spread) : null],
    [
      "Chronic illness",
      intake.has_chronic_illness == null ? null : intake.has_chronic_illness ? "Yes" : "No",
    ],
    [
      "Putting weight on limb",
      intake.weight_bearing == null ? null : intake.weight_bearing ? "Yes" : "No",
    ],
  ].filter((row): row is [string, string] => row[1] !== null);

  return (
    <Card title="Reported symptoms" description="The answers recorded before this photo was analyzed.">
      <dl className="mt-5 grid gap-4 sm:grid-cols-2">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs font-medium uppercase text-slate-500">{label}</dt>
            <dd className="mt-1 text-sm font-medium text-slate-800">{value}</dd>
          </div>
        ))}
      </dl>
      {intake.red_flags.length > 0 && (
        <div className="mt-5 border-t border-slate-200 pt-4">
          <h3 className="text-xs font-medium uppercase text-slate-500">Reported warning signs</h3>
          <ul className="mt-2 flex flex-wrap gap-2">
            {intake.red_flags.map((flag) => (
              <li key={flag}>
                <Badge variant="danger">{humanize(flag)}</Badge>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

export default function AnalysisDetailPage() {
  const { analysisId } = useParams();
  const location = useLocation();
  const requestedReturn = (location.state as { from?: string } | null)?.from;
  const returnTo = requestedReturn?.startsWith("/analysis/history")
    ? requestedReturn
    : "/analysis/history";

  const [analysis, setAnalysis] = useState<AnalysisDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadAnalysis = useCallback(async () => {
    if (!analysisId) return;
    setIsLoading(true);
    setLoadError(null);
    try {
      setAnalysis(await getAnalysis(analysisId));
    } catch (error) {
      setLoadError(error instanceof ApiError ? error.message : "Could not load this analysis.");
    } finally {
      setIsLoading(false);
    }
  }, [analysisId]);

  useEffect(() => {
    void loadAnalysis();
  }, [loadAnalysis]);

  const analysisResponse: AnalysisResponse | null = analysis
    ? {
        analysis_id: analysis.id,
        animal_id: analysis.animal?.id ?? null,
        image_url: analysis.image_url,
        created_at: analysis.created_at,
        result: analysis.result,
        triage: analysis.triage,
      }
    : null;

  return (
    <div className="mx-auto max-w-3xl">
      <Link
        to={returnTo}
        className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-primary-600 hover:text-primary-700"
      >
        <ArrowLeftIcon className="h-4 w-4" />
        Back to analysis history
      </Link>

      {isLoading && <div className="flex justify-center py-20"><Spinner /></div>}

      {!isLoading && loadError && (
        <div className="rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700" role="alert">
          {loadError}{" "}
          <button onClick={() => void loadAnalysis()} className="font-medium underline">Retry</button>
        </div>
      )}

      {!isLoading && analysis && analysisResponse && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold text-slate-800">Analysis details</h1>
              <p className="mt-1 text-sm text-slate-500">{formatTimestamp(analysis.created_at)}</p>
              {analysis.correction && (
                <Badge variant="primary" className="mt-2">
                  Corrected by you
                </Badge>
              )}
            </div>
            <Link to={analysis.animal ? `/analyze?pet=${analysis.animal.id}` : "/analyze"}>
              <Button variant="secondary">Analyze another photo</Button>
            </Link>
          </div>

          <section className="grid overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200 md:grid-cols-[minmax(0,1.35fr)_minmax(16rem,0.65fr)]">
            <div className="flex min-h-64 items-center justify-center bg-slate-100 p-4">
              <img
                src={analysis.image_url}
                alt={`Analyzed ${analysis.result.species}`}
                className="max-h-[32rem] w-full rounded-lg object-contain"
              />
            </div>
            <div className="p-5">
              <h2 className="text-lg font-semibold text-slate-800">
                {capitalize(analysis.result.species)} analysis
              </h2>
              <dl className="mt-5 space-y-4">
                <div>
                  <dt className="text-xs font-medium uppercase text-slate-500">Linked pet</dt>
                  <dd className="mt-1 text-sm font-medium text-slate-800">
                    {analysis.animal ? (
                      <Link to={`/pets/${analysis.animal.id}`} className="text-primary-600 hover:text-primary-700">
                        {analysis.animal.name}
                      </Link>
                    ) : "Not linked to a pet"}
                  </dd>
                </div>
                {/*
                  The owner's version, where the model's used to be the only
                  version. Shown first and labelled as theirs, with what the app
                  said kept underneath — the record of the prediction is the
                  point of storing this at all, so it is never removed, only
                  demoted.
                */}
                {analysis.correction && (
                  <div>
                    <dt className="text-xs font-medium uppercase text-slate-500">
                      Your correction
                    </dt>
                    <dd className="mt-1 space-y-0.5 text-sm text-slate-800">
                      {analysis.correction.species && (
                        <p>
                          <span className="font-medium">Species:</span>{" "}
                          {capitalize(analysis.correction.species)}{" "}
                          <span className="text-xs text-slate-400">
                            (app said {capitalize(analysis.result.species)})
                          </span>
                        </p>
                      )}
                      {analysis.correction.breed && (
                        <p>
                          <span className="font-medium">Breed:</span> {analysis.correction.breed}{" "}
                          {analysis.result.breed_candidates[0] && (
                            <span className="text-xs text-slate-400">
                              (app said {analysis.result.breed_candidates[0].breed})
                            </span>
                          )}
                        </p>
                      )}
                      {analysis.correction.age_category && (
                        <p>
                          <span className="font-medium">Age:</span>{" "}
                          {capitalize(analysis.correction.age_category)}{" "}
                          <span className="text-xs text-slate-400">
                            (app said {capitalize(analysis.result.age_estimate.category)})
                          </span>
                        </p>
                      )}
                      {analysis.correction.note && (
                        <p className="mt-1 text-sm italic text-slate-600">
                          &ldquo;{analysis.correction.note}&rdquo;
                        </p>
                      )}
                    </dd>
                  </div>
                )}
              </dl>

              {/*
                The model version and the record id live here now. Both are real
                and both are occasionally needed — for a support conversation,
                or for somebody checking which build produced a result — but
                neither is something a pet owner opened this page to read, and
                the version string was the first line under the heading.
              */}
              <details className="mt-5 border-t border-slate-100 pt-4">
                <summary className="cursor-pointer text-xs font-medium uppercase tracking-wide text-slate-400 hover:text-slate-600">
                  Technical details
                </summary>
                <dl className="mt-3 space-y-3">
                  <div>
                    <dt className="text-xs font-medium uppercase text-slate-500">Model version</dt>
                    <dd className="mt-1 font-mono text-xs text-slate-500">
                      {analysis.result.model_version}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs font-medium uppercase text-slate-500">Record ID</dt>
                    <dd className="mt-1 break-all font-mono text-xs text-slate-500">
                      {analysis.id}
                    </dd>
                  </div>
                </dl>
              </details>
            </div>
          </section>

          {analysis.triage && <TriageResultCard triage={analysis.triage} />}
          <AnalysisCard analysis={analysisResponse} />
          {analysis.intake && <IntakeDetails intake={analysis.intake} />}

          <AnalysisControls analysis={analysis} onChanged={setAnalysis} />
        </div>
      )}
    </div>
  );
}
