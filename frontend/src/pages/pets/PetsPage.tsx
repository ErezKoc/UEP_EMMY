import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ApiError,
  createAnimal,
  getAnimals,
  updateAnimal,
  uploadAnimalPhoto,
} from "../../api/client";
import {
  Badge,
  Button,
  CropIcon,
  EmptyState,
  Modal,
  PawIcon,
  Spinner,
  useToast,
} from "../../components/ui";
import { capitalize, formatAge } from "../../lib/format";
import type { Animal, AnimalPayload } from "../../types";
import PetForm from "./PetForm";
import ThumbnailFocusForm from "./ThumbnailFocusForm";

function PetCard({ pet, onAdjustThumbnail }: { pet: Animal; onAdjustThumbnail: () => void }) {
  return (
    <article
      className="group overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200 transition hover:shadow-md hover:ring-primary-300"
    >
      <div className="relative">
        <Link
          to={`/pets/${pet.id}`}
          className="block focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-primary-600"
        >
          <div className="flex aspect-[5/2] w-full items-center justify-center overflow-hidden bg-slate-100">
            {pet.photo_url ? (
              <img
                src={pet.photo_url}
                alt={pet.name}
                className="h-full w-full object-cover"
                style={{
                  objectPosition: `${pet.photo_position_x}% ${pet.photo_position_y}%`,
                  transformOrigin: `${pet.photo_position_x}% ${pet.photo_position_y}%`,
                  transform: `scale(${pet.photo_zoom})`,
                }}
              />
            ) : (
              <PawIcon className="h-10 w-10 text-slate-300" />
            )}
          </div>
        </Link>
        {pet.photo_url && (
          <button
            type="button"
            onClick={onAdjustThumbnail}
            aria-label={`Adjust ${pet.name}'s thumbnail`}
            title="Adjust thumbnail"
            className="absolute right-2 top-2 inline-flex h-8 w-8 items-center justify-center rounded-lg bg-white/70 text-slate-700 shadow-sm ring-1 ring-white/80 transition hover:bg-white/95 hover:text-primary-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600"
          >
            <CropIcon className="h-4 w-4" />
          </button>
        )}
      </div>
      <Link
        to={`/pets/${pet.id}`}
        className="block p-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-primary-600"
      >
        <div className="flex items-center justify-between gap-2">
          <h3 className="truncate font-semibold text-slate-800">{pet.name}</h3>
          <Badge variant="primary">{capitalize(pet.species)}</Badge>
        </div>
        <p className="mt-1 truncate text-sm text-slate-500">
          {pet.breed ?? "Unknown breed"}
          {pet.birth_date && ` · ${formatAge(pet.birth_date)}`}
        </p>
      </Link>
    </article>
  );
}

export default function PetsPage() {
  const { toast } = useToast();
  const [pets, setPets] = useState<Animal[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [thumbnailPet, setThumbnailPet] = useState<Animal | null>(null);

  const loadPets = useCallback(async () => {
    setLoadError(null);
    try {
      setPets(await getAnimals());
    } catch (err) {
      setLoadError(
        err instanceof ApiError ? err.message : "Could not load pets. Is the backend running?",
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPets();
  }, [loadPets]);

  const handleCreate = async (payload: AnimalPayload, photo?: File) => {
    let created = await createAnimal(payload);
    let photoErrorMessage: string | null = null;
    if (photo) {
      try {
        created = await uploadAnimalPhoto(created.id, photo);
      } catch (err) {
        photoErrorMessage = err instanceof ApiError ? err.message : "The photo upload failed.";
      }
    }
    setPets((current) => [...current, created]);
    setAddOpen(false);
    if (photoErrorMessage) {
      toast(`${created.name} was added, but the photo could not be uploaded. ${photoErrorMessage}`, "error");
    } else {
      toast(`${created.name} added to your pets.`, "success");
    }
  };

  const handleThumbnailSave = async (positionX: number, positionY: number, zoom: number) => {
    if (!thumbnailPet) return;
    const updated = await updateAnimal(thumbnailPet.id, {
      photo_position_x: positionX,
      photo_position_y: positionY,
      photo_zoom: zoom,
    });
    setPets((current) => current.map((pet) => (pet.id === updated.id ? updated : pet)));
    setThumbnailPet(null);
    toast("Thumbnail updated.", "success");
  };

  return (
    <div>
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">My pets</h1>
          <p className="mt-1 text-sm text-slate-500">
            Profiles for your animals — analyses you run can be linked to them.
          </p>
        </div>
        <Button onClick={() => setAddOpen(true)}>Add pet</Button>
      </div>

      <div className="mt-6">
        {isLoading && (
          <div className="flex justify-center py-16">
            <Spinner />
          </div>
        )}

        {loadError && (
          <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
            {loadError}{" "}
            <button onClick={() => void loadPets()} className="font-medium underline">
              Retry
            </button>
          </div>
        )}

        {!isLoading && !loadError && pets.length === 0 && (
          <EmptyState
            title="No pets yet"
            description="Add your first pet to keep its profile, photos, and AI analyses in one place."
            action={<Button onClick={() => setAddOpen(true)}>Add your first pet</Button>}
          />
        )}

        {pets.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {pets.map((pet) => (
              <PetCard
                key={pet.id}
                pet={pet}
                onAdjustThumbnail={() => setThumbnailPet(pet)}
              />
            ))}
          </div>
        )}
      </div>

      <Modal open={addOpen} onClose={() => setAddOpen(false)} title="Add a pet">
        <PetForm
          submitLabel="Add pet"
          onSubmit={handleCreate}
          onCancel={() => setAddOpen(false)}
        />
      </Modal>

      <Modal
        open={thumbnailPet !== null}
        onClose={() => setThumbnailPet(null)}
        title="Adjust thumbnail"
      >
        {thumbnailPet && (
          <ThumbnailFocusForm
            pet={thumbnailPet}
            onSubmit={handleThumbnailSave}
            onCancel={() => setThumbnailPet(null)}
          />
        )}
      </Modal>
    </div>
  );
}
