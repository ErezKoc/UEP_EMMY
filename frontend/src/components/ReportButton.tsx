import { useState } from "react";
import { useSession } from "../auth/SessionContext";
import ReportDialog from "./ReportDialog";
import type { ReportTarget } from "./ReportDialog";
import { FlagIcon } from "./ui";

/**
 * Drop-in "Report" control for a post, comment, or profile.
 *
 * Renders nothing for signed-out visitors or on your own content, so the action
 * only appears where it is actually usable.
 */
export default function ReportButton({
  target,
  authorId,
  className = "",
  label = "Report",
}: {
  target: ReportTarget;
  /** The author's user id, used to hide the control on your own content. */
  authorId: string;
  className?: string;
  label?: string;
}) {
  const { user } = useSession();
  const [open, setOpen] = useState(false);

  if (!user || user.id === authorId || user.role === "admin") return null;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={`inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-medium text-slate-500 transition-colors hover:bg-rose-50 hover:text-rose-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600 ${className}`}
        aria-label={`${label} — ${target.authorName}`}
      >
        <FlagIcon className="h-3.5 w-3.5" />
        {label}
      </button>
      <ReportDialog open={open} onClose={() => setOpen(false)} target={target} />
    </>
  );
}
