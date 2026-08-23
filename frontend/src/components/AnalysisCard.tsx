import type { AnalysisResponse } from "../types";
import { capitalize, formatPercent, formatYearsRange } from "../lib/format";

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
          <p className="text-xs text-slate-400">model {result.model_version}</p>
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
          <dd className="text-xs text-slate-500">
            {formatPercent(result.species_confidence)} confidence
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
            {formatYearsRange(result.age_estimate.min_years, result.age_estimate.max_years)} ·{" "}
            {formatPercent(result.age_estimate.confidence)} confidence
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
              <div className="mb-1 flex items-baseline justify-between text-sm">
                <span className="font-medium text-slate-700">{candidate.breed}</span>
                <span className="text-slate-500">{formatPercent(candidate.confidence)}</span>
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

      <p className="mt-5 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
        AI estimates are informational only and not a substitute for a veterinary examination.
      </p>
    </section>
  );
}
