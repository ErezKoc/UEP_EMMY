import { useEffect, useRef, useState } from "react";
import type { ChangeEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ApiError,
  deleteAnimal,
  getAnimal,
  updateAnimal,
  uploadAnimalPhoto,
} from "../../api/client";
import {
  Badge,
  Button,
  CameraIcon,
  Card,
  EmptyState,
  Modal,
  PawIcon,
  Spinner,
  useToast,
} from "../../components/ui";
import { capitalize, formatAge, formatDate } from "../../lib/format";
import type { Animal, AnimalPayload } from "../../types";
import PetForm from "./PetForm";

const PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"];

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 border-b border-slate-100 py-2 text-sm last:border-b-0">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-800">{value}</dd>
    </div>
  );
}

export default function PetDetailPage() {
  const { petId } = useParams<{ petId: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [pet, setPet] = useState<Animal | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);

  useEffect(() => {
    if (!petId) return;
    let cancelled = false;
    getAnimal(petId)
      .then((loaded) => {
        if (!cancelled) setPet(loaded);
      })
      .catch((err) => {
        if (!cancelled) {
          setLoadError(
            err instanceof ApiError && err.status === 404
              ? "This pet does not exist (or belongs to another account)."
              : err instanceof ApiError
                ? err.message
                : "Could not load the pet. Is the backend running?",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [petId]);

  const handleEdit = async (payload: AnimalPayload) => {
    if (!pet) return;
    const updated = await updateAnimal(pet.id, payload);
    setPet(updated);
    setEditOpen(false);
    toast("Pet updated.", "success");
  };

  const handleDelete = async () => {
    if (!pet) return;
    setDeleting(true);
    try {
      await deleteAnimal(pet.id);
      toast(`${pet.name} was removed.`, "success");
      navigate("/pets");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not delete the pet.", "error");
      setDeleting(false);
      setDeleteOpen(false);
    }
  };

  const handlePhotoChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !pet) return;
    if (!PHOTO_TYPES.includes(file.type)) {
      toast("Please choose a JPEG, PNG, or WebP image.", "error");
      return;
    }
    setUploadingPhoto(true);
    try {
      setPet(await uploadAnimalPhoto(pet.id, file));
      toast("Photo updated.", "success");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not upload the photo.", "error");
    } finally {
      setUploadingPhoto(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner />
      </div>
    );
  }

  if (loadError || !pet) {
    return (
      <div className="mx-auto max-w-lg">
        <EmptyState
          title="Pet not found"
          description={loadError ?? "Unknown error."}
          action={
            <Link to="/pets">
              <Button variant="secondary">Back to my pets</Button>
            </Link>
          }
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl">
      <Link to="/pets" className="text-sm font-medium text-primary-600 hover:text-primary-700">
        ← My pets
      </Link>

      <div className="mt-4 overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
        <div
          className={`relative flex items-center justify-center bg-slate-100 ${
            pet.photo_url ? "h-80 sm:h-[30rem]" : "h-56"
          }`}
        >
          {pet.photo_url ? (
            <img src={pet.photo_url} alt={pet.name} className="h-full w-full object-contain" />
          ) : (
            <PawIcon className="h-16 w-16 text-slate-300" />
          )}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadingPhoto}
            className="absolute bottom-3 right-3 inline-flex items-center gap-2 rounded-lg bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow ring-1 ring-slate-200 hover:bg-slate-50 disabled:text-slate-400"
          >
            <CameraIcon className="h-4 w-4" />
            {uploadingPhoto ? "Uploading…" : pet.photo_url ? "Change photo" : "Add photo"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept={PHOTO_TYPES.join(",")}
            onChange={handlePhotoChange}
            className="hidden"
          />
        </div>

        <div className="p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-800">{pet.name}</h1>
              <Badge variant="primary">{capitalize(pet.species)}</Badge>
            </div>
            <div className="flex flex-wrap justify-end gap-2">
              <Button variant="secondary" size="sm" onClick={() => setEditOpen(true)}>
                Edit
              </Button>
              <Button variant="danger" size="sm" onClick={() => setDeleteOpen(true)}>
                Delete
              </Button>
            </div>
          </div>

          <dl className="mt-4">
            <InfoRow label="Breed" value={pet.breed ?? "Unknown"} />
            <InfoRow
              label="Birth date"
              value={pet.birth_date ? formatDate(pet.birth_date) : "Unknown"}
            />
            {pet.birth_date ? (
              <InfoRow label="Age" value={formatAge(pet.birth_date)} />
            ) : (
              pet.age_category && pet.age_category !== "unknown" && (
                <InfoRow label="Age Category" value={capitalize(pet.age_category)} />
              )
            )}
            <InfoRow label="Added on" value={formatDate(pet.created_at.slice(0, 10))} />
          </dl>
        </div>
      </div>

      <Card
        className="mt-6"
        title="Health history"
        description={`AI analyses and symptom checks linked to ${pet.name}.`}
      >
        <div className="mt-4 flex flex-wrap gap-2">
          <Link to={`/analysis/history?pet=${pet.id}`}>
            <Button variant="secondary" size="sm">
              View {pet.name}&apos;s analyses
            </Button>
          </Link>
          <Link to={`/symptom-check/history?pet=${pet.id}`}>
            <Button variant="secondary" size="sm">
              View {pet.name}&apos;s symptom checks
            </Button>
          </Link>
          <Link to={`/analyze?pet=${pet.id}`}>
            <Button variant="secondary" size="sm">
              Analyze a photo
            </Button>
          </Link>
          <Link to={`/symptom-check?pet=${pet.id}`}>
            <Button variant="secondary" size="sm">
              Check symptoms
            </Button>
          </Link>
        </div>
      </Card>

      <Modal open={editOpen} onClose={() => setEditOpen(false)} title={`Edit ${pet.name}`}>
        <PetForm
          initial={pet}
          submitLabel="Save changes"
          onSubmit={handleEdit}
          onCancel={() => setEditOpen(false)}
        />
      </Modal>

      <Modal
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        title={`Delete ${pet.name}?`}
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button variant="danger" loading={deleting} onClick={() => void handleDelete()}>
              Delete pet
            </Button>
          </>
        }
      >
        <p className="text-sm text-slate-600">
          This removes {pet.name}&apos;s profile. Past AI analyses are kept but will no longer be
          linked to a pet. This cannot be undone.
        </p>
      </Modal>
    </div>
  );
}
