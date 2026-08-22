import { useId, useState } from "react";
import type { ReactNode, Ref } from "react";
import {
  AlertTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  QuestionCircleIcon,
} from "./ui";
import { EMERGENCY_SCREEN_FLAGS } from "./SymptomIntakeForm";
import {
  BODY_AREA_LABELS,
  CONCERN_LABELS,
  DURATION_LABELS,
  ITCH_LEVEL_LABELS,
  SIGN_LABELS,
  SKIN_SPREAD_LABELS,
  TIME_SINCE_EATING_LABELS,
  TREND_LABELS,
  labelFor,
} from "../lib/symptomLabels";
import { capitalize } from "../lib/format";
import type {
  ConfidenceDimension,
  ConfidenceKind,
  ConfidenceLevel,
  ConfidenceReport,
  FiredRule,
  SymptomIntake,
  TriageAssessment,
  TriageLevel,
} from "../types";

/*
 * The result card, ordered by what an owner needs first.
 *
 * It used to be ordered by what was easiest to explain: reasoning, then every
 * confidence dimension expanded, then a fifteen-item list of general emergency
 * signs opened automatically on red results, and only then the advice. On a
 * phone that put "contact a vet now" and the button to find one about fifteen
 * hundred pixels below where the page landed. Everything is still here — none
 * of the transparency has been removed — but the order is now urgency,
 * headline, what to do, the button that does it, and then the explanation.
 *
 * The words are chosen on the same principle. An owner reading the first
 * screen is answering three questions — how urgent is this, what do I do, why
 * am I being told this — and none of them are answered by "no emergency
 * trigger was matched in this screening", which describes what our software
 * did rather than what they should do. Implementation language lives inside
 * the disclosures, where somebody who wants it can find it.
 */

interface LevelStyle {
  container: string;
  chip: string;
  label: string;
  /** The urgency in words, so the colour is never the only carrier. */
  word: string;
  Icon: (props: { className?: string }) => ReactNode;
}

const LEVEL_STYLES: Record<TriageLevel, LevelStyle> = {
  red: {
    container: "border-rose-300 bg-rose-50",
    chip: "bg-rose-600 text-white",
    label: "text-rose-900",
    word: "Emergency",
    Icon: AlertTriangleIcon,
  },
  amber: {
    container: "border-amber-300 bg-amber-50",
    chip: "bg-amber-600 text-white",
    label: "text-amber-900",
    // Names the recommendation, and no timeframe. Several amber rules rest on
    // sources that give no timing at all, so any "today" or "within 24 hours"
    // here would be ours rather than theirs.
    word: "Vet visit recommended",
    Icon: ClockIcon,
  },
  green: {
    container: "border-emerald-300 bg-emerald-50",
    chip: "bg-emerald-700 text-white",
    label: "text-emerald-900",
    // Not "all clear", and not "monitor at home" either. The finding is about
    // what this checker did not find in the answers given — which is a much
    // smaller claim than the animal being well, and the label has to be the
    // smaller claim or the colour will be read as the larger one.
    word: "No urgent warning identified",
    Icon: CheckCircleIcon,
  },
  // Deliberately slate, not emerald. This card says "we cannot assess this",
  // and a green card would undo the sentence it is wrapping — an owner reads
  // the colour before the words.
  unassessed: {
    container: "border-slate-300 bg-slate-50",
    chip: "bg-slate-700 text-white",
    label: "text-slate-900",
    word: "Not assessed",
    Icon: QuestionCircleIcon,
  },
};

/*
 * How sure the engine is of its own answer — as separate questions.
 *
 * "What would change this" is computed, not guessed: the backend re-runs the
 * assessment with each unanswered question filled in. And there is no single
 * badge, because the parts routinely disagree — matching our rules exactly says
 * nothing about whether any source states how soon, and an owner reading one
 * averaged word would never learn that. That is also why the section is called
 * "Evidence and review status" rather than "How sure we are": the old name
 * invited exactly the summary judgement the panel exists to refuse.
 */
const KIND_LABELS: Record<ConfidenceKind, string> = {
  match: "Did your answers match a rule?",
  evidence: "What do the published sources support?",
  review: "Has a veterinarian reviewed this rule?",
};

const KIND_ORDER: ConfidenceKind[] = ["match", "evidence", "review"];

const CONFIDENCE_STYLES: Record<ConfidenceKind, Record<ConfidenceLevel, { label: string; pill: string }>> = {
  // Not "Strong": a rule matching completely is a fact about our table, and
  // the word for it must not be the word used for evidence quality below.
  match: {
    high: { label: "Complete", pill: "bg-sky-100 text-sky-900" },
    moderate: { label: "Partial", pill: "bg-amber-100 text-amber-900" },
    low: { label: "No match", pill: "bg-slate-200 text-slate-700" },
    not_assessed: { label: "Not assessed", pill: "bg-slate-100 text-slate-500" },
  },
  evidence: {
    high: { label: "Strong", pill: "bg-emerald-100 text-emerald-800" },
    moderate: { label: "Partial", pill: "bg-amber-100 text-amber-900" },
    // "None" is a finding about the sources: we asked and they do not say.
    low: { label: "None", pill: "bg-slate-200 text-slate-700" },
    // This is a finding about us: the question was never in scope for the rule
    // that answered, so nothing was searched for and nothing is missing. On a
    // red urinary result those read very differently, and the badge is the part
    // an owner takes in.
    not_assessed: { label: "Not assessed", pill: "bg-slate-100 text-slate-500" },
  },
  review: {
    high: { label: "Signed off", pill: "bg-emerald-100 text-emerald-800" },
    moderate: { label: "In progress", pill: "bg-amber-100 text-amber-900" },
    low: { label: "Not yet reviewed", pill: "bg-amber-100 text-amber-900" },
    not_assessed: { label: "Not assessed", pill: "bg-slate-100 text-slate-500" },
  },
};

/** Defaulted, because a check stored before the kinds existed carries none. */
function kindOf(entry: ConfidenceDimension): ConfidenceKind {
  return entry.kind && KIND_LABELS[entry.kind] ? entry.kind : "evidence";
}

/** Shared chrome so every disclosure on the card has the same target size. */
function Disclosure({
  summary,
  count,
  countLabel,
  open,
  onToggle,
  tone = "slate",
  children,
}: {
  summary: string;
  count?: number;
  /** Spoken form of the count, e.g. "15 listed". */
  countLabel?: string;
  open?: boolean;
  onToggle?: (open: boolean) => void;
  tone?: "slate" | "rose";
  children: ReactNode;
}) {
  const border = tone === "rose" ? "border-rose-200" : "border-slate-200";
  const text = tone === "rose" ? "text-rose-800" : "text-slate-700";
  return (
    <details
      className={`mt-3 rounded-lg border ${border} bg-white/70 px-4`}
      open={open}
      onToggle={(event) => onToggle?.((event.currentTarget as HTMLDetailsElement).open)}
    >
      <summary
        className={`flex min-h-11 cursor-pointer items-center gap-2 py-3 text-sm font-semibold ${text} focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600`}
      >
        <span>{summary}</span>
        {count !== undefined && (
          <>
            {/*
              Two renderings of one number. Left as a bare sibling span the
              count joined the label in the accessible name — "Other reasons to
              seek urgent help15" — so the spoken version is spelled out and the
              visible pill is hidden from assistive technology.
            */}
            <span className="sr-only">({countLabel ?? `${count} listed`})</span>
            <span
              aria-hidden
              className="rounded-full bg-slate-200/70 px-2 py-0.5 text-xs font-normal text-slate-600"
            >
              {count}
            </span>
          </>
        )}
      </summary>
      <div className="pb-4">{children}</div>
    </details>
  );
}

function SourceLinks({ sources }: { sources: Array<{ name: string; url: string }> }) {
  return (
    <>
      {sources.map((source, index) => (
        <span key={source.url || source.name}>
          {index > 0 && "; "}
          {source.url ? (
            <a
              href={source.url}
              target="_blank"
              rel="noreferrer"
              className="underline decoration-slate-300 underline-offset-2 hover:text-slate-700"
            >
              {source.name}
            </a>
          ) : (
            source.name
          )}
        </span>
      ))}
    </>
  );
}

/*
 * Reasons that rest on the same publication, gathered under one citation.
 *
 * Two rules from the same VCA page produced two bullets each trailing the same
 * link, which reads as two independent findings and doubles the citation noise
 * in the first thing an owner looks at. The claims stay separate and unedited;
 * only the attribution is said once.
 */
function groupBySources(rules: FiredRule[]): Array<{
  key: string;
  messages: Array<{ id: string; text: string }>;
  sources: Array<{ name: string; url: string }>;
}> {
  const groups = new Map<string, ReturnType<typeof groupBySources>[number]>();
  for (const rule of rules) {
    const sources = rule.source_links?.length
      ? rule.source_links
      : (rule.sources ?? []).map((name) => ({ name, url: "" }));
    const key = sources.map((source) => source.url || source.name).join("|");
    const existing = groups.get(key);
    if (existing) existing.messages.push({ id: rule.rule_id, text: rule.message });
    else {
      groups.set(key, {
        key,
        messages: [{ id: rule.rule_id, text: rule.message }],
        sources,
      });
    }
  }
  return [...groups.values()];
}

/*
 * What the owner told us, played back.
 *
 * A confirmation summary and nothing more: every line is an answer they gave,
 * none of it is interpreted, and a question they skipped is either absent or
 * marked as skipped rather than filled in with a guess. Built defensively
 * because it also renders for checks saved months ago, whose intake may be
 * missing fields that exist today.
 */
function AnswerSummary({
  answers,
  petLabel,
}: {
  answers: SymptomIntake;
  petLabel?: string | null;
}) {
  const flags = answers.red_flags ?? [];
  const emergency = new Set<string>(EMERGENCY_SCREEN_FLAGS);
  const reportedEmergency = flags.filter((flag) => emergency.has(flag));
  const otherSigns = flags.filter((flag) => !emergency.has(flag));

  const rows: Array<{ term: string; value: string }> = [];
  const add = (term: string, value: string | null | undefined) => {
    if (value) rows.push({ term, value });
  };

  add("Pet", petLabel || (answers.species ? capitalize(answers.species) : null));
  add("Main concern", labelFor(CONCERN_LABELS, answers.concern));

  // Always shown, because "none selected" is the answer that matters most and
  // its absence is the thing a reader would most wrongly assume.
  rows.push({
    term: "Emergency warning signs",
    value: reportedEmergency.length
      ? reportedEmergency.map((flag) => SIGN_LABELS[flag] ?? flag).join(", ")
      : answers.emergency_screen_answered
        ? "None selected"
        : "Not answered",
  });

  add("Other signs reported", otherSigns.map((flag) => SIGN_LABELS[flag] ?? flag).join(", "));
  add("Where on the body", labelFor(BODY_AREA_LABELS, answers.body_area));
  add("How long", labelFor(DURATION_LABELS, answers.duration));
  add("Since it started", labelFor(TREND_LABELS, answers.trend));
  add(
    "Can put weight on the leg",
    answers.weight_bearing == null ? null : answers.weight_bearing ? "Yes" : "No",
  );
  add("How much it bothers them", labelFor(ITCH_LEVEL_LABELS, answers.itch_level));
  add("How widespread", labelFor(SKIN_SPREAD_LABELS, answers.skin_spread));
  add("Time since last ate", labelFor(TIME_SINCE_EATING_LABELS, answers.time_since_eating));
  add(
    "Long-term illness",
    answers.has_chronic_illness == null ? null : answers.has_chronic_illness ? "Yes" : "No",
  );

  return (
    <>
      <dl className="space-y-2 text-sm">
        {rows.map((row) => (
          <div key={row.term} className="flex flex-wrap gap-x-2">
            <dt className="font-medium text-slate-600">{row.term}:</dt>
            <dd className="text-slate-800">{row.value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs text-slate-500">
        This is a record of what you selected, not an assessment of your pet.
      </p>
    </>
  );
}

function ConfidenceSection({ confidence }: { confidence: ConfidenceReport }) {
  // Optional-chained: a check stored before dimensions existed has none.
  const dimensions = confidence.dimensions ?? [];
  const groups = KIND_ORDER.map((kind) => ({
    kind,
    entries: dimensions.filter((entry) => kindOf(entry) === kind),
  })).filter((group) => group.entries.length > 0);

  return (
    <div>
      <p className="text-xs text-slate-500">
        Three separate questions, and they often disagree. Strong support from published sources
        and review by a veterinarian are not the same thing: a rule can rest on good published
        guidance and still have had no veterinarian check it.
      </p>

      {groups.map((group) => (
        <div key={group.kind} className="mt-3">
          <h4 className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
            {KIND_LABELS[group.kind]}
          </h4>
          <dl className="mt-1 space-y-2">
            {group.entries.map((entry) => {
              const style =
                CONFIDENCE_STYLES[group.kind][entry.level] ?? CONFIDENCE_STYLES.evidence.low;
              return (
                <div key={entry.name} className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                  <dt className="text-sm font-medium text-slate-700">{entry.name}</dt>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${style.pill}`}
                  >
                    {style.label}
                  </span>
                  <dd className="w-full text-sm text-slate-600">{entry.detail}</dd>
                </div>
              );
            })}
          </dl>
        </div>
      ))}

      {confidence.would_change_the_answer?.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-semibold text-slate-600">
            Answering these would change this result:
          </p>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-700">
            {confidence.would_change_the_answer.map((question) => (
              <li key={question}>{question}</li>
            ))}
          </ul>
        </div>
      )}

      {confidence.based_on?.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-semibold text-slate-600">What this rests on:</p>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-slate-500">
            {/* Filtered: an empty string would render as a bare bullet. */}
            {confidence.based_on.filter(Boolean).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

interface TriageResultCardProps {
  triage: TriageAssessment;
  /*
   * The next thing to do, rendered immediately under the advice. Supplied by
   * the page rather than built in, because "find a vet" is a route this
   * component should not know about — and because the history page renders
   * this card for a check from last week, where there is no next action.
   */
  actions?: ReactNode;
  /** Repeated at the foot of long results so the action is never scrolled off. */
  repeatActions?: ReactNode;
  /** The intake behind this verdict, played back under "Your answers". */
  answers?: SymptomIntake | null;
  /** The linked pet's name, where there is one. */
  petLabel?: string | null;
  headingRef?: Ref<HTMLHeadingElement>;
  /*
   * Announce the verdict to assistive technology. Off by default: the history
   * page renders one of these per row, and a live region per row would read
   * the whole list aloud on load.
   */
  announce?: boolean;
}

export default function TriageResultCard({
  triage,
  actions,
  repeatActions,
  answers,
  petLabel,
  headingRef,
  announce = false,
}: TriageResultCardProps) {
  const baseId = useId();
  const detailsId = `${baseId}-details`;
  const [sourcesOpen, setSourcesOpen] = useState(false);

  // A verdict stored before a level existed must not fall through to `green`.
  const styles = LEVEL_STYLES[triage.level] ?? LEVEL_STYLES.unassessed;
  const { Icon } = styles;
  const isRed = triage.level === "red";

  const reasonGroups = groupBySources(triage.fired_rules ?? []);

  const sources = Array.from(
    new Map(
      (triage.fired_rules ?? [])
        .flatMap((rule) =>
          rule.source_links?.length
            ? rule.source_links
            : (rule.sources ?? []).map((name) => ({ name, url: "" })),
        )
        .map((source) => [source.url || source.name, source]),
    ).values(),
  );

  return (
    <section className={`rounded-lg border-2 p-5 sm:p-6 ${styles.container}`}>
      {/*
        A short spoken summary, separate from the visible card. Marking the card
        itself as a live region would have a screen reader read every citation
        and disclosure label the moment the result appeared; this says the three
        things that matter and stops.
      */}
      {announce && (
        <p className="sr-only" role={isRed ? "alert" : "status"}>
          {styles.word}. {triage.headline}. {triage.advice}
        </p>
      )}

      {/* ------------------------------------------------ urgency + headline */}
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wide ${styles.chip}`}
        >
          <Icon className="h-4 w-4" />
          {styles.word}
        </span>
      </div>

      <h2
        ref={headingRef}
        tabIndex={-1}
        className={`mt-3 text-xl font-bold sm:text-2xl ${styles.label} focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary-600`}
      >
        {triage.headline}
      </h2>

      {/* ------------------------------------------------------ what to do now */}
      <div className="mt-4 rounded-lg bg-white/80 p-4">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          What to do now
        </h3>
        <p className="mt-1 text-sm text-slate-800">{triage.advice}</p>
        {actions && <div className="mt-4">{actions}</div>}
      </div>

      {/*
        Immediate actions stay open on red — these can carry the poison-control
        numbers, and an owner in an emergency should not have to find a
        disclosure triangle first.
      */}
      {triage.care_instructions?.length > 0 &&
        (isRed ? (
          <div className="mt-3 rounded-lg border border-rose-200 bg-white/70 p-4">
            <h3 className="text-sm font-semibold text-rose-800">What to do right now</h3>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
              {triage.care_instructions.map((instruction) => (
                <li key={instruction}>{instruction}</li>
              ))}
            </ul>
          </div>
        ) : (
          <Disclosure summary="Care until the appointment">
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
              {triage.care_instructions.map((instruction) => (
                <li key={instruction}>{instruction}</li>
              ))}
            </ul>
          </Disclosure>
        ))}

      {/* ---------------------------------------------------- why this result */}
      {reasonGroups.length > 0 && (
        <div className="mt-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Why this result
          </h3>
          <ul className="mt-2 space-y-3 text-sm text-slate-700">
            {reasonGroups.map((group) => (
              <li key={group.key}>
                <ul className="list-disc space-y-1 pl-5">
                  {group.messages.map((message) => (
                    <li key={message.id}>{message.text}</li>
                  ))}
                </ul>
                {group.sources.length > 0 && (
                  <p className="mt-1 pl-5 text-xs text-slate-500">
                    {group.sources.length > 1 ? "Sources: " : "Source: "}
                    <SourceLinks sources={group.sources} />
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/*
        The screening result, after the action rather than before the reasoning.
        It is a restatement of the owner's own answers, which matters — but not
        more than what to do about them.
      */}
      {triage.screening_note && (
        <p className="mt-4 rounded-lg border border-slate-200 bg-white/60 p-3 text-sm text-slate-600">
          {triage.screening_note}
        </p>
      )}

      {/*
        Green is the one verdict that could be mistaken for a clean bill of
        health, so the limit of the claim is stated on the card rather than
        left inside a closed panel.
      */}
      {triage.level === "green" && (
        <p className="mt-3 rounded-lg border border-emerald-200 bg-white/70 p-3 text-xs text-slate-600">
          This means the answers you gave did not match an urgent warning in this checker. It does
          not mean your pet is well, and it is not a diagnosis. {triage.disclaimer}
        </p>
      )}

      {/*
        The provenance of the whole card, as two plain facts rather than a row
        of labels separated by middots. "Not yet reviewed by a veterinarian" is
        the sentence this product is least entitled to soften, so it is written
        out in full and never abbreviated into a badge.
      */}
      <div className="mt-4 rounded-lg border border-slate-200 bg-white/60 p-3 text-xs text-slate-600">
        <p>Based on published veterinary sources.</p>
        {!triage.rules_fully_verified && (
          <p className="mt-1 font-semibold text-slate-700">
            The checker&rsquo;s rules have not yet been reviewed by a veterinarian.
          </p>
        )}
        <button
          type="button"
          // On its own line, so it can carry a real target height rather than
          // the 16px an inline text link would be.
          className="mt-1 inline-flex min-h-11 items-center underline decoration-slate-400 underline-offset-2 hover:text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600"
          aria-expanded={sourcesOpen}
          aria-controls={detailsId}
          onClick={() => {
            setSourcesOpen(true);
            requestAnimationFrame(() =>
              document.getElementById(detailsId)?.scrollIntoView({ block: "center" }),
            );
          }}
        >
          Read the sources and limitations
        </button>
      </div>

      {/* -------------------------------------------------------- disclosures */}
      {answers && (
        <Disclosure summary="Your answers">
          <AnswerSummary answers={answers} petLabel={petLabel} />
        </Disclosure>
      )}

      {triage.confidence && (
        <Disclosure summary="Evidence and review status">
          <ConfidenceSection confidence={triage.confidence} />
        </Disclosure>
      )}

      {triage.urgent_care_signs?.length > 0 && (
        /*
          Never open, on any level. It used to expand automatically on red,
          where fifteen general emergency signs and their citations sat between
          the advice and the button to act on it — burying the action under a
          list of things that were not what the owner had reported.
        */
        <Disclosure
          tone="rose"
          summary={
            triage.urgent_care_note
              ? "Other reasons to seek urgent help"
              : "When to get urgent help"
          }
          count={triage.urgent_care_signs.length}
          countLabel={`${triage.urgent_care_signs.length} reasons listed`}
        >
          {triage.urgent_care_note && (
            <p className="mb-3 text-xs text-slate-500">{triage.urgent_care_note}</p>
          )}
          <ul className="list-disc space-y-2 pl-5 text-sm text-slate-700">
            {triage.urgent_care_signs.map((sign) => (
              <li key={sign.text}>
                {sign.text}
                {/*
                  Per line, because these are not uniformly sourced: severe pain
                  is Merck's, the gum colour and the seizure are the ASPCA's. One
                  shared list implied a reviewer would find each on either page.
                */}
                {triage.urgent_care_note && sign.sources?.length > 0 && (
                  <span className="mt-0.5 block text-xs text-slate-500">
                    <SourceLinks sources={sign.sources} />
                  </span>
                )}
              </li>
            ))}
          </ul>
        </Disclosure>
      )}

      {triage.what_to_expect && triage.what_to_expect.length > 0 && (
        // Explanation, not instructions — filing these under "Care until the
        // appointment" labelled two sentences about how skin disease is
        // diagnosed as advice on looking after the animal.
        <Disclosure summary="What an examination involves">
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
            {triage.what_to_expect.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </Disclosure>
      )}

      <div id={detailsId}>
        <Disclosure summary="Sources and limitations" open={sourcesOpen} onToggle={setSourcesOpen}>
          {sources.length > 0 && (
            <ul className="space-y-1 text-xs text-slate-500">
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
            <p className="mt-2 text-xs text-slate-500">
              These rules were read from published veterinary sources by the team. No veterinarian
              has signed them off yet.
            </p>
          )}
        </Disclosure>
      </div>

      {/*
        Long results scroll the action out of reach. Repeating it costs one row
        and means the owner never has to scroll back up to act.
      */}
      {repeatActions && (
        <div className="mt-5 border-t border-slate-200/70 pt-4">{repeatActions}</div>
      )}
    </section>
  );
}
