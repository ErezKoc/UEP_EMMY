import { useState } from "react";
import { ApiError, createReport } from "../api/client";
import { useSession } from "../auth/SessionContext";
import { Button, Modal, Textarea, useToast } from "./ui";
import type { ReportReason, ReportTargetType } from "../types";

/*
 * One dialog for every kind of report (post, comment, or profile), so the
 * checklist stays identical wherever a member reports from and administrators
 * receive comparable reports.
 */

const REASON_OPTIONS: Array<{ value: ReportReason; label: string; description: string }> = [
  {
    value: "offensive_language",
    label: "Offensive language",
    description: "Insults, slurs, or abusive wording.",
  },
  {
    value: "harassment",
    label: "Harassment or bullying",
    description: "Targeted attacks on a specific member.",
  },
  {
    value: "spam",
    label: "Spam or advertising",
    description: "Repetitive promotion unrelated to the discussion.",
  },
  {
    value: "impersonating_vet",
    label: "Pretending to be a veterinarian",
    description: "Claims professional credentials without a verified badge.",
  },
  {
    value: "harmful_advice",
    label: "Dangerous medical advice",
    description: "Guidance that could harm an animal if followed.",
  },
  {
    value: "animal_welfare",
    label: "Animal welfare concern",
    description: "Suggests neglect, cruelty, or mistreatment.",
  },
  {
    value: "graphic_content",
    label: "Graphic or disturbing content",
    description: "Distressing images or descriptions posted without warning.",
  },
  { value: "other", label: "Something else", description: "Explain it in the box below." },
];

const TARGET_NOUN: Record<ReportTargetType, string> = {
  post: "post",
  comment: "comment",
  user: "profile",
};

export interface ReportTarget {
  type: ReportTargetType;
  id: string;
  /** Who wrote it — shown in the dialog so nobody reports the wrong person. */
  authorName: string;
}

interface ReportDialogProps {
  open: boolean;
  onClose: () => void;
  target: ReportTarget | null;
}

export default function ReportDialog({ open, onClose, target }: ReportDialogProps) {
  const { user } = useSession();
  const { toast } = useToast();
  const [reasons, setReasons] = useState<ReportReason[]>([]);
  const [details, setDetails] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setReasons([]);
    setDetails("");
    setError(null);
  };

  const close = () => {
    if (submitting) return;
    reset();
    onClose();
  };

  const toggleReason = (reason: ReportReason) => {
    setReasons((current) =>
      current.includes(reason) ? current.filter((r) => r !== reason) : [...current, reason],
    );
  };

  const submit = async () => {
    if (!target || reasons.length === 0) return;
    setSubmitting(true);
    setError(null);
    try {
      await createReport({
        target_type: target.type,
        target_id: target.id,
        reasons,
        details: details.trim() || null,
      });
      toast("Report sent to the moderation team. Thank you.", "success");
      reset();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send the report.");
    } finally {
      setSubmitting(false);
    }
  };

  const noun = target ? TARGET_NOUN[target.type] : "content";
  // "Something else" without a written explanation tells a reviewer nothing.
  const explanationMissing = reasons.includes("other") && details.trim() === "";
  const blocked = user !== null && !user.can_participate;

  return (
    <Modal
      open={open}
      onClose={close}
      title={`Report this ${noun}`}
      footer={
        <>
          <Button variant="secondary" onClick={close} disabled={submitting}>
            Cancel
          </Button>
          <Button
            variant="danger"
            loading={submitting}
            disabled={reasons.length === 0 || explanationMissing || blocked}
            onClick={() => void submit()}
          >
            Send report
          </Button>
        </>
      }
    >
      {target && (
        <div className="space-y-4">
          <p className="text-sm text-slate-600">
            You are reporting {noun === "profile" ? "the profile of" : `a ${noun} by`}{" "}
            <strong className="text-slate-800">{target.authorName}</strong>. An administrator
            reviews every report and the author is not told who reported them.
          </p>

          <fieldset>
            <legend className="mb-2 text-sm font-medium text-slate-700">
              What is wrong with it? <span className="text-slate-400">(tick all that apply)</span>
            </legend>
            <div className="space-y-1">
              {REASON_OPTIONS.map((option) => (
                <label
                  key={option.value}
                  className="flex cursor-pointer gap-3 rounded-lg p-2 hover:bg-slate-50"
                >
                  <input
                    type="checkbox"
                    checked={reasons.includes(option.value)}
                    onChange={() => toggleReason(option.value)}
                    className="mt-0.5 h-4 w-4 shrink-0 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
                  />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-slate-800">{option.label}</span>
                    <span className="block text-xs text-slate-500">{option.description}</span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          <Textarea
            label="Anything else the reviewer should know? (optional)"
            value={details}
            onChange={(event) => setDetails(event.target.value)}
            placeholder="Add context — what happened, and why it is a problem."
            rows={3}
            maxLength={2000}
            hint={
              explanationMissing
                ? undefined
                : "Details help an administrator decide without guessing."
            }
            error={
              explanationMissing
                ? "Please explain the problem when choosing “Something else”."
                : undefined
            }
          />

          {blocked && (
            <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800" role="alert">
              Your account is currently restricted, so you cannot file reports.
            </p>
          )}
          {error && (
            <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
              {error}
            </p>
          )}
        </div>
      )}
    </Modal>
  );
}
