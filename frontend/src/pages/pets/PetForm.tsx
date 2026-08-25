import { useEffect, useId, useRef, useState } from "react";
import { isSupportedSpecies, unsupportedSummary } from "../../lib/species";
import type { ChangeEvent, FormEvent } from "react";
import { ApiError } from "../../api/client";
import { Button, CameraIcon, Input, Select, XIcon } from "../../components/ui";
import type { Animal, AnimalPayload } from "../../types";

/*
 * Shared add/edit pet form, rendered inside a <Modal>. The caller supplies the
 * submit action (create or update); the form owns its fields and error state.
 */

const SPECIES_OPTIONS = [
  { value: "dog", label: "Dog" },
  { value: "cat", label: "Cat" },
  { value: "rabbit", label: "Rabbit" },
  { value: "bird", label: "Bird" },
  { value: "other", label: "Other" },
];

const AGE_CATEGORY_OPTIONS = [
  { value: "unknown", label: "Unknown" },
  { value: "baby", label: "Baby (Puppy/Kitten)" },
  { value: "young", label: "Young" },
  { value: "adult", label: "Adult" },
  { value: "senior", label: "Senior" },
];

const PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_PHOTO_BYTES = 10 * 1024 * 1024;

interface PetFormProps {
  /** Pet being edited, or undefined when adding a new one. */
  initial?: Animal;
  submitLabel: string;
  onSubmit: (payload: AnimalPayload, photo?: File) => Promise<void>;
  onCancel: () => void;
}

export default function PetForm({ initial, submitLabel, onSubmit, onCancel }: PetFormProps) {
  const photoInputId = useId();
  const photoInputRef = useRef<HTMLInputElement>(null);
  const knownSpecies = SPECIES_OPTIONS.some((option) => option.value === initial?.species);
  const [name, setName] = useState(initial?.name ?? "");
  const [species, setSpecies] = useState(initial ? (knownSpecies ? initial.species : "other") : "dog");
  const [customSpecies, setCustomSpecies] = useState(
    initial && !knownSpecies ? initial.species : "",
  );
  const [breed, setBreed] = useState(initial?.breed ?? "");
  const [birthDate, setBirthDate] = useState(initial?.birth_date ?? "");
  const [ageCategory, setAgeCategory] = useState<import("../../types").AgeCategory>(
    initial?.age_category ?? "unknown",
  );
  const [photo, setPhoto] = useState<File | null>(null);
  const [photoPreviewUrl, setPhotoPreviewUrl] = useState<string | null>(null);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const today = new Date().toISOString().slice(0, 10);

  useEffect(() => {
    if (!photo) {
      setPhotoPreviewUrl(null);
      return;
    }
    const previewUrl = URL.createObjectURL(photo);
    setPhotoPreviewUrl(previewUrl);
    return () => URL.revokeObjectURL(previewUrl);
  }, [photo]);

  const handlePhotoChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0];
    if (!selected) return;
    if (!PHOTO_TYPES.includes(selected.type)) {
      setPhotoError("Please choose a JPEG, PNG, or WebP image.");
      event.target.value = "";
      return;
    }
    if (selected.size > MAX_PHOTO_BYTES) {
      setPhotoError("Photo must be 10 MB or smaller.");
      event.target.value = "";
      return;
    }
    setPhoto(selected);
    setPhotoError(null);
  };

  const removePhoto = () => {
    setPhoto(null);
    setPhotoError(null);
    if (photoInputRef.current) photoInputRef.current.value = "";
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await onSubmit(
        {
          name: name.trim(),
          species: species === "other" ? customSpecies.trim() || "other" : species,
          breed: breed.trim() || null,
          birth_date: birthDate || null,
          age_category: ageCategory,
        },
        photo ?? undefined,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the pet.");
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Input
        label="Name"
        value={name}
        onChange={(event) => setName(event.target.value)}
        placeholder="Buddy"
        maxLength={120}
        required
      />
      <Select
        label="Species"
        value={species}
        onChange={(event) => setSpecies(event.target.value)}
        options={SPECIES_OPTIONS}
      />
      {/*
        Said at the moment the species is chosen, not after the pet is saved.
        An owner picking "Rabbit" is about to find out that two of the four
        things on the navigation bar do nothing for them; finding that out here
        costs one sentence, and finding it out later costs a photo upload and
        every step of a symptom form.
      */}
      {!isSupportedSpecies(species === "other" ? customSpecies : species) && (
        <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
          {unsupportedSummary(species === "other" ? customSpecies || null : species)} The profile,
          photos, health record, community and vet directory all work normally.
        </p>
      )}

      {species === "other" && (
        <Input
          label="Which species?"
          value={customSpecies}
          onChange={(event) => setCustomSpecies(event.target.value)}
          placeholder="hamster, turtle, parrot…"
          maxLength={80}
          required
        />
      )}
      <Input
        label="Breed"
        value={breed}
        onChange={(event) => setBreed(event.target.value)}
        placeholder="Labrador Retriever"
        hint="Optional — leave empty if unknown; the AI analysis can suggest one."
        maxLength={120}
      />
      <Input
        label="Birth date"
        type="date"
        value={birthDate}
        onChange={(event) => setBirthDate(event.target.value)}
        max={today}
        hint="Optional — used to show your pet's exact age if known."
      />
      <Select
        label="Age Category"
        value={ageCategory}
        onChange={(event) => setAgeCategory(event.target.value as import("../../types").AgeCategory)}
        options={AGE_CATEGORY_OPTIONS}
        hint="Used if birth date is unknown."
      />

      {!initial && (
        <div>
          <label htmlFor={photoInputId} className="mb-1 block text-sm font-medium text-slate-700">
            Photo <span className="font-normal text-slate-400">(optional)</span>
          </label>
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-slate-100 ring-1 ring-slate-200">
              {photoPreviewUrl ? (
                <img
                  src={photoPreviewUrl}
                  alt="Selected pet preview"
                  className="h-full w-full object-cover"
                />
              ) : (
                <CameraIcon className="h-6 w-6 text-slate-400" />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => photoInputRef.current?.click()}
                >
                  {photo ? "Change photo" : "Choose photo"}
                </Button>
                {photo && (
                  <button
                    type="button"
                    onClick={removePhoto}
                    aria-label="Remove selected photo"
                    title="Remove photo"
                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600"
                  >
                    <XIcon className="h-4 w-4" />
                  </button>
                )}
              </div>
              <p className="mt-1 truncate text-xs text-slate-500">
                {photo ? photo.name : "JPEG, PNG, or WebP up to 10 MB"}
              </p>
            </div>
          </div>
          <input
            ref={photoInputRef}
            id={photoInputId}
            type="file"
            accept={PHOTO_TYPES.join(",")}
            onChange={handlePhotoChange}
            className="hidden"
          />
          {photoError && (
            <p className="mt-1 text-xs text-rose-600" role="alert">
              {photoError}
            </p>
          )}
        </div>
      )}

      {error && (
        <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
          {error}
        </p>
      )}

      <div className="flex justify-end gap-3 pt-2">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" loading={submitting}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}
