/**
 * Which animals the main features actually work for.
 *
 * One place, because the answer was previously implied in three different ways
 * and stated in none. A rabbit could be given a profile, taken through four
 * steps of the symptom checker, and photographed for breed analysis — and only
 * at the end of each would anything go wrong, differently each time:
 *
 * - the symptom checker abstained, blaming the owner's answers;
 * - the breed analyser did NOT fail. It is a binary cat-or-dog classifier, so a
 *   rabbit photo comes back "cat, 91% confident". A confident wrong answer is
 *   worse than a refusal, and it is the reason the analyser is blocked for
 *   these pets rather than merely warned about.
 *
 * This is a product decision, not a bug: dogs and cats are the scope. What was
 * a bug is that nothing said so until after the effort had been spent.
 */

/** Species the AI analysis and the symptom checker are built for. */
export const SUPPORTED_SPECIES = ["dog", "cat"] as const;

export type SupportedSpecies = (typeof SUPPORTED_SPECIES)[number];

/**
 * Does this pet get the analysis and symptom-checker features?
 *
 * Case- and whitespace-insensitive, matching the backend's `normalise_species`.
 * A blank or unknown species returns false: we cannot promise a feature works
 * for an animal nobody has named.
 */
export function isSupportedSpecies(species: string | null | undefined): boolean {
  if (!species) return false;
  const token = species.trim().toLowerCase();
  return (SUPPORTED_SPECIES as readonly string[]).includes(token);
}

/** "a rabbit", "a bird" — for dropping into a sentence. */
export function speciesPhrase(species: string | null | undefined): string {
  const token = (species ?? "").trim().toLowerCase();
  if (!token) return "this pet";
  return /^[aeiou]/.test(token) ? `an ${token}` : `a ${token}`;
}

/** The one-line version, for a form hint. */
export function unsupportedSummary(species: string | null | undefined): string {
  return (
    `The photo analysis and symptom checker are built for dogs and cats, so they are turned ` +
    `off for ${speciesPhrase(species)}.`
  );
}
