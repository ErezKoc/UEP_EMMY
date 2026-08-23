import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, decideReport, getReports } from "../../api/client";
import type { ReportDecisionPayload } from "../../api/client";
import {
  Avatar,
  Badge,
  BanIcon,
  Button,
  Card,
  EmptyState,
  FlagIcon,
  GavelIcon,
  Modal,
  RoleBadge,
  Select,
  Spinner,
  Textarea,
  useToast,
} from "../../components/ui";
import { formatRelativeTime, formatShortDate } from "../../lib/format";
import type { ModerationAction, ReportReason, ReportStatus, UserReport } from "../../types";

const FILTER_OPTIONS = [
  { value: "pending", label: "Awaiting review" },
  { value: "actioned", label: "Actioned" },
  { value: "dismissed", label: "Dismissed" },
  { value: "", label: "All reports" },
];

const REASON_LABELS: Record<ReportReason, string> = {
  offensive_language: "Offensive language",
  harassment: "Harassment",
  spam: "Spam",
  impersonating_vet: "Pretending to be a vet",
  harmful_advice: "Dangerous medical advice",
  animal_welfare: "Animal welfare concern",
  graphic_content: "Graphic content",
  other: "Something else",
};

const SUSPEND_PRESETS = [
  { value: "3", label: "3 days" },
  { value: "7", label: "7 days" },
  { value: "30", label: "30 days" },
  { value: "90", label: "90 days" },
];

/*
 * Suspending or banning silences a member across the whole platform, so — like
 * approving a verification — every decision is confirmed in a dialog and every
 * penalty carries a written reason the member gets to read. Decisions stay
 * reversible: an actioned report can be reinstated from the Actioned filter.
 */
type Action = "dismiss" | ModerationAction;

interface PendingDecision {
  item: UserReport;
  action: Action;
}

const ACTION_COPY: Record<Action, { title: string; confirm: string; noteRequired: boolean }> = {
  dismiss: { title: "Dismiss report", confirm: "Dismiss report", noteRequired: false },
  suspend: { title: "Suspend account", confirm: "Suspend account", noteRequired: true },
  ban: { title: "Ban account", confirm: "Ban account", noteRequired: true },
  reinstate: { title: "Reinstate account", confirm: "Reinstate account", noteRequired: true },
};

function AccountStatusBadge({ item }: { item: UserReport }) {
  const status = item.reported_user.account_status;
  if (status === "banned") return <Badge variant="danger">Banned</Badge>;
  if (status === "suspended") {
    const until = item.reported_user.suspended_until;
    return (
      <Badge variant="warning">
        Suspended{until ? ` until ${formatShortDate(until)}` : ""}
      </Badge>
    );
  }
  return <Badge variant="success">Active</Badge>;
}

function ReportCard({ item, onAct }: { item: UserReport; onAct: (action: Action) => void }) {
  const isPending = item.status === "pending";
  const targetLabel =
    item.target_type === "post" ? "post" : item.target_type === "comment" ? "comment" : "profile";

  return (
    <li className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <Avatar
            name={item.reported_user.display_name}
            src={item.reported_user.avatar_url}
            size="md"
          />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-semibold text-slate-800">{item.reported_user.display_name}</p>
              <RoleBadge user={item.reported_user} />
            </div>
            <p className="text-sm text-slate-600">{item.reported_user.email}</p>
            <p className="mt-1 text-xs text-slate-500">
              Reported {formatRelativeTime(item.created_at)} by {item.reporter.display_name} ·{" "}
              {targetLabel}
            </p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-2">
          <Badge
            variant={
              item.status === "actioned"
                ? "danger"
                : item.status === "dismissed"
                  ? "neutral"
                  : "warning"
            }
          >
            {item.status}
          </Badge>
          <AccountStatusBadge item={item} />
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-1.5">
        {item.reasons.map((reason) => (
          <Badge key={reason} variant="primary">
            {REASON_LABELS[reason] ?? reason}
          </Badge>
        ))}
      </div>

      {item.details && (
        <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">
          <span className="font-medium text-slate-500">Reporter's explanation: </span>
          {item.details}
        </p>
      )}

      {/* The text as it read when reported, so the review holds up even if the
          author edited or deleted it since. */}
      {item.content_snapshot && (
        <blockquote className="mt-3 border-l-4 border-slate-200 bg-white pl-3 text-sm leading-relaxed whitespace-pre-line text-slate-600">
          {item.content_snapshot}
        </blockquote>
      )}

      {item.post_id && (
        <Link
          to={`/community/${item.post_id}`}
          className="mt-3 inline-block text-sm font-medium text-primary-600 hover:text-primary-700"
        >
          Open the discussion →
        </Link>
      )}

      {isPending ? (
        <div className="mt-4 flex flex-wrap justify-end gap-2 border-t border-slate-100 pt-4">
          <Button variant="secondary" size="sm" onClick={() => onAct("dismiss")}>
            Dismiss
          </Button>
          <Button variant="secondary" size="sm" onClick={() => onAct("suspend")}>
            Suspend
          </Button>
          <Button variant="danger" size="sm" onClick={() => onAct("ban")}>
            <BanIcon className="h-4 w-4" />
            Ban
          </Button>
        </div>
      ) : (
        <div className="mt-4 space-y-3 border-t border-slate-100 pt-4">
          <p className="text-xs text-slate-500">
            {item.action_taken === "suspend"
              ? "Account suspended"
              : item.action_taken === "ban"
                ? "Account banned"
                : item.action_taken === "reinstate"
                  ? "Account reinstated"
                  : "Dismissed — no action taken"}
            {item.reviewed_by_name ? ` by ${item.reviewed_by_name}` : ""}
            {item.reviewed_at ? ` · ${formatRelativeTime(item.reviewed_at)}` : ""}
          </p>
          {item.review_note && <p className="text-sm text-slate-600">Note: {item.review_note}</p>}
          {item.reported_user.account_status !== "active" && (
            <div className="flex justify-end">
              <Button variant="secondary" size="sm" onClick={() => onAct("reinstate")}>
                Reinstate account
              </Button>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

export default function ReportQueuePage() {
  const { toast } = useToast();
  const [filter, setFilter] = useState<ReportStatus | "">("pending");
  const [items, setItems] = useState<UserReport[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [pending, setPending] = useState<PendingDecision | null>(null);
  const [note, setNote] = useState("");
  const [suspendDays, setSuspendDays] = useState("7");
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      setItems(await getReports(filter || undefined));
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Could not load the moderation queue.");
    } finally {
      setIsLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    void load();
  }, [load]);

  const openDialog = (item: UserReport, action: Action) => {
    setNote("");
    setSuspendDays("7");
    setPending({ item, action });
  };

  const closeDialog = () => {
    if (submitting) return;
    setPending(null);
    setNote("");
  };

  const confirmDecision = async () => {
    if (!pending) return;
    const { item, action } = pending;

    const payload: ReportDecisionPayload =
      action === "dismiss"
        ? { dismiss: true, review_note: note }
        : action === "suspend"
          ? { action: "suspend", suspend_days: Number(suspendDays), review_note: note }
          : { action, review_note: note };

    setSubmitting(true);
    try {
      const updated = await decideReport(item.id, payload);
      const name = item.reported_user.display_name;
      toast(
        action === "dismiss"
          ? `Report about ${name} dismissed.`
          : action === "suspend"
            ? `${name} is suspended for ${suspendDays} days.`
            : action === "ban"
              ? `${name} has been banned.`
              : `${name}'s account was reinstated.`,
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
            <GavelIcon className="h-6 w-6 text-primary-600" />
            Reported content
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Review what members have reported, and suspend or ban accounts that break the rules.
          </p>
        </div>
        <div className="w-52">
          <Select
            label="Show"
            value={filter}
            onChange={(event) => setFilter(event.target.value as ReportStatus | "")}
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
              icon={<FlagIcon className="h-6 w-6" />}
              title={filter === "pending" ? "Nothing to review" : "No reports here"}
              description={
                filter === "pending"
                  ? "Reports from the community will appear here as members submit them."
                  : "Try a different filter."
              }
            />
          </Card>
        )}

        {!isLoading && !loadError && items.length > 0 && (
          <ul className="space-y-4">
            {items.map((item) => (
              <ReportCard key={item.id} item={item} onAct={(action) => openDialog(item, action)} />
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
              variant={pending?.action === "dismiss" ? "primary" : "danger"}
              loading={submitting}
              disabled={noteMissing}
              onClick={() => void confirmDecision()}
            >
              {copy?.confirm}
            </Button>
          </>
        }
      >
        {pending && (
          <div className="space-y-4">
            <p className="text-sm text-slate-600">
              {pending.action === "dismiss" && (
                <>
                  The report about{" "}
                  <strong className="text-slate-800">
                    {pending.item.reported_user.display_name}
                  </strong>{" "}
                  is closed with no penalty. Their account is unaffected.
                </>
              )}
              {pending.action === "suspend" && (
                <>
                  <strong className="text-slate-800">
                    {pending.item.reported_user.display_name}
                  </strong>{" "}
                  will not be able to post, comment, or report until the suspension lapses. They can
                  still sign in and read your reason.
                </>
              )}
              {pending.action === "ban" && (
                <>
                  <strong className="text-slate-800">
                    {pending.item.reported_user.display_name}
                  </strong>{" "}
                  will be locked out of the platform indefinitely and cannot sign in again. Use this
                  only for serious or repeated violations.
                </>
              )}
              {pending.action === "reinstate" && (
                <>
                  <strong className="text-slate-800">
                    {pending.item.reported_user.display_name}
                  </strong>{" "}
                  regains full access immediately. Use this if a penalty was given by mistake or the
                  appeal succeeded.
                </>
              )}
            </p>

            {pending.action === "suspend" && (
              <Select
                label="Suspension length"
                value={suspendDays}
                onChange={(event) => setSuspendDays(event.target.value)}
                options={SUSPEND_PRESETS}
                hint="The account unlocks automatically when this runs out."
              />
            )}

            <Textarea
              label={copy?.noteRequired ? "Reason (required)" : "Reviewer note (optional)"}
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder={
                pending.action === "dismiss"
                  ? "e.g. Checked the thread; nothing against the rules."
                  : "The member sees this, so explain which rule was broken."
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
