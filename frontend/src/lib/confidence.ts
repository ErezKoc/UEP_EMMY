/**
 * How sure the model was, in words.
 *
 * The results page used to show "91% confidence" and "model mock-1.4.0" and
 * leave the reader to make of that what they could. Both are worse than they
 * look:
 *
 * - A percentage invites the reading "this is right 91% of the time", which is
 *   a claim about the model's measured accuracy. Nobody has measured it. The
 *   number is how strongly one photo matched, and those are different things.
 * - A model version is an answer to a question a pet owner did not ask. It
 *   belongs in a support conversation, not above a photo of their dog.
 *
 * So the band is the headline and the figure is kept underneath it, in small
 * text, for anyone who wants it. Nothing is hidden — it is ordered.
 */

export type ConfidenceBand = "very-likely" | "likely" | "possible" | "uncertain";

interface BandStyle {
  /** The word an owner reads first. */
  label: string;
  /** Tailwind classes for the pill. */
  pill: string;
}

const BANDS: Record<ConfidenceBand, BandStyle> = {
  "very-likely": { label: "Very likely", pill: "bg-emerald-100 text-emerald-900" },
  likely: { label: "Likely", pill: "bg-sky-100 text-sky-900" },
  possible: { label: "Possible", pill: "bg-amber-100 text-amber-900" },
  // Not "low confidence": that names our internal state. This names what it
  // means for the owner, which is that the answer may simply be wrong.
  uncertain: { label: "Uncertain", pill: "bg-slate-200 text-slate-700" },
};

/*
 * The cut-offs are ours, not the model's, and they are round numbers chosen to
 * separate "I would act on this" from "I would check this" from "ignore this".
 * No source calibrates them, which is exactly why the explanation below never
 * claims the bands mean anything about how often the app is right.
 */
export function bandFor(confidence: number): ConfidenceBand {
  if (confidence >= 0.85) return "very-likely";
  if (confidence >= 0.65) return "likely";
  if (confidence >= 0.45) return "possible";
  return "uncertain";
}

export function confidenceLabel(confidence: number): string {
  return BANDS[bandFor(confidence)].label;
}

export function confidencePill(confidence: number): string {
  return BANDS[bandFor(confidence)].pill;
}

/** The one sentence that stops the band being read as an accuracy rate. */
export const CONFIDENCE_EXPLANATION =
  "These words describe how strongly the photo matched what the app was trained on. " +
  "They are not a measure of how often it turns out to be right, and nobody has measured that.";
