import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { createAnimal, getAnimals } from "../../api/client";
import AnalysisCard from "../../components/AnalysisCard";
import ImageUpload from "../../components/ImageUpload";
import { Button, Card, HistoryIcon, Select, useToast } from "../../components/ui";
import { capitalize, formatPercent } from "../../lib/format";
import type { AnalysisResponse, Animal, PostPrefill } from "../../types";

const NO_PET = "";

/** Compose the pre-filled community post for "Share to community". */
function buildPrefill(analysis: AnalysisResponse, pet: Animal | undefined): PostPrefill {
  const { result } = analysis;
  const topBreed = result.breed_candidates[0];
  const petIntro = pet ? `I analyzed a photo of my ${result.species} ${pet.name}` : `I analyzed a pet photo`;
  return {
    analysis_id: analysis.analysis_id,
    image_url: analysis.image_url,
    title: `AI analysis: ${capitalize(result.species)}${topBreed ? `, likely ${topBreed.breed}` : ""} — what do you think?`,
    content:
      `${petIntro} with the UEP EMMY analyzer (${result.model_version}).\n\n` +
      `AI findings:\n` +
      `- Species: ${capitalize(result.species)} (${formatPercent(result.species_confidence)} confidence)\n` +
      result.breed_candidates
        .map((candidate) => `- Breed candidate: ${candidate.breed} (${formatPercent(candidate.confidence)})\n`)
        .join("") +
      `- Age estimate: ${result.age_estimate.category} (${formatPercent(result.age_estimate.confidence)})\n\n` +
      `Does this look right? Any advice is welcome — especially from the veterinarians here.`,
  };
}

export default function AnalyzePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const preselectedPet = searchParams.get("pet") ?? NO_PET;

  const [pets, setPets] = useState<Animal[]>([]);
  const [selectedPetId, setSelectedPetId] = useState(preselectedPet);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [addingPet, setAddingPet] = useState(false);
  const { toast } = useToast();
  // Bumping the key remounts ImageUpload, clearing its preview ("analyze another").
  const [uploadKey, setUploadKey] = useState(0);

  useEffect(() => {
    getAnimals()
      .then(setPets)
      .catch(() => setPets([])); // No pets is fine — the analysis just stays unlinked.
  }, []);

  // A ?pet= id that isn't ours (stale link, other account) falls back to unlinked.
  useEffect(() => {
    if (selectedPetId !== NO_PET && pets.length > 0 && !pets.some((p) => p.id === selectedPetId)) {
      setSelectedPetId(NO_PET);
    }
  }, [pets, selectedPetId]);

  const petOptions = useMemo(
    () => [
      { value: NO_PET, label: "Not linked to a pet" },
      ...pets.map((pet) => ({ value: pet.id, label: `${pet.name} (${capitalize(pet.species)})` })),
    ],
    [pets],
  );

  const linkedPet = pets.find((pet) => pet.id === (analysis?.animal_id ?? selectedPetId));

  const handleReset = () => {
    setAnalysis(null);
    setUploadKey((current) => current + 1);
  };

  const handleShare = () => {
    if (!analysis) return;
    navigate("/community/new", { state: { prefill: buildPrefill(analysis, linkedPet) } });
  };

  const handleAddPet = async () => {
    if (!analysis) return;
    setAddingPet(true);
    try {
      const topBreed = analysis.result.breed_candidates[0]?.breed || null;
      const newPet = await createAnimal({
        name: "Analyzed Pet",
        species: analysis.result.species,
        breed: topBreed,
        age_category: analysis.result.age_estimate.category,
      });
      toast("Pet added to your profile.", "success");
      navigate(`/pets/${newPet.id}`);
    } catch (err) {
      toast("Failed to add pet.", "error");
    } finally {
      setAddingPet(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-slate-800">Analyze a pet photo</h1>
        <Link
          to="/analysis/history"
          className="inline-flex items-center gap-2 rounded-lg bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm ring-1 ring-slate-300 transition hover:bg-slate-50 hover:text-primary-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600"
        >
          <HistoryIcon className="h-4 w-4" />
          Analysis history
        </Link>
      </div>

      {analysis === null ? (
        <>
          <Card
            title="1 · Which pet is this?"
            description="Linked analyses appear in that pet's history. You can also analyze without linking."
          >
            <div className="mt-4">
              <Select
                label="Pet"
                value={selectedPetId}
                onChange={(event) => setSelectedPetId(event.target.value)}
                options={petOptions}
                hint={
                  pets.length === 0
                    ? "You have no pets yet — add one under My Pets to link analyses."
                    : undefined
                }
              />
            </div>
          </Card>

          <ImageUpload
            key={uploadKey}
            animalId={selectedPetId === NO_PET ? null : selectedPetId}
            onAnalysisComplete={setAnalysis}
          />
        </>
      ) : (
        <>
          <AnalysisCard analysis={analysis} />

          <Card>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-slate-500">
                {linkedPet
                  ? `Saved to ${linkedPet.name}'s history.`
                  : "Saved to your analysis history (not linked to a pet)."}
              </p>
              <div className="flex flex-wrap gap-2">
                {!linkedPet && (
                  <Button variant="secondary" onClick={handleAddPet} loading={addingPet}>
                    Add to my pets
                  </Button>
                )}
                <Button variant="secondary" onClick={handleReset}>
                  Analyze another photo
                </Button>
                <Button onClick={handleShare}>Share to community</Button>
              </div>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
