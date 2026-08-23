import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { ApiError, getAnalyses, getAnimals } from "../../api/client";
import {
  ArrowLeftIcon,
  Badge,
  Button,
  ChevronRightIcon,
  EmptyState,
  Select,
  Spinner,
} from "../../components/ui";
import { capitalize, formatRelativeTime } from "../../lib/format";
import { confidenceLabel, confidencePill } from "../../lib/confidence";
import type { AnalysisHistoryItem, Animal } from "../../types";

const ALL_PETS = "";

function HistoryRow({ item, backTo }: { item: AnalysisHistoryItem; backTo: string }) {
  const { result } = item;
  const topBreed = result.breed_candidates[0];
  return (
    <li>
      <Link
        to={`/analysis/${item.id}`}
        state={{ from: backTo }}
        className="group flex items-center gap-4 rounded-xl border border-slate-200 bg-white p-4 transition hover:border-primary-300 hover:shadow-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600"
      >
        <img
          src={item.image_url}
          alt={`Analyzed ${result.species}`}
          className="h-16 w-16 shrink-0 rounded-lg object-cover ring-1 ring-slate-200"
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-slate-800 group-hover:text-primary-700">
              {capitalize(result.species)}
            </span>
            {/*
              The band, not the bare percentage. This row said "91% confidence",
              which reads as "right 91% of the time" — a claim about measured
              accuracy that nobody has measured. The figure is still on the
              analysis's own page, after the word that frames it.
            */}
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-semibold ${confidencePill(
                result.species_confidence,
              )}`}
            >
              {confidenceLabel(result.species_confidence)}
            </span>
            {item.animal ? (
              <Badge variant="primary">{item.animal.name}</Badge>
            ) : (
              <Badge variant="neutral">Not linked</Badge>
            )}
            {/*
              So a corrected row is recognisable without opening it. The list is
              where an owner goes looking for the one they fixed, and every row
              otherwise shows the app's own guess as though nobody had disagreed.
            */}
            {item.correction && <Badge variant="primary">Corrected</Badge>}
            {item.triage && (
              <Badge
                variant={
                  item.triage.level === "red"
                    ? "danger"
                    : item.triage.level === "amber"
                      ? "warning"
                      : // Only an explicit `green` earns the success styling.
                        // `unassessed` — and any level a stored verdict carries
                        // that this build does not know — stays neutral.
                        item.triage.level === "green"
                        ? "success"
                        : "neutral"
                }
              >
                {item.triage.headline}
              </Badge>
            )}
          </div>
          <p className="mt-1 truncate text-sm text-slate-600">
            {/*
              "Likely X (62%)" hard-coded the word "Likely" regardless of how
              weak the match was, then put a bare percentage beside it. The word
              now comes from the figure instead of contradicting it.
            */}
            {topBreed
              ? `${confidenceLabel(topBreed.confidence)}: ${topBreed.breed}`
              : "No breed estimate"}
            {" / "}
            {result.age_estimate.category} age
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2 text-slate-400">
          <time className="hidden text-xs sm:block" dateTime={item.created_at}>
            {formatRelativeTime(item.created_at)}
          </time>
          <ChevronRightIcon className="h-5 w-5 transition group-hover:translate-x-0.5 group-hover:text-primary-600" />
        </div>
      </Link>
    </li>
  );
}

export default function AnalysisHistoryPage() {
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const petFilter = searchParams.get("pet") ?? ALL_PETS;

  const [items, setItems] = useState<AnalysisHistoryItem[]>([]);
  const [pets, setPets] = useState<Animal[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    getAnimals()
      .then(setPets)
      .catch(() => setPets([]));
  }, []);

  const loadItems = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      setItems(await getAnalyses(petFilter === ALL_PETS ? null : petFilter));
    } catch (err) {
      setLoadError(
        err instanceof ApiError ? err.message : "Could not load the history. Is the backend running?",
      );
    } finally {
      setIsLoading(false);
    }
  }, [petFilter]);

  useEffect(() => {
    void loadItems();
  }, [loadItems]);

  const filterOptions = useMemo(
    () => [
      { value: ALL_PETS, label: "All analyses" },
      ...pets.map((pet) => ({ value: pet.id, label: `${pet.name} (${capitalize(pet.species)})` })),
    ],
    [pets],
  );

  return (
    <div className="mx-auto max-w-3xl">
      <Link
        to="/analyze"
        className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-primary-600 hover:text-primary-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600"
      >
        <ArrowLeftIcon className="h-4 w-4" />
        Back to analyze
      </Link>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Analysis history</h1>
          <p className="mt-1 text-sm text-slate-500">
            Select an analysis to inspect its full results and reported symptoms.
          </p>
        </div>
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
            <button onClick={() => void loadItems()} className="font-medium underline">
              Retry
            </button>
          </div>
        )}

        {!isLoading && !loadError && items.length === 0 && (
          <EmptyState
            title={petFilter === ALL_PETS ? "No analyses yet" : "No analyses for this pet yet"}
            description="Upload a photo and the result will be stored here automatically."
            action={
              <Link to={petFilter === ALL_PETS ? "/analyze" : `/analyze?pet=${petFilter}`}>
                <Button>Analyze a photo</Button>
              </Link>
            }
          />
        )}

        {!isLoading && !loadError && items.length > 0 && (
          <ul className="space-y-3">
            {items.map((item) => (
              <HistoryRow
                key={item.id}
                item={item}
                backTo={`${location.pathname}${location.search}`}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
