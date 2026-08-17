import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError, assessSymptoms, createSymptomCheck, getAnimals } from "../../api/client";
import SymptomIntakeForm from "../../components/SymptomIntakeForm";
import TriageResultCard from "../../components/TriageResultCard";
import { Button, Card, HistoryIcon, Select } from "../../components/ui";
import { useSession } from "../../auth/SessionContext";
import { capitalize } from "../../lib/format";
import type { AgeCategory, Animal, SymptomIntake, TriageAssessment } from "../../types";

/*
 * Symptom triage on its own, with no photo involved.
 *
 * The questions used to live on the analyze page, which tied advice to an
 * upload the owner might not have — and a worried owner should never have to
 * find a camera first. Species still matters (several rules in the backend's
 * rules.py are cat-only or dog-only), so it is asked directly here instead of
 * being inferred from an image.
 */

const NO_PET = "";
const UNKNOWN_SPECIES = "";

const SPECIES_OPTIONS = [
  { value: UNKNOWN_SPECIES, label: "Not sure / another animal" },
  { value: "dog", label: "Dog" },
  { value: "cat", label: "Cat" },
];

export default function SymptomCheckPage() {
  const { user } = useSession();
  const [searchParams] = useSearchParams();
  const [pets, setPets] = useState<Animal[]>([]);
  const [selectedPetId, setSelectedPetId] = useState(searchParams.get("pet") ?? NO_PET);
  const [species, setSpecies] = useState(UNKNOWN_SPECIES);
  const [assessment, setAssessment] = useState<TriageAssessment | null>(null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!user) return;
    getAnimals()
      .then(setPets)
      .catch(() => setPets([])); // Advice does not depend on having pets saved.
  }, [user]);

  // A ?pet= id that isn't ours (stale link, other account) falls back to unlinked.
  useEffect(() => {
    if (selectedPetId !== NO_PET && pets.length > 0 && !pets.some((p) => p.id === selectedPetId)) {
      setSelectedPetId(NO_PET);
    }
  }, [pets, selectedPetId]);

  const selectedPet = pets.find((pet) => pet.id === selectedPetId);

  const petOptions = useMemo(
    () => [
      { value: NO_PET, label: "Not one of my saved pets" },
      ...pets.map((pet) => ({ value: pet.id, label: `${pet.name} (${capitalize(pet.species)})` })),
    ],
    [pets],
  );

  const handleReset = () => {
    setAssessment(null);
    setSaved(false);
  };

  const handleSubmit = async (intake: SymptomIntake) => {
    setBusy(true);
    setError(null);
    // A saved pet knows its own species and age; only fall back to the manual
    // answer when the owner did not pick one.
    const effectiveSpecies = selectedPet ? selectedPet.species : species || null;
    const ageCategory: AgeCategory | null = selectedPet ? selectedPet.age_category : null;
    const answers = { ...intake, species: effectiveSpecies, age_category: ageCategory };

    try {
      // Signed-in owners get the check kept in their history; a visitor who is
      // not signed in still gets the same advice, just not stored.
      if (user) {
        const check = await createSymptomCheck(answers, selectedPetId || null);
        setAssessment(check.triage);
        setSaved(check.triage !== null);
      } else {
        setAssessment(await assessSymptoms(answers));
        setSaved(false);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not assess the symptoms.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Symptom checker</h1>
          <p className="mt-1 text-sm text-slate-500">
            Answer a few questions about how your pet is doing and get guidance on how urgently
            they should be seen. No photo needed.
          </p>
        </div>
        {user && (
          <Link
            to="/symptom-check/history"
            className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm ring-1 ring-slate-300 transition hover:bg-slate-50 hover:text-primary-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600"
          >
            <HistoryIcon className="h-4 w-4" />
            Past checks
          </Link>
        )}
      </div>

      {assessment === null ? (
        <>
          <Card
            title="Who is this about?"
            description="Species changes the answer for some symptoms, so it is worth setting."
          >
            <div className="mt-4 space-y-4">
              {user && pets.length > 0 && (
                <Select
                  label="Pet"
                  value={selectedPetId}
                  onChange={(event) => setSelectedPetId(event.target.value)}
                  options={petOptions}
                  hint="Picking a saved pet fills in their species and age for you."
                />
              )}

              {!selectedPet && (
                <Select
                  label="Species"
                  value={species}
                  onChange={(event) => setSpecies(event.target.value)}
                  options={SPECIES_OPTIONS}
                  hint={
                    user && pets.length === 0
                      ? "You have no saved pets yet — you can add one under My Pets."
                      : undefined
                  }
                />
              )}

              {selectedPet && (
                <p className="rounded-lg bg-slate-100 px-4 py-3 text-sm text-slate-600">
                  Using {selectedPet.name}'s details: {capitalize(selectedPet.species)},{" "}
                  {selectedPet.age_category}.
                </p>
              )}
            </div>
          </Card>

          <SymptomIntakeForm onSubmit={handleSubmit} busy={busy} />

          {error && (
            <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
              {error}
            </p>
          )}

          <p className="text-center text-sm text-slate-500">
            Want a breed and age estimate instead?{" "}
            <Link to="/analyze" className="font-medium text-primary-600 underline">
              Analyze a photo
            </Link>
          </p>
        </>
      ) : (
        <>
          <TriageResultCard triage={assessment} />

          <Card>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-slate-500">
                {saved ? (
                  selectedPet ? (
                    <>Saved to {selectedPet.name}&apos;s history.</>
                  ) : (
                    <>Saved to your symptom check history (not linked to a pet).</>
                  )
                ) : (
                  <>
                    <Link to="/login" className="font-medium text-primary-600 underline">
                      Sign in
                    </Link>{" "}
                    to keep a record of checks like this one.
                  </>
                )}
              </p>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" onClick={handleReset}>
                  Start over
                </Button>
                <Link to="/vets">
                  <Button>Find a vet</Button>
                </Link>
              </div>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
