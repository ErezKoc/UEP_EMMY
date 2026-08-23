import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, deleteAnalysis, getAnimals, updateAnalysis } from "../api/client";
import { Button, Card, Input, Modal, Select, Textarea, useToast } from "./ui";
import { capitalize } from "../lib/format";
import type { AgeCategory, AnalysisDetail, Animal } from "../types";

const NO_PET = "none";
const KEEP = "";

const AGE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: KEEP, label: "Leave as the app estimated" },
  { value: "baby", label: "Baby (puppy/kitten)" },
  { value: "young", label: "Young" },
  { value: "adult", label: "Adult" },
  { value: "senior", label: "Senior" },
  { value: "unknown", label: "Unknown" },
];

/*
 * Everything an owner can do to a stored result: correct it, move it to a
 * different pet, take a copy, or remove it.
 *
 * The correction form is deliberately not an "edit result" form. It never
 * overwrites what the model predicted — the record of the prediction is the
 * only reason to keep these rows — so each field reads as "actually, it is…"
 * and the original stays visible on the page beside it.
 */
export default function AnalysisControls({
  analysis,
  onChanged,
}: {
  analysis: AnalysisDetail;
  onChanged: (updated: AnalysisDetail) => void;
}) {
  const navigate = useNavigate();
  const { toast } = useToast();

  const [pets, setPets] = useState<Animal[]>([]);
  const [species, setSpecies] = useState(analysis.correction?.species ?? "");
  const [breed, setBreed] = useState(analysis.correction?.breed ?? "");
  const [ageCategory, setAgeCategory] = useState<string>(
    analysis.correction?.age_category ?? KEEP,
  );
  const [note, setNote] = useState(analysis.correction?.note ?? "");
  const [petId, setPetId] = useState(analysis.animal?.id ?? NO_PET);

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    getAnimals()
      .then(setPets)
      .catch(() => setPets([]));
  }, []);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const updated = await updateAnalysis(analysis.id, {
        // An emptied box means "use the app's value again", which the API
        // expresses as null rather than as an empty string.
        correction: {
          species: species.trim() || null,
          breed: breed.trim() || null,
          age_category: (ageCategory || null) as AgeCategory | null,
          note: note.trim() || null,
        },
        animal_id: petId === NO_PET ? null : petId,
      });
      onChanged(updated);
      toast("Saved.", "success");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the changes.");
    } finally {
      setSaving(false);
    }
  };

  /*
   * Export is built here rather than fetched from an endpoint: the page already
   * holds the whole record, so a download needs no round trip and no
   * authenticated file request. The model version and the raw figures ARE
   * included — this is the copy somebody keeps or hands to a veterinarian, and
   * leaving detail out of an export to keep a screen readable would be
   * withholding the owner's own data.
   */
  const exportJson = () => {
    const payload = {
      exported_at: new Date().toISOString(),
      exported_from: "UEP EMMY",
      analysis: {
        id: analysis.id,
        created_at: analysis.created_at,
        image_url: analysis.image_url,
        linked_pet: analysis.animal
          ? { id: analysis.animal.id, name: analysis.animal.name, species: analysis.animal.species }
          : null,
        what_the_app_predicted: analysis.result,
        what_the_owner_corrected: analysis.correction ?? null,
        corrected_at: analysis.corrected_at ?? null,
        symptom_answers: analysis.intake ?? null,
        triage_result: analysis.triage ?? null,
      },
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    const stamp = analysis.created_at.slice(0, 10);
    link.download = `analysis-${stamp}-${analysis.id.slice(0, 8)}.json`;
    link.click();
    URL.revokeObjectURL(url);
    toast("Downloaded.", "success");
  };

  const confirmDelete = async () => {
    setDeleting(true);
    try {
      await deleteAnalysis(analysis.id);
      toast("Analysis deleted.", "success");
      navigate("/analysis/history", { replace: true });
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not delete it.", "error");
      setDeleting(false);
      setDeleteOpen(false);
    }
  };

  const petOptions = [
    { value: NO_PET, label: "Not linked to a pet" },
    ...pets.map((pet) => ({ value: pet.id, label: `${pet.name} (${capitalize(pet.species)})` })),
  ];

  return (
    <>
      <Card
        title="Something not right?"
        description="Correct what the app got wrong, move this to a different pet, or remove it. Your corrections are shown instead of the app's guess — the original stays on record underneath."
      >
        <div className="mt-5 space-y-4">
          <Select
            label="Linked pet"
            value={petId}
            onChange={(event) => setPetId(event.target.value)}
            options={petOptions}
            hint="Moving this to another pet also moves it in that pet's history."
          />

          <Input
            label="Actually, the species is"
            value={species}
            onChange={(event) => setSpecies(event.target.value)}
            placeholder={`Leave blank to keep "${capitalize(analysis.result.species)}"`}
            maxLength={80}
          />

          <Input
            label="Actually, the breed is"
            value={breed}
            onChange={(event) => setBreed(event.target.value)}
            placeholder={
              analysis.result.breed_candidates[0]
                ? `Leave blank to keep "${analysis.result.breed_candidates[0].breed}"`
                : "Leave blank if you are not sure"
            }
            maxLength={120}
          />

          <Select
            label="Actually, the age is"
            value={ageCategory}
            onChange={(event) => setAgeCategory(event.target.value)}
            options={AGE_OPTIONS}
          />

          <Textarea
            label="Anything worth noting (optional)"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="My vet confirmed she is a Basset Hound mix."
            rows={2}
            maxLength={500}
            hint="A note on its own does not count as a correction."
          />

          {error && (
            <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
              {error}
            </p>
          )}

          <div className="flex flex-wrap justify-between gap-2 border-t border-slate-100 pt-4">
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void save()} loading={saving}>
                Save changes
              </Button>
              <Button variant="secondary" onClick={exportJson}>
                Export a copy
              </Button>
            </div>
            <Button variant="danger" onClick={() => setDeleteOpen(true)}>
              Delete
            </Button>
          </div>
        </div>
      </Card>

      <Modal
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        title="Delete this analysis?"
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleteOpen(false)} disabled={deleting}>
              Keep it
            </Button>
            <Button variant="danger" onClick={() => void confirmDelete()} loading={deleting}>
              Delete permanently
            </Button>
          </>
        }
      >
        <p className="text-sm text-slate-600">
          {/*
            Says what else goes, because the photograph is the part an owner
            would most expect to be removed and would least expect to have to
            ask about.
          */}
          This removes the result, your symptom answers, and the photo it was run on. It cannot be
          undone. Export a copy first if you want to keep one.
        </p>
      </Modal>
    </>
  );
}
