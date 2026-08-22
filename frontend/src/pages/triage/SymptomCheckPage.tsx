import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError, assessSymptoms, createSymptomCheck, getAnimals } from "../../api/client";
import SymptomIntakeForm, { clearIntakeDraft } from "../../components/SymptomIntakeForm";
import TriageResultCard from "../../components/TriageResultCard";
import { Button, Card, HistoryIcon, StethoscopeIcon } from "../../components/ui";
import { useSession } from "../../auth/SessionContext";
import { capitalize } from "../../lib/format";
import { scrollIntoViewSafely } from "../../lib/scroll";
import type { AgeCategory, Animal, SymptomIntake, TriageAssessment } from "../../types";

/*
 * Symptom triage on its own, with no photo involved.
 *
 * The questions used to live on the analyze page, which tied advice to an
 * upload the owner might not have — and a worried owner should never have to
 * find a camera first. Species still matters (several rules in the backend's
 * rules.py are cat-only or dog-only), so it is asked directly here instead of
 * being inferred from an image. It is asked as the first step of the intake
 * flow rather than in a card above it, because it is a question like the
 * others and was the one most often left unanswered when it sat outside.
 */

const NO_PET = "";
const NO_SPECIES = "";

/*
 * A finished check outlives this component, because the two things an owner is
 * most likely to do next both unmount it: "Find a vet" navigates away, and
 * "Sign in" leaves for the login page. Both used to come back to an empty form
 * with the assessment gone — the worst moment to lose it, since the advice is
 * the reason they were sent looking in the first place.
 *
 * sessionStorage rather than a route or context value: it survives the reload a
 * browser does on some redirects, and it dies with the tab, which is the right
 * lifetime for a health answer on a possibly shared computer. The intake is
 * kept alongside the verdict so a guest who signs in can store the same check
 * they are looking at, rather than being asked to answer everything again.
 */
const PENDING_KEY = "symptom-check:pending";

interface PendingCheck {
  answers: SymptomIntake;
  petId: string | null;
  assessment: TriageAssessment;
  /** Id of the stored record, or null for a check that was never saved. */
  savedId: string | null;
}

function readPending(): PendingCheck | null {
  try {
    const raw = sessionStorage.getItem(PENDING_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PendingCheck;
    // A shape from an older build is discarded rather than half-rendered.
    return parsed?.assessment && parsed?.answers ? parsed : null;
  } catch {
    return null; // Private mode, quota, or corrupt JSON: start clean.
  }
}

function writePending(pending: PendingCheck | null): void {
  try {
    if (pending) sessionStorage.setItem(PENDING_KEY, JSON.stringify(pending));
    else sessionStorage.removeItem(PENDING_KEY);
  } catch {
    // Storage unavailable. The result still shows for this visit; it just will
    // not survive leaving the page, which is the old behaviour.
  }
}

export default function SymptomCheckPage() {
  const { user } = useSession();
  const [searchParams] = useSearchParams();
  const [pets, setPets] = useState<Animal[]>([]);
  // Restored once, on first render: a check left behind by "Find a vet" or by a
  // trip to the login page is still the one the owner is in the middle of.
  const [pending, setPending] = useState<PendingCheck | null>(readPending);
  const [selectedPetId, setSelectedPetId] = useState(
    () => readPending()?.petId ?? searchParams.get("pet") ?? NO_PET,
  );
  /*
   * Restored alongside the pet, for the same reason and from the same record.
   * "Find a vet" unmounts this page, so an owner who goes looking for a clinic
   * and comes back has already lost this once; without it, "Start over" then
   * drops them on step 1 with the species blank even though they answered it
   * two minutes ago. Only when no pet is linked — a linked pet carries its own
   * species and the manual answer is not asked.
   */
  const [species, setSpecies] = useState(() => {
    const restored = readPending();
    if (!restored || restored.petId) return NO_SPECIES;
    return restored.answers?.species ?? NO_SPECIES;
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const resultRef = useRef<HTMLDivElement>(null);
  const resultHeadingRef = useRef<HTMLHeadingElement>(null);
  // A result restored from storage is already at the top of a freshly loaded
  // page, and taking focus on load is the kind of thing that loses a keyboard
  // user their place. Only a result that ARRIVES gets the treatment.
  const hadResult = useRef(pending !== null);

  const assessment = pending?.assessment ?? null;
  const saved = pending?.savedId != null;

  const rememberPending = (next: PendingCheck | null) => {
    setPending(next);
    writePending(next);
  };

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

  /*
   * The result has to be read from the top. Submitting from the foot of a long
   * form used to leave the page scrolled exactly where it was, so the owner
   * landed in the middle of the reasoning with the urgency and the action
   * somewhere above them.
   */
  useEffect(() => {
    if (!assessment) {
      hadResult.current = false;
      return;
    }
    if (hadResult.current) return;
    hadResult.current = true;
    scrollIntoViewSafely(resultRef.current, "start");
    resultHeadingRef.current?.focus({ preventScroll: true });
  }, [assessment]);

  const selectedPet = pets.find((pet) => pet.id === selectedPetId);

  const handleReset = () => {
    // The result and every answer behind it. The species/pet choice is kept,
    // and is visible as a selected chip on the first step, so an owner checking
    // a second symptom for the same animal does not re-answer it.
    clearIntakeDraft();
    rememberPending(null);
    setError(null);
  };

  /*
   * The save a guest could not make at the time. Reached only after signing in
   * with a result already on screen, so the check that gets stored is exactly
   * the one being read — same answers, same pet, same verdict.
   */
  const handleSaveToHistory = async () => {
    if (!pending || pending.savedId) return;
    setBusy(true);
    setError(null);
    try {
      const check = await createSymptomCheck(pending.answers, pending.petId);
      rememberPending({
        ...pending,
        savedId: check.id,
        assessment: check.triage ?? pending.assessment,
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save this check.");
    } finally {
      setBusy(false);
    }
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
        if (check.triage) {
          rememberPending({
            answers,
            petId: selectedPetId || null,
            assessment: check.triage,
            savedId: check.id,
          });
          clearIntakeDraft();
        }
      } else {
        rememberPending({
          answers,
          petId: selectedPetId || null,
          assessment: await assessSymptoms(answers),
          savedId: null,
        });
        clearIntakeDraft();
      }
    } catch (err) {
      // The draft is deliberately left alone: every answer is still in the form
      // behind the retry button.
      setError(err instanceof ApiError ? err.message : "Could not assess the symptoms.");
    } finally {
      setBusy(false);
    }
  };

  /*
   * The next action, and nothing competing with it. Rendered inside the result
   * card directly beneath the advice, and again at the foot of the card, so it
   * is reachable without scrolling in either direction.
   */
  const findAVet = (
    <div className="flex flex-wrap gap-3">
      <Link to="/vets" className="w-full sm:w-auto">
        <Button
          size="lg"
          variant={assessment?.level === "red" ? "danger" : "primary"}
          className="min-h-11 w-full sm:w-auto"
        >
          <StethoscopeIcon className="h-5 w-5" />
          Find a vet
        </Button>
      </Link>
    </div>
  );

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Symptom checker</h1>
          <p className="mt-1 text-sm text-slate-500">
            Answer a few questions about how your pet is doing and get guidance on how urgently
            they should be seen. This is not a diagnosis, and no photo is needed.
          </p>
        </div>
        {user && (
          <Link
            to="/symptom-check/history"
            className="inline-flex min-h-11 shrink-0 items-center gap-2 rounded-lg bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm ring-1 ring-slate-300 transition hover:bg-slate-50 hover:text-primary-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600"
          >
            <HistoryIcon className="h-4 w-4" />
            Past checks
          </Link>
        )}
      </div>

      {assessment === null ? (
        <>
          <SymptomIntakeForm
            onSubmit={handleSubmit}
            busy={busy}
            pets={pets}
            selectedPetId={selectedPetId}
            onSelectPet={setSelectedPetId}
            species={species}
            onSelectSpecies={setSpecies}
            submitError={error}
          />

          <p className="text-center text-sm text-slate-500">
            Want a breed and age estimate instead?{" "}
            <Link to="/analyze" className="font-medium text-primary-600 underline">
              Analyze a photo
            </Link>
          </p>
        </>
      ) : (
        <>
          <div ref={resultRef} className="scroll-mt-4">
            <TriageResultCard
              triage={assessment}
              headingRef={resultHeadingRef}
              announce
              actions={findAVet}
              repeatActions={findAVet}
              answers={pending?.answers ?? null}
              petLabel={selectedPet ? `${selectedPet.name} (${capitalize(selectedPet.species)})` : null}
            />
          </div>

          {error && (
            <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
              {error}
            </p>
          )}

          {/*
            Secondary, and below the card on purpose. Saving a record and
            starting again are both housekeeping, and neither should sit next to
            "contact a vet now" asking for attention.
          */}
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-slate-500">
                {saved ? (
                  selectedPet ? (
                    <>Saved to {selectedPet.name}&apos;s history.</>
                  ) : (
                    <>Saved to your symptom check history (not linked to a pet).</>
                  )
                ) : user ? (
                  <>This check is not in your history yet.</>
                ) : (
                  <>
                    {/*
                      `from` sends the owner back to this page after signing in,
                      instead of to the dashboard. The result is still here when
                      they land, so the promise the link makes is one it keeps.
                    */}
                    <Link
                      to="/login"
                      state={{ from: "/symptom-check" }}
                      className="font-medium text-primary-600 underline"
                    >
                      Sign in
                    </Link>{" "}
                    to keep a record of this check — we will bring you back here.
                  </>
                )}
              </p>
              <div className="flex flex-wrap gap-2">
                {user && !saved && (
                  <Button
                    variant="secondary"
                    className="min-h-11"
                    loading={busy}
                    onClick={() => void handleSaveToHistory()}
                  >
                    Save to my history
                  </Button>
                )}
                <Button variant="secondary" className="min-h-11" onClick={handleReset}>
                  Start over
                </Button>
              </div>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
