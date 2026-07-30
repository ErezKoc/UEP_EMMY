import { useCallback, useEffect, useState } from "react";
import { ApiError, decideVerification, getVerifications } from "../../api/client";
import {
  Avatar,
  Badge,
  Button,
  Card,
  EmptyState,
  ImageIcon,
  Modal,
  Select,
  ShieldCheckIcon,
  Spinner,
  Textarea,
  useToast,
} from "../../components/ui";
import { formatRelativeTime } from "../../lib/format";
import type { VerificationStatus, VetVerification } from "../../types";

const FILTER_OPTIONS = [
  { value: "pending", label: "Pending review" },
  { value: "verified", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "", label: "All submissions" },
];

/*
 * Approving grants the verified badge across the whole community, so every
 * decision is confirmed in a dialog before it is sent — a stray click on
 * "Approve" must never be enough to vouch for someone. Mistakes stay fixable:
 * an approved veterinarian can be revoked from the Approved tab.
 */
type Action = "verified" | "rejected" | "revoke";

interface PendingAction {
  item: VetVerification;
  action: Action;
}

const ACTION_COPY: Record<Action, { title: string; confirm: string; noteRequired: boolean }> = {
  verified: { title: "Approve verification", confirm: "Approve", noteRequired: false },
  rejected: { title: "Reject verification", confirm: "Reject", noteRequired: true },
  revoke: { title: "Revoke verification", confirm: "Revoke verification", noteRequired: true },
};

function SubmissionCard({
  item,
  onAct,
}: {
  item: VetVerification;
  onAct: (action: Action) => void;
}) {
  const isPending = item.status === "pending";

  return (
    <li className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <Avatar name={item.user.display_name} src={item.user.avatar_url} size="md" />
          <div className="min-w-0">
            <p className="font-semibold text-slate-800">{item.user.display_name}</p>
            <p className="text-sm text-slate-600">
              {item.user.clinic_name ?? "Independent veterinarian"}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Licence {item.license_number ?? "not provided"} · submitted{" "}
              {formatRelativeTime(item.created_at)}
            </p>
          </div>
        </div>
        <Badge
          variant={
            item.status === "verified" ? "success" : item.status === "rejected" ? "danger" : "warning"
          }
        >
          {item.status}
        </Badge>
      </div>

      <a
        href={item.document_url}
        target="_blank"
        rel="noreferrer"
        className="mt-4 inline-flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm font-medium text-primary-700 ring-1 ring-slate-200 hover:bg-slate-100"
      >
        <ImageIcon className="h-4 w-4" />
        Open submitted document
      </a>

      {isPending ? (
        <div className="mt-4 flex flex-wrap justify-end gap-2 border-t border-slate-100 pt-4">
          <Button variant="secondary" size="sm" onClick={() => onAct("rejected")}>
            Reject
          </Button>
          <Button size="sm" onClick={() => onAct("verified")}>
            Approve
          </Button>
        </div>
      ) : (
        <div className="mt-4 space-y-3 border-t border-slate-100 pt-4">
          <p className="text-xs text-slate-500">
            {item.status === "verified" ? "Approved" : "Rejected"}
            {item.reviewed_by_name ? ` by ${item.reviewed_by_name}` : ""}
            {item.reviewed_at ? ` · ${formatRelativeTime(item.reviewed_at)}` : ""}
          </p>
          {item.review_note && (
            <p className="text-sm text-slate-600">Note: {item.review_note}</p>
          )}
          {item.status === "verified" && (
            <div className="flex justify-end">
              <Button variant="danger" size="sm" onClick={() => onAct("revoke")}>
                Revoke verification
              </Button>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

export default function VerificationQueuePage() {
  const { toast } = useToast();
  const [filter, setFilter] = useState<VerificationStatus | "">("pending");
  const [items, setItems] = useState<VetVerification[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [pending, setPending] = useState<PendingAction | null>(null);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      setItems(await getVerifications(filter || undefined));
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Could not load the review queue.");
    } finally {
      setIsLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    void load();
  }, [load]);

  const openDialog = (item: VetVerification, action: Action) => {
    setNote("");
    setPending({ item, action });
  };

  const closeDialog = () => {
    if (submitting) return;
    setPending(null);
    setNote("");
  };

  const confirmAction = async () => {
    if (!pending) return;
    const { item, action } = pending;
    // "Revoke" is the same API call as a rejection; only the wording differs.
    const status = action === "verified" ? "verified" : "rejected";

    setSubmitting(true);
    try {
      const updated = await decideVerification(item.id, status, note);
      toast(
        action === "verified"
          ? `${item.user.display_name} is now a verified veterinarian.`
          : action === "revoke"
            ? `${item.user.display_name}'s verification was revoked.`
            : `${item.user.display_name}'s request was rejected.`,
        "success",
      );
      setItems((current) =>
        filter === "" || filter === updated.status
          ? current.map((row) => (row.id === updated.id ? updated : row))
          : current.filter((row) => row.id !== updated.id),
      );
      setPending(null);
      setNote("");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not save the decision.", "error");
    } finally {
      setSubmitting(false);
    }
  };

  const copy = pending ? ACTION_COPY[pending.action] : null;
  const noteMissing = copy?.noteRequired === true && note.trim() === "";

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-slate-800">
            <ShieldCheckIcon className="h-6 w-6 text-primary-600" />
            Veterinarian verification
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Approve licence documents so professional advice in the community is trustworthy.
          </p>
        </div>
        <div className="w-52">
          <Select
            label="Show"
            value={filter}
            onChange={(event) => setFilter(event.target.value as VerificationStatus | "")}
            options={FILTER_OPTIONS}
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
            <button onClick={() => void load()} className="font-medium underline">
              Retry
            </button>
          </div>
        )}

        {!isLoading && !loadError && items.length === 0 && (
          <Card>
            <EmptyState
              icon={<ShieldCheckIcon className="h-6 w-6" />}
              title={filter === "pending" ? "Nothing waiting for review" : "No submissions here"}
              description={
                filter === "pending"
                  ? "New verification requests will appear here as veterinarians submit them."
                  : "Try a different filter."
              }
            />
          </Card>
        )}

        {!isLoading && !loadError && items.length > 0 && (
          <ul className="space-y-4">
            {items.map((item) => (
              <SubmissionCard
                key={item.id}
                item={item}
                onAct={(action) => openDialog(item, action)}
              />
            ))}
          </ul>
        )}
      </div>

      <Modal
        open={pending !== null}
        onClose={closeDialog}
        title={copy?.title ?? ""}
        footer={
          <>
            <Button variant="secondary" onClick={closeDialog} disabled={submitting}>
              Cancel
            </Button>
            <Button
              variant={pending?.action === "verified" ? "primary" : "danger"}
              loading={submitting}
              disabled={noteMissing}
              onClick={() => void confirmAction()}
            >
              {copy?.confirm}
            </Button>
          </>
        }
      >
        {pending && (
          <div className="space-y-4">
            <p className="text-sm text-slate-600">
              {pending.action === "verified" && (
                <>
                  <strong className="text-slate-800">{pending.item.user.display_name}</strong> will
                  get the verified veterinarian badge on every post and comment, and appear in the
                  verified directory. Only approve after checking the document.
                </>
              )}
              {pending.action === "rejected" && (
                <>
                  <strong className="text-slate-800">{pending.item.user.display_name}</strong> will
                  not be verified. They can read your note and submit a new document.
                </>
              )}
              {pending.action === "revoke" && (
                <>
                  <strong className="text-slate-800">{pending.item.user.display_name}</strong> will
                  immediately lose the verified badge everywhere. Use this if an approval was given
                  by mistake.
                </>
              )}
            </p>

            <Textarea
              label={copy?.noteRequired ? "Reason (required)" : "Reviewer note (optional)"}
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder={
                pending.action === "verified"
                  ? "e.g. Licence confirmed with the chamber registry."
                  : "The veterinarian sees this, so explain what was wrong."
              }
              rows={3}
              maxLength={1000}
              hint={
                copy?.noteRequired
                  ? "The confirm button stays disabled until you give a reason."
                  : undefined
              }
            />
          </div>
        )}
      </Modal>
    </div>
  );
}
