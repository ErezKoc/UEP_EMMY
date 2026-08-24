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

/*
 * The words describe the MATCH, not the odds of being right.
 *
 * These used to read "Very likely", "Likely", "Possible", "Uncertain" — the
 * vocabulary of probability. "Likely" means "probably true", which is a claim
 * about how often the answer turns out to be correct, and the explanation
 * printed underneath says in so many words that nobody has measured that. The
 * label and the disclaimer were arguing with each other, and a reader is
 * entitled to conclude that one of them is untrue.
 *
 * "Strong match" makes exactly the claim the number supports: this photo looked
 * a lot like the training data. Whether that means the breed is right is a
 * different question, and one this app cannot answer yet.
 */
const BANDS: Record<ConfidenceBand, BandStyle> = {
  "very-likely": { label: "Strong match", pill: "bg-emerald-100 text-emerald-900" },
  likely: { label: "Good match", pill: "bg-sky-100 text-sky-900" },
  possible: { label: "Weak match", pill: "bg-amber-100 text-amber-900" },
  uncertain: { label: "Very weak match", pill: "bg-slate-200 text-slate-700" },
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

/**
 * Never reaches 100%, and never rounds upward.
 *
 * `Math.round` turned a score of 0.9987 into "100% match" — a claim of
 * certainty manufactured by rounding, on a page that also says the app's
 * real-world accuracy has never been measured. Nothing this model produces
 * justifies the word "100", so the top of the scale is "over 99%".
 *
 * Rounding DOWN elsewhere is the same principle in miniature: where the display
 * has to lose precision, it loses it in the direction that claims less.
 */
export function formatMatchScore(confidence: number): string {
  const percent = confidence * 100;
  if (percent >= 99) return "over 99%";
  if (percent < 1) return "under 1%";
  return `${Math.floor(percent)}%`;
}

/** The one sentence that stops the band being read as an accuracy rate. */
export const CONFIDENCE_EXPLANATION =
  "These describe how closely the photo matched what the app was trained on — nothing more. " +
  "A strong match is not a promise that the answer is right: how often these estimates turn " +
  "out to be correct has never been measured. Treat every one of them as a starting point for " +
  "a conversation with a vet, not as a finding.";
