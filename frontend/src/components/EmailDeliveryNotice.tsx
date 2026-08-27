import { useEffect, useState } from "react";
import { getEmailDelivery } from "../api/client";
import type { EmailDeliveryStatus } from "../types";

/**
 * Whether this deployment can actually send email, said out loud.
 *
 * Every screen that promises "check your inbox" needs this. Without it the
 * interface tells somebody an email is on its way from an installation that has
 * no mail server, and they wait for a message that was never going to arrive —
 * which is worse than being told plainly that this build writes messages to a
 * file instead.
 *
 * Renders nothing at all while loading, and nothing when delivery IS available:
 * a green "email works" badge on every auth screen is noise, and the absence of
 * a warning already means the normal thing.
 */
export function useEmailDelivery(): EmailDeliveryStatus | null {
  const [status, setStatus] = useState<EmailDeliveryStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    getEmailDelivery()
      .then((result) => {
        if (!cancelled) setStatus(result);
      })
      .catch(() => {
        // A capability probe that cannot load is not worth an error message.
        // The screen still works; it simply does not add the warning.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return status;
}

interface Props {
  /** What the reader was about to be promised, e.g. "verification emails". */
  what?: string;
  className?: string;
}

export default function EmailDeliveryNotice({ what = "emails", className = "" }: Props) {
  const status = useEmailDelivery();
  if (status === null || status.available) return null;

  return (
    <p
      role="status"
      className={`rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-900 ${className}`}
    >
      <span className="font-semibold">This server cannot send email.</span> No mail server is
      set up here, so {what} are written to the server&apos;s outbox as files instead of being
      delivered. Ask whoever runs this deployment for the message, or set up SMTP.
    </p>
  );
}
