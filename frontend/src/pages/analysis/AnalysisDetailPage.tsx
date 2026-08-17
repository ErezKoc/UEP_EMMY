import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { ApiError, getAnalysis } from "../../api/client";
import AnalysisCard from "../../components/AnalysisCard";
import TriageResultCard from "../../components/TriageResultCard";
import { ArrowLeftIcon, Badge, Button, Card, Spinner } from "../../components/ui";
import { capitalize } from "../../lib/format";
import type { AnalysisDetail, AnalysisResponse, SymptomIntake } from "../../types";

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

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
                <div>
                  <dt className="text-xs font-medium uppercase text-slate-500">Model version</dt>
                  <dd className="mt-1 text-sm text-slate-700">{analysis.result.model_version}</dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase text-slate-500">Analysis ID</dt>
                  <dd className="mt-1 break-all font-mono text-xs text-slate-500">{analysis.id}</dd>
                </div>
              </dl>
            </div>
          </section>

          {analysis.triage && <TriageResultCard triage={analysis.triage} />}
          <AnalysisCard analysis={analysisResponse} />
          {analysis.intake && <IntakeDetails intake={analysis.intake} />}
        </div>
      )}
    </div>
  );
}
