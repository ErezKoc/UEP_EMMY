import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError, getVeterinarians } from "../../api/client";
import { useSession } from "../../auth/SessionContext";
import AppointmentRequestDialog from "../../components/AppointmentRequestDialog";
import ClinicContact from "../../components/ClinicContact";
import EmergencyContactsPanel from "../../components/EmergencyContactsPanel";
import ReportButton from "../../components/ReportButton";
import VetAvailability from "../../components/VetAvailability";
import VetFilters, { EMPTY_FILTERS } from "../../components/VetFilters";
import type { Position, VetFilterState } from "../../components/VetFilters";
import {
  Avatar,
  Badge,
  Button,
  CalendarIcon,
  EmptyState,
  RoleBadge,
  SearchIcon,
  Spinner,
  StethoscopeIcon,
} from "../../components/ui";
import { formatDate } from "../../lib/format";
import type { AvailabilitySlot, Veterinarian } from "../../types";


/*
 * The five things somebody is actually comparing, on one line each.
 *
 * Every one of them is missing for some practices, and every one says so in
 * words rather than by absence. "Hours not listed" and "closed" are different
 * facts and only one of them is ours to state; a card that just showed nothing
 * would leave the reader to guess, and in a directory they are searching with
 * a sick animal they will guess the worse way.
 */
function VetSignals({ vet }: { vet: Veterinarian }) {
  const fee =
    vet.consultation_fee_min == null
      ? null
      : vet.consultation_fee_max != null && vet.consultation_fee_max !== vet.consultation_fee_min
        ? `${vet.consultation_fee_min}–${vet.consultation_fee_max} ${vet.fee_currency ?? ""}`.trim()
        : `from ${vet.consultation_fee_min} ${vet.fee_currency ?? ""}`.trim();

  return (
    <div className="mt-3 space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        {vet.open_now === true && (
          <span className="rounded-full bg-emerald-100 px-2 py-0.5 font-semibold text-emerald-800">
            Open now{vet.closes_at ? ` · until ${vet.closes_at}` : ""}
          </span>
        )}
        {vet.open_now === false && (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 font-semibold text-slate-600">
            Closed
            {vet.opens_at ? ` · opens ${vet.opens_at}${vet.opens_day ? ` ${vet.opens_day}` : ""}` : ""}
          </span>
        )}
        {/*
          The third state, spelled out. A boolean would have to call this
          "closed", and telling somebody a clinic is shut when nobody ever said
          so is the one mistake here that ends with a pet not being seen.

          Two different sentences, because a practice can have perfectly clear
          written hours and no machine-readable grid - and "Hours not listed"
          printed directly above "Every day 09:00-19:00" reads as a bug in the
          page rather than as a limit on what the filter can see.
        */}
        {vet.open_now === null &&
          (vet.clinic_hours ? (
            <span className="rounded-full bg-slate-50 px-2 py-0.5 text-slate-500 ring-1 ring-slate-200">
              See hours below
            </span>
          ) : (
            <span className="rounded-full bg-slate-50 px-2 py-0.5 text-slate-500 ring-1 ring-slate-200">
              Hours not listed
            </span>
          ))}

        {vet.distance_km != null && (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 font-semibold text-slate-700">
            {vet.distance_km} km away
          </span>
        )}

        {fee && (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 font-semibold text-slate-700">
            Consultation {fee}
          </span>
        )}

        {vet.next_slot_date && (
          <span className="rounded-full bg-primary-50 px-2 py-0.5 font-semibold text-primary-700">
            Next published time {formatDate(vet.next_slot_date)}
            {vet.next_slot_time ? ` at ${vet.next_slot_time.slice(0, 5)}` : ""}
          </span>
        )}
      </div>

      {vet.specialty_labels.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {vet.specialty_labels.map((label) => (
            <span
              key={label}
              className="rounded-full bg-teal-50 px-2 py-0.5 text-xs font-medium text-teal-800"
            >
              {label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function VetsPage() {
  const [draftQuery, setDraftQuery] = useState("");
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<VetFilterState>(EMPTY_FILTERS);
  // Which practice's request dialog is open, by id. Held here rather than in
  // each card so only one can be open at a time.
  const [requesting, setRequesting] = useState<string | null>(null);
  // The published opening the owner picked, if they picked one. Handed to the
  // dialog so the request names the exact time rather than describing it.
  const [pickedSlot, setPickedSlot] = useState<AvailabilitySlot | null>(null);
  const { user } = useSession();
  const [vets, setVets] = useState<Veterinarian[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  /*
   * Location is asked for, never assumed, and a refusal is not an error.
   *
   * Somebody declining to share where they are has answered the question; the
   * directory carries on without distances rather than nagging. The message
   * below says what was lost, not that they did something wrong.
   */
  const [position, setPosition] = useState<Position | null>(null);
  const [locating, setLocating] = useState(false);
  const [locationError, setLocationError] = useState<string | null>(null);

  const locate = () => {
    if (!navigator.geolocation) {
      setLocationError("This browser cannot share a location, so distances are unavailable.");
      return;
    }
    setLocating(true);
    setLocationError(null);
    navigator.geolocation.getCurrentPosition(
      (found) => {
        setPosition({ lat: found.coords.latitude, lng: found.coords.longitude });
        setLocating(false);
      },
      () => {
        setLocating(false);
        setLocationError(
          "No location shared, so distances are not shown. Everything else still works.",
        );
      },
      { timeout: 10_000 },
    );
  };

  const loadVets = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      setVets(
        await getVeterinarians({
          q: query,
          verifiedOnly: filters.verifiedOnly,
          acceptingOnly: filters.acceptingOnly,
          lat: position?.lat ?? null,
          lng: position?.lng ?? null,
          radiusKm: filters.radiusKm,
          specialties: filters.specialties,
          openNow: filters.openNow,
          maxFee: filters.maxFee,
          hasAvailability: filters.hasAvailability,
          availabilityDays: 30,
          sort: filters.sort,
        }),
      );
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Could not load veterinarians.");
    } finally {
      setIsLoading(false);
    }
  }, [query, filters, position]);

  useEffect(() => {
    void loadVets();
  }, [loadVets]);

  const handleSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setQuery(draftQuery.trim());
  };

  return (
    <div className="mx-auto max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Veterinarians</h1>
        <p className="mt-1 text-sm text-slate-500">
          Contact details, opening hours and appointment requests for the practices on this
          platform.
        </p>
      </div>

      <EmergencyContactsPanel />

      <form onSubmit={handleSearch} className="mt-6 flex max-w-xl gap-2">
        <label htmlFor="vet-search" className="sr-only">Search veterinarians</label>
        <div className="relative min-w-0 flex-1">
          <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            id="vet-search"
            type="search"
            value={draftQuery}
            onChange={(event) => setDraftQuery(event.target.value)}
            placeholder="Search by name, clinic, city or postcode"
            className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-100"
          />
        </div>
        <Button type="submit" variant="secondary">Search</Button>
      </form>

      <VetFilters
        value={filters}
        onChange={setFilters}
        position={position}
        onLocate={locate}
        locating={locating}
        locationError={locationError}
      />

      <div className="mt-6">
        {isLoading && <div className="flex justify-center py-16"><Spinner /></div>}
        {!isLoading && loadError && (
          <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
            {loadError} <button onClick={() => void loadVets()} className="font-medium underline">Retry</button>
          </div>
        )}
        {!isLoading && !loadError && vets.length === 0 && (
          <EmptyState
            icon={<StethoscopeIcon className="h-6 w-6" />}
            title="No veterinarians found"
            description={query ? "Try a different name or clinic." : "No veterinarian profiles are available yet."}
            action={query ? <Button variant="secondary" onClick={() => { setDraftQuery(""); setQuery(""); }}>Clear search</Button> : undefined}
          />
        )}
        {!isLoading && !loadError && vets.length > 0 && (
          <ul className="grid gap-4 md:grid-cols-2">
            {vets.map((vet) => (
              <li key={vet.id} className="rounded-lg border border-slate-200 bg-white p-5">
                <div className="flex items-start gap-4">
                  <Avatar name={vet.display_name} src={vet.avatar_url} size="lg" />
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="font-semibold text-slate-800">{vet.display_name}</h2>
                      <RoleBadge user={vet} />
                      {vet.accepts_appointments && (
                        <Badge variant="success">Takes appointments</Badge>
                      )}
                    </div>
                    <p className="mt-1 text-sm font-medium text-slate-600">{vet.clinic_name ?? "Independent veterinarian"}</p>
                    {vet.license_number && <p className="mt-1 text-xs text-slate-400">License {vet.license_number}</p>}
                  </div>
                </div>
                <VetSignals vet={vet} />

                {vet.bio && <p className="mt-4 text-sm leading-relaxed text-slate-600">{vet.bio}</p>}

                <ClinicContact vet={vet} />

                <VetAvailability
                  vet={vet}
                  canRequest={Boolean(user) && vet.accepts_appointments}
                  onPick={(slot) => {
                    setPickedSlot(slot);
                    setRequesting(vet.id);
                  }}
                />

                {vet.accepts_appointments && (
                  <div className="mt-4">
                    {user ? (
                      <Button
                        size="sm"
                        onClick={() => {
                          setPickedSlot(null);
                          setRequesting(vet.id);
                        }}
                      >
                        <CalendarIcon className="h-4 w-4" />
                        Request an appointment
                      </Button>
                    ) : (
                      /*
                        Signed out, the button would open a dialog that could
                        only fail on submit. The link says what is needed
                        instead, and RequireAuth brings them back here.
                      */
                      <Link to="/login" state={{ from: "/vets" }}>
                        <Button size="sm" variant="secondary">
                          <CalendarIcon className="h-4 w-4" />
                          Sign in to request an appointment
                        </Button>
                      </Link>
                    )}
                  </div>
                )}

                {user && (
                  <AppointmentRequestDialog
                    vet={vet}
                    slot={requesting === vet.id ? pickedSlot : null}
                    open={requesting === vet.id}
                    onClose={() => {
                      setRequesting(null);
                      setPickedSlot(null);
                    }}
                  />
                )}

                <div className="mt-3 flex justify-end">
                  <ReportButton
                    authorId={vet.id}
                    target={{ type: "user", id: vet.id, authorName: vet.display_name }}
                    label="Report profile"
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
