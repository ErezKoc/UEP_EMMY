import { useEffect, useState } from "react";
import { getEmergencyContacts } from "../api/client";
import { AlertTriangleIcon, PhoneIcon } from "./ui";
import type { EmergencyContacts } from "../types";

/*
 * The numbers to call when no practice is open.
 *
 * Fails silently on purpose. If the request errors the panel renders nothing:
 * an error box headed "could not load emergency numbers" is alarming in
 * proportion to how urgent the section sounds, and it is not a state anybody
 * can act on. The rest of the page — the directory of practices, each with its
 * own number — is still there.
 *
 * The note above the list is served with it rather than written here, because
 * it carries the limitation that these are US services and that a poison line
 * cannot examine an animal. That sentence has to travel with the numbers.
 */
export default function EmergencyContactsPanel() {
  const [data, setData] = useState<EmergencyContacts | null>(null);

  useEffect(() => {
    let cancelled = false;
    getEmergencyContacts()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => {
        /* See the note above: no error state for this panel. */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!data || data.contacts.length === 0) return null;

  return (
    <section
      aria-labelledby="emergency-numbers"
      className="mt-6 rounded-lg border-2 border-rose-200 bg-rose-50 p-5"
    >
      <h2
        id="emergency-numbers"
        className="flex items-center gap-2 text-sm font-bold uppercase tracking-wide text-rose-800"
      >
        <AlertTriangleIcon className="h-4 w-4" />
        Emergency numbers
      </h2>

      <p className="mt-2 text-sm text-rose-900">{data.note}</p>

      <ul className="mt-4 space-y-4">
        {data.contacts.map((contact) => (
          <li key={contact.dial} className="rounded-lg bg-white/70 p-3">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <a
                href={`tel:${contact.dial}`}
                className="inline-flex items-center gap-2 text-lg font-bold text-rose-800 underline decoration-rose-300 underline-offset-4 hover:text-rose-900"
              >
                <PhoneIcon className="h-4 w-4" />
                {contact.phone}
              </a>
              <span className="text-sm font-semibold text-slate-700">{contact.name}</span>
              {/*
                Named per entry, not once at the top: somebody scanning for a
                number should not have to have read the paragraph above to know
                which country's service they are about to ring.
              */}
              <span className="text-xs text-slate-500">{contact.coverage}</span>
            </div>
            <p className="mt-1 text-sm text-slate-700">{contact.when}</p>
            {contact.caveat && <p className="mt-1 text-xs text-slate-500">{contact.caveat}</p>}
            <p className="mt-1 text-xs text-slate-400">
              Number published by{" "}
              <a
                href={contact.source_url}
                target="_blank"
                rel="noreferrer noopener"
                className="underline hover:text-slate-600"
              >
                {contact.source_name}
              </a>
              , read {contact.accessed}
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}
