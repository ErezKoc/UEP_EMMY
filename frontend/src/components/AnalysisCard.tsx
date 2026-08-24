import type { AnalysisResponse } from "../types";
import { capitalize, formatYearsRange } from "../lib/format";
import {
  CONFIDENCE_EXPLANATION,
  confidenceLabel,
  confidencePill,
  formatMatchScore,
} from "../lib/confidence";

interface AnalysisCardProps {
  analysis: AnalysisResponse | null;
}

function ConfidenceBar({ value }: { value: number }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
      <div
        className="h-full rounded-full bg-indigo-500"
        style={{ width: `${Math.round(value * 100)}%` }}
      />
    </div>
  );
}

export default function AnalysisCard({ analysis }: AnalysisCardProps) {
  if (!analysis) {
    return (
      <section className="rounded-2xl border border-dashed border-slate-300 bg-white/60 p-6 text-center">
        <h2 className="text-lg font-semibold text-slate-700">Analysis results</h2>
        <p className="mt-2 text-sm text-slate-500">
          Upload a photo above and the AI assessment will appear here.
        </p>
      </section>
    );
  }

  const { result, image_url } = analysis;

  return (
    <section className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-800">Analysis results</h2>
          {/*
            The model version used to sit here. It is an answer to a question a
            pet owner did not ask, and it was the first thing under the heading.
            It is still available — on the analysis's own page, under "Technical
            details" — for the one conversation that needs it.
          */}
          <p className="text-xs text-slate-400">What the app thinks, from the photo</p>
        </div>
        <img
          src={image_url}
          alt="Analyzed pet"
          className="h-16 w-16 rounded-lg object-cover ring-1 ring-slate-200"
        />
      </div>

      <dl className="mt-5 grid grid-cols-2 gap-4">
        <div className="rounded-xl bg-slate-50 p-4">
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Species</dt>
          <dd className="mt-1 text-xl font-semibold text-slate-800">
            {capitalize(result.species)}
          </dd>
          <dd className="mt-1">
            <span
              className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${confidencePill(
                result.species_confidence,
              )}`}
            >
              {confidenceLabel(result.species_confidence)}
            </span>
            {/*
              The figure survives, one size down and after the word. Removing it
              outright would be hiding something an owner is entitled to see;
              leading with it is what made "91%" read as an accuracy rate.
            */}
            <span className="ml-2 text-xs text-slate-400">
              {formatMatchScore(result.species_confidence)} match
            </span>
          </dd>
          {/*
            The confidence figure is a choice BETWEEN dog and cat, not a
            judgement that the photo contains either. The model has two classes,
            so a rabbit, a hamster or a houseplant all come back as one of them
            with a number beside it, and the number is the most convincing part
            of the answer. A pet profile catches this before the upload; an
            unlinked photo has nothing to catch it with, so the card says it.
          */}
          <dd className="mt-2 text-xs leading-relaxed text-slate-400">
            This model chooses between dog and cat only. It will name one of them for any photo,
            including of another animal.
          </dd>
        </div>

        <div className="rounded-xl bg-slate-50 p-4">
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Estimated age
          </dt>
          <dd className="mt-1 text-xl font-semibold text-slate-800">
            {capitalize(result.age_estimate.category)}
          </dd>
          <dd className="text-xs text-slate-500">
            {formatYearsRange(result.age_estimate.min_years, result.age_estimate.max_years)}
          </dd>
          <dd className="mt-1">
            <span
              className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${confidencePill(
                result.age_estimate.confidence,
              )}`}
            >
              {confidenceLabel(result.age_estimate.confidence)}
            </span>
            <span className="ml-2 text-xs text-slate-400">
              {formatMatchScore(result.age_estimate.confidence)} match
            </span>
          </dd>
        </div>
      </dl>

      <div className="mt-5">
        <h3 className="text-xs font-medium uppercase tracking-wide text-slate-500">
          Breed candidates
        </h3>
        <ul className="mt-2 space-y-3">
          {result.breed_candidates.map((candidate) => (
            <li key={candidate.breed}>
              <div className="mb-1 flex flex-wrap items-baseline justify-between gap-x-2 text-sm">
                <span className="font-medium text-slate-700">{candidate.breed}</span>
                <span className="text-xs text-slate-500">
                  {confidenceLabel(candidate.confidence)}{" "}
                  <span className="text-slate-400">
                    ({formatMatchScore(candidate.confidence)} match)
                  </span>
                </span>
              </div>
              <ConfidenceBar value={candidate.confidence} />
            </li>
          ))}
        </ul>
      </div>

      {result.characteristics.length > 0 && (
        <div className="mt-5">
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Observed characteristics
          </h3>
          <ul className="mt-2 flex flex-wrap gap-2">
            {result.characteristics.map((trait) => (
              <li
                key={trait}
                className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700"
              >
                {trait}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/*
        Said once, near the bands rather than buried at the bottom, because a
        reader who has just seen "Strong match" three times needs to know what
        the word is a measurement of before they act on it.
      */}
      <p className="mt-5 text-xs leading-relaxed text-slate-500">{CONFIDENCE_EXPLANATION}</p>

      <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
        AI estimates are informational only and not a substitute for a veterinary examination.
      </p>
    </section>
  );
}
