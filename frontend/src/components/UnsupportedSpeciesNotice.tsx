import { Link } from "react-router-dom";
import { Button, ChatIcon, StethoscopeIcon } from "./ui";
import { speciesPhrase } from "../lib/species";

/*
 * What this pet CAN do here.
 *
 * Written as scope rather than as an error, because it is one: dogs and cats
 * are what the analysis model and the evidence library cover, and saying "not
 * supported" in red would frame a deliberate limit as a fault the owner has hit.
 *
 * It always ends by naming the two things that do work for every species — the
 * community and the veterinary directory — because a notice that only takes
 * something away leaves an owner with a profile and no reason to have made one.
 */
export default function UnsupportedSpeciesNotice({
  species,
  petName,
  feature,
}: {
  species: string | null | undefined;
  petName?: string | null;
  /** Which feature the owner was reaching for, so the first line is about that. */
  feature: "analysis" | "symptom-checker" | "both";
}) {
  const subject = petName ?? speciesPhrase(species);
  const headline =
    feature === "analysis"
      ? `Photo analysis is for dogs and cats`
      : feature === "symptom-checker"
        ? `The symptom checker is for dogs and cats`
        : `Some features are for dogs and cats only`;

  return (
    <section className="rounded-lg border border-slate-300 bg-slate-50 p-5">
      <h2 className="text-base font-semibold text-slate-800">{headline}</h2>

      <p className="mt-2 text-sm text-slate-600">
        {feature === "analysis" ? (
          <>
            The breed and age model was trained on dogs and cats only. Run on {speciesPhrase(species)}{" "}
            it would not fail — it would return a dog or cat breed with a confidence figure
            attached, which is worse than returning nothing. So it is turned off for {subject}.
          </>
        ) : feature === "symptom-checker" ? (
          <>
            Every piece of published guidance behind the checker is about dogs or cats, so it has
            nothing to weigh {speciesPhrase(species)} against and would have to abstain at the end
            of the questions. It is turned off for {subject} rather than wasting the answers.
          </>
        ) : (
          <>
            The photo analysis and the symptom checker are both built on dog and cat sources, so
            they are turned off for {subject}. Everything else on the platform works normally.
          </>
        )}
      </p>

      <p className="mt-3 text-sm font-medium text-slate-700">What you can do instead:</p>
      <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-600">
        <li>Keep the profile, photos and health record — those work for any species.</li>
        <li>Ask the community; verified veterinarians answer there.</li>
        <li>Find a practice and request an appointment — the directory is not species-limited.</li>
      </ul>

      <div className="mt-4 flex flex-wrap gap-2">
        <Link to="/community/new">
          <Button size="sm">
            <ChatIcon className="h-4 w-4" />
            Ask the community
          </Button>
        </Link>
        <Link to="/vets">
          <Button size="sm" variant="secondary">
            <StethoscopeIcon className="h-4 w-4" />
            Find a vet
          </Button>
        </Link>
      </div>
    </section>
  );
}
