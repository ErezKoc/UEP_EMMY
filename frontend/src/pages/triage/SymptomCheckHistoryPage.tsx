import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError, deleteSymptomCheck, getAnimals, getSymptomChecks } from "../../api/client";
import TriageResultCard from "../../components/TriageResultCard";
import {
  ArrowLeftIcon,
  Badge,
  Button,
  EmptyState,
  Select,
  Spinner,
  useToast,
} from "../../components/ui";
import { capitalize, formatRelativeTime } from "../../lib/format";
import type { Animal, SymptomCheck, TriageLevel } from "../../types";

const ALL_PETS = "";

const LEVEL_VARIANT: Record<TriageLevel, "danger" | "warning" | "success" | "neutral"> = {
  red: "danger",
  amber: "warning",
  green: "success",
  // Neutral, never "success" — an abstention is not a clean bill of health.
  unassessed: "neutral",
};

/** The concern is stored as a snake_case enum; show it the way the form did. */
function describeConcern(check: SymptomCheck): string {
  const concern = check.intake?.concern;
  if (!concern || concern === "breed_only") return "Symptom check";
  return capitalize(concern.replace(/_/g, " "));
}

function HistoryRow({ check, onDeleted }: { check: SymptomCheck; onDeleted: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const [removing, setRemoving] = useState(false);
  const { toast } = useToast();

  const handleDelete = async () => {
    setRemoving(true);
    try {
      await deleteSymptomCheck(check.id);
      toast("Symptom check deleted.", "success");
      onDeleted();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not delete the check.", "error");
      setRemoving(false);
    }
  };

  return (
    <li className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold text-slate-800">{describeConcern(check)}</span>
        {check.animal ? (
          <Badge variant="primary">{check.animal.name}</Badge>
        ) : (
          <Badge variant="neutral">Not linked</Badge>
        )}
        {check.triage && (
          <Badge variant={LEVEL_VARIANT[check.triage.level] ?? "neutral"}>
            {check.triage.headline}
          </Badge>
        )}
        <time className="ml-auto text-xs text-slate-400" dateTime={check.created_at}>
          {formatRelativeTime(check.created_at)}
        </time>
      </div>

      {check.triage ? (
        <>
          <p className="mt-2 text-sm text-slate-600">{check.triage.advice}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" onClick={() => setExpanded((open) => !open)}>
              {expanded ? "Hide details" : "Show details"}
            </Button>
            <Button variant="secondary" size="sm" onClick={handleDelete} disabled={removing}>
              {removing ? "Deleting…" : "Delete"}
            </Button>
          </div>
          {expanded && (
            <div className="mt-4">
              <TriageResultCard triage={check.triage} />
            </div>
          )}
        </>
      ) : (
        // Verdicts are stored verbatim, so one written before a rules change may
        // no longer be readable. The row still belongs in the timeline.
        <p className="mt-2 text-sm text-slate-500">
          This verdict was saved under an older version of the rules and can no longer be shown.
        </p>
      )}
    </li>
  );
}

export default function SymptomCheckHistoryPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const petFilter = searchParams.get("pet") ?? ALL_PETS;

  const [checks, setChecks] = useState<SymptomCheck[]>([]);
  const [pets, setPets] = useState<Animal[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    getAnimals()
      .then(setPets)
      .catch(() => setPets([]));
  }, []);

  const loadChecks = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      setChecks(await getSymptomChecks(petFilter === ALL_PETS ? null : petFilter));
    } catch (err) {
      setLoadError(
        err instanceof ApiError ? err.message : "Could not load your symptom checks.",
      );
    } finally {
      setIsLoading(false);
    }
  }, [petFilter]);

  useEffect(() => {
    void loadChecks();
  }, [loadChecks]);

  const filterOptions = useMemo(
    () => [
      { value: ALL_PETS, label: "All checks" },
      ...pets.map((pet) => ({ value: pet.id, label: `${pet.name} (${capitalize(pet.species)})` })),
    ],
    [pets],
  );

  return (
    <div className="mx-auto max-w-3xl">
      <Link
        to="/symptom-check"
        className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-primary-600 hover:text-primary-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600"
      >
        <ArrowLeftIcon className="h-4 w-4" />
        Back to symptom checker
      </Link>

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Symptom check history</h1>
          <p className="mt-1 text-sm text-slate-500">
            Every check you have run, newest first. Useful to show your vet how things changed.
          </p>
        </div>
        {pets.length > 0 && (
          <div className="w-56">
            <Select
              label="Filter by pet"
              value={petFilter}
              onChange={(event) => {
                const value = event.target.value;
                setSearchParams(value === ALL_PETS ? {} : { pet: value });
              }}
              options={filterOptions}
            />
          </div>
        )}
      </div>

      <div className="mt-6">
        {isLoading && (
          <div className="flex justify-center py-16">
            <Spinner />
          </div>
        )}

        {!isLoading && loadError && (
          <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
            {loadError}{" "}
            <button onClick={() => void loadChecks()} className="font-medium underline">
              Retry
            </button>
          </div>
        )}

        {!isLoading && !loadError && checks.length === 0 && (
          <EmptyState
            title={petFilter === ALL_PETS ? "No symptom checks yet" : "No checks for this pet yet"}
            description="Run a symptom check and the result will be kept here automatically."
            action={
              <Link to="/symptom-check">
                <Button>Run a symptom check</Button>
              </Link>
            }
          />
        )}

        {!isLoading && !loadError && checks.length > 0 && (
          <ul className="space-y-3">
            {checks.map((check) => (
              <HistoryRow key={check.id} check={check} onDeleted={() => void loadChecks()} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
