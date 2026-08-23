import { GlobeIcon, MailIcon, MapPinIcon, PhoneIcon } from "./ui";
import type { Veterinarian } from "../types";

/*
 * How to reach a practice.
 *
 * Ordered by what someone opening it actually needs, which is not the order the
 * fields happen to sit in on the record: the out-of-hours number first when
 * there is one, then the day number, then the address, then everything else.
 * The person reading this at eleven at night is not browsing.
 *
 * Every line is a real link — `tel:` and `mailto:` rather than text a phone
 * cannot dial — because the whole complaint that produced this component was
 * that finding a vet gave you a name and left you to go and look up the number
 * somewhere else.
 */

/** The address as a single line, or null when the practice gave us none. */
export function formatAddress(vet: Veterinarian): string | null {
  const parts = [
    vet.clinic_address_line,
    vet.clinic_city,
    vet.clinic_postcode,
    vet.clinic_country,
  ].filter((part): part is string => Boolean(part && part.trim()));
  return parts.length > 0 ? parts.join(", ") : null;
}

/**
 * A maps link built from the address text.
 *
 * Deliberately a plain search URL and not an embedded map: an iframe would mean
 * a third-party script on every page that lists a vet, an API key to keep
 * alive, and a component that breaks in a demo when the network is slow. A link
 * hands the address to whatever map app the person already uses.
 */
export function mapsUrl(address: string): string {
  return `https://www.openstreetmap.org/search?query=${encodeURIComponent(address)}`;
}

export function hasContactDetails(vet: Veterinarian): boolean {
  return Boolean(
    vet.clinic_phone ||
      vet.clinic_emergency_phone ||
      vet.clinic_email ||
      vet.clinic_website ||
      formatAddress(vet) ||
      vet.clinic_hours,
  );
}

function Row({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-2 text-sm">
      <span className="mt-0.5 shrink-0 text-slate-400" aria-hidden>
        {icon}
      </span>
      <div className="min-w-0">
        <span className="sr-only">{label}: </span>
        {children}
      </div>
    </div>
  );
}

export default function ClinicContact({ vet }: { vet: Veterinarian }) {
  const address = formatAddress(vet);

  if (!hasContactDetails(vet)) {
    /*
     * Said out loud rather than rendered as an empty space. A blank area under
     * a vet's name reads as "still loading" or as a layout bug; this reads as
     * what it is, and tells the owner what to do instead.
     */
    return (
      <p className="mt-4 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-500">
        This practice has not added contact details yet. You can still ask them a question in
        the community.
      </p>
    );
  }

  return (
    <div className="mt-4 space-y-2 border-t border-slate-100 pt-4">
      {/*
        First, and in red, because it is the one line here that matters at the
        moment it matters most. A practice that publishes an out-of-hours
        number has said this is where to ring when they are shut, and burying
        it under the switchboard number would waste that.
      */}
      {vet.clinic_emergency_phone && (
        <Row icon={<PhoneIcon className="h-4 w-4" />} label="Out-of-hours number">
          <a
            href={`tel:${vet.clinic_emergency_phone.replace(/\s+/g, "")}`}
            className="font-semibold text-rose-700 underline decoration-rose-300 underline-offset-2 hover:text-rose-800"
          >
            {vet.clinic_emergency_phone}
          </a>
          <span className="ml-1 text-xs font-medium uppercase tracking-wide text-rose-600">
            out of hours
          </span>
        </Row>
      )}

      {vet.clinic_phone && (
        <Row icon={<PhoneIcon className="h-4 w-4" />} label="Phone">
          <a
            href={`tel:${vet.clinic_phone.replace(/\s+/g, "")}`}
            className="font-medium text-slate-800 underline decoration-slate-300 underline-offset-2 hover:text-primary-700"
          >
            {vet.clinic_phone}
          </a>
        </Row>
      )}

      {address && (
        <Row icon={<MapPinIcon className="h-4 w-4" />} label="Address">
          <span className="text-slate-700">{address}</span>{" "}
          <a
            href={mapsUrl(address)}
            target="_blank"
            rel="noreferrer noopener"
            className="whitespace-nowrap text-xs font-medium text-primary-600 hover:text-primary-700"
          >
            Open in maps
          </a>
        </Row>
      )}

      {vet.clinic_hours && (
        <Row icon={<span className="block h-4 w-4" />} label="Opening hours">
          <span className="text-slate-600">{vet.clinic_hours}</span>
        </Row>
      )}

      {vet.clinic_email && (
        <Row icon={<MailIcon className="h-4 w-4" />} label="Email">
          <a
            href={`mailto:${vet.clinic_email}`}
            className="break-all text-slate-700 underline decoration-slate-300 underline-offset-2 hover:text-primary-700"
          >
            {vet.clinic_email}
          </a>
        </Row>
      )}

      {vet.clinic_website && (
        <Row icon={<GlobeIcon className="h-4 w-4" />} label="Website">
          <a
            href={vet.clinic_website}
            target="_blank"
            rel="noreferrer noopener"
            className="break-all text-primary-600 hover:text-primary-700"
          >
            {vet.clinic_website.replace(/^https?:\/\//, "")}
          </a>
        </Row>
      )}
    </div>
  );
}
