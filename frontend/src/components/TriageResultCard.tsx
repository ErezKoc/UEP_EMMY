import type { TriageAssessment, TriageLevel } from "../types";

const LEVEL_STYLES: Record<TriageLevel, { container: string; dot: string; label: string }> = {
  red: {
    container: "border-rose-300 bg-rose-50",
    dot: "bg-rose-500",
    label: "text-rose-800",
  },
  amber: {
    container: "border-amber-300 bg-amber-50",
    dot: "bg-amber-500",
    label: "text-amber-900",
  },
  green: {
    container: "border-emerald-300 bg-emerald-50",
    dot: "bg-emerald-500",
    label: "text-emerald-900",
  },
  // Deliberately slate, not emerald. This card says "we cannot assess this",
  // and a green card would undo the sentence it is wrapping — an owner reads
  // the colour before the words.
  unassessed: {
    container: "border-slate-300 bg-slate-50",
    dot: "bg-slate-400",
    label: "text-slate-800",
  },
};

export default function TriageResultCard({ triage }: { triage: TriageAssessment }) {
  // A verdict stored before a level existed must not fall through to `green`.
  const styles = LEVEL_STYLES[triage.level] ?? LEVEL_STYLES.unassessed;
  const sources = Array.from(
    new Map(
      triage.fired_rules
        .flatMap((rule) =>
          rule.source_links?.length
            ? rule.source_links
            : rule.sources.map((name) => ({ name, url: "" })),
        )
        .map((source) => [source.url || source.name, source]),
    ).values(),
  );

  return (
    <section className={`rounded-lg border-2 p-6 ${styles.container}`} aria-live="polite">
      <div className="flex items-center gap-3">
        <span className={`h-3 w-3 shrink-0 rounded-full ${styles.dot}`} aria-hidden />
        <h2 className={`text-lg font-bold ${styles.label}`}>{triage.headline}</h2>
      </div>

      {triage.fired_rules.length > 0 && (
        <div className="mt-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Why this result
          </h3>
          <ul className="mt-2 list-disc space-y-2 pl-5 text-sm text-slate-700">
            {triage.fired_rules.map((rule) => (
              <li key={rule.rule_id}>{rule.message}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-4 rounded-lg bg-white/70 p-4">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          What to do now
        </h3>
        <p className="mt-1 text-sm text-slate-700">{triage.advice}</p>
      </div>

      {triage.urgent_care_signs?.length > 0 && (
        <details
          open={triage.level === "red"}
          className="mt-4 rounded-lg border border-rose-200 bg-white/70 px-4 py-3"
        >
          <summary className="cursor-pointer text-sm font-semibold text-rose-700">
            When to get urgent help
            <span className="ml-2 font-normal text-slate-500">
              {triage.urgent_care_signs.length} signs
            </span>
          </summary>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-700">
            {triage.urgent_care_signs.map((sign) => (
              <li key={sign}>{sign}</li>
            ))}
          </ul>
        </details>
      )}

      {triage.care_instructions?.length > 0 && (
        // Open on red: these can carry the poison-control numbers, and an owner
        // in an emergency should not have to find a disclosure triangle first.
        <details
          open={triage.level === "red"}
          className="mt-3 rounded-lg border border-slate-200 bg-white/70 px-4 py-3"
        >
          <summary className="cursor-pointer text-sm font-semibold text-slate-700">
            {triage.level === "red" ? "What to do right now" : "Care until the appointment"}
          </summary>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-700">
            {triage.care_instructions.map((instruction) => (
              <li key={instruction}>{instruction}</li>
            ))}
          </ul>
        </details>
      )}

      <details className="mt-3 border-t border-slate-200 pt-3">
        <summary className="cursor-pointer text-xs font-medium text-slate-500">
          Sources and limitations
        </summary>
        {sources.length > 0 && (
          <ul className="mt-2 space-y-1 text-xs text-slate-500">
            {sources.map((source) => (
              <li key={source.url || source.name}>
                {source.url ? (
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noreferrer"
                    className="font-medium underline decoration-slate-300 underline-offset-2 hover:text-slate-700"
                  >
                    {source.name}
                  </a>
                ) : (
                  source.name
                )}
              </li>
            ))}
          </ul>
        )}
        <p className="mt-3 text-xs text-slate-500">{triage.disclaimer}</p>
        {!triage.rules_fully_verified && (
          <p className="mt-2 text-xs text-slate-400">
            These rules use published veterinary sources and are awaiting veterinarian review.
          </p>
        )}
      </details>
    </section>
  );
}
