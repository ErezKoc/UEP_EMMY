import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError, getVeterinarians } from "../../api/client";
import { useSession } from "../../auth/SessionContext";
import AppointmentRequestDialog from "../../components/AppointmentRequestDialog";
import ClinicContact from "../../components/ClinicContact";
import EmergencyContactsPanel from "../../components/EmergencyContactsPanel";
import ReportButton from "../../components/ReportButton";
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
import type { Veterinarian } from "../../types";

export default function VetsPage() {
  const [draftQuery, setDraftQuery] = useState("");
  const [query, setQuery] = useState("");
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [acceptingOnly, setAcceptingOnly] = useState(false);
  // Which practice's request dialog is open, by id. Held here rather than in
  // each card so only one can be open at a time.
  const [requesting, setRequesting] = useState<string | null>(null);
  const { user } = useSession();
  const [vets, setVets] = useState<Veterinarian[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadVets = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      setVets(await getVeterinarians(query, verifiedOnly, acceptingOnly));
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Could not load veterinarians.");
    } finally {
      setIsLoading(false);
    }
  }, [query, verifiedOnly, acceptingOnly]);

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

      <label className="mt-3 inline-flex items-center gap-2 text-sm text-slate-600">
        <input
          type="checkbox"
          checked={verifiedOnly}
          onChange={(event) => setVerifiedOnly(event.target.checked)}
          className="h-4 w-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
        />
        Verified veterinarians only
      </label>

      <label className="mt-3 ml-4 inline-flex items-center gap-2 text-sm text-slate-600">
        <input
          type="checkbox"
          checked={acceptingOnly}
          onChange={(event) => setAcceptingOnly(event.target.checked)}
          className="h-4 w-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
        />
        Taking appointment requests
      </label>

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
                {vet.bio && <p className="mt-4 text-sm leading-relaxed text-slate-600">{vet.bio}</p>}

                <ClinicContact vet={vet} />

                {vet.accepts_appointments && (
                  <div className="mt-4">
                    {user ? (
                      <Button size="sm" onClick={() => setRequesting(vet.id)}>
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
                    open={requesting === vet.id}
                    onClose={() => setRequesting(null)}
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
