import { useEffect, useState } from "react";
import { ApiError, getAnimals, requestAppointment } from "../api/client";
import { Button, Input, Modal, Select, Textarea, useToast } from "./ui";
import { capitalize } from "../lib/format";
import type { Animal, Veterinarian } from "../types";

const NO_PET = "none";

/** Today in the browser's own timezone, for the date input's floor. */
function todayValue(): string {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

/*
 * Asking a practice for an appointment.
 *
 * The wording throughout is "request" and never "book", and the dialog says so
 * twice — in its own description and again on the button. This platform does
 * not hold the clinic's diary, so an owner who leaves here believing a time is
 * reserved has been misled by us, and the cost of that is landing at a closed
 * door with a sick animal.
 *
 * There is no time picker for the same reason. We do not know which times the
 * practice has free, and a grid of slots would claim we did; the owner writes
 * when suits them in their own words and the practice replies.
 */
export default function AppointmentRequestDialog({
  vet,
  open,
  onClose,
  onRequested,
}: {
  vet: Veterinarian;
  open: boolean;
  onClose: () => void;
  onRequested?: () => void;
}) {
  const { toast } = useToast();
  const [pets, setPets] = useState<Animal[]>([]);
  const [animalId, setAnimalId] = useState(NO_PET);
  const [reason, setReason] = useState("");
  const [preferredDate, setPreferredDate] = useState(todayValue());
  const [timeNote, setTimeNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    // Failure here is not fatal: the pet is optional, and a request that names
    // none is still a request. It only means no calendar entry on confirmation.
    getAnimals()
      .then(setPets)
      .catch(() => setPets([]));
  }, [open]);

  const submit = async () => {
    if (!reason.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await requestAppointment({
        vet_id: vet.id,
        reason: reason.trim(),
        preferred_date: preferredDate,
        preferred_time_note: timeNote.trim() || null,
        animal_id: animalId === NO_PET ? null : animalId,
      });
      toast("Request sent. The practice will reply.", "success");
      setReason("");
      setTimeNote("");
      onRequested?.();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send the request.");
      setSubmitting(false);
      return;
    }
    setSubmitting(false);
  };

  const practice = vet.clinic_name ?? vet.display_name;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Request an appointment — ${practice}`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={() => void submit()} loading={submitting} disabled={!reason.trim()}>
            Send request
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">
          This sends your details to {practice} — it does not reserve a time. They will confirm,
          suggest another day, or decline, and only a confirmation puts anything on your calendar.
        </p>

        {pets.length > 0 && (
          <Select
            label="Which pet?"
            value={animalId}
            onChange={(event) => setAnimalId(event.target.value)}
            options={[
              { value: NO_PET, label: "Not about a specific pet" },
              ...pets.map((pet) => ({
                value: pet.id,
                label: `${pet.name} (${capitalize(pet.species)})`,
              })),
            ]}
            hint="Choosing a pet is what lets a confirmed appointment appear on your calendar."
          />
        )}

        <Textarea
          label="What is it about?"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder="Buddy has been limping on his back left leg for three days."
          rows={4}
          maxLength={1000}
          required
        />

        <Input
          label="Preferred date"
          type="date"
          value={preferredDate}
          min={todayValue()}
          onChange={(event) => setPreferredDate(event.target.value)}
          required
        />

        <Input
          label="Any time that suits you (optional)"
          value={timeNote}
          onChange={(event) => setTimeNote(event.target.value)}
          placeholder="Mornings, or after 5pm"
          maxLength={120}
        />

        {error && (
          <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
            {error}
          </p>
        )}
      </div>
    </Modal>
  );
}
