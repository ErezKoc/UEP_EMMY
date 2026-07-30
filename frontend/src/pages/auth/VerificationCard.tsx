import { useEffect, useRef, useState } from "react";
import type { ChangeEvent } from "react";
import { ApiError, getMyVerifications, submitVerification } from "../../api/client";
import { useSession } from "../../auth/SessionContext";
import {
  Badge,
  Button,
  Card,
  ClockIcon,
  ShieldCheckIcon,
  Spinner,
  useToast,
} from "../../components/ui";
import { formatRelativeTime } from "../../lib/format";
import type { User, VetVerification } from "../../types";

const DOCUMENT_TYPES = ["image/jpeg", "image/png", "image/webp", "application/pdf"];
const MAX_DOCUMENT_MB = 10;

/**
 * Licence verification panel on a veterinarian's own profile.
 *
 * Shown only to veterinarians: submit proof of licence, watch the review state,
 * read the reviewer's note, and resubmit after a rejection.
 */
export default function VerificationCard({ user }: { user: User }) {
  const { setUser } = useSession();
  const { toast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [history, setHistory] = useState<VetVerification[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getMyVerifications()
      .then((items) => {
        if (!cancelled) setHistory(items);
      })
      .catch(() => {
        if (!cancelled) setHistory([]);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!DOCUMENT_TYPES.includes(file.type)) {
      toast("Please upload a JPEG, PNG, WebP, or PDF document.", "error");
      return;
    }
    if (file.size > MAX_DOCUMENT_MB * 1024 * 1024) {
      toast(`The document must be smaller than ${MAX_DOCUMENT_MB} MB.`, "error");
      return;
    }

    setUploading(true);
    try {
      const created = await submitVerification(file);
      setHistory((current) => [created, ...current]);
      // Mirror the new pending state into the session so badges update at once.
      setUser({ ...user, verification_status: "pending", is_verified_vet: false });
      toast("Document submitted — an administrator will review it.", "success");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not submit the document.", "error");
    } finally {
      setUploading(false);
    }
  };

  const latest = history[0];
  const status = user.verification_status;
  const canSubmit = status === "unverified" || status === "rejected";

  return (
    <Card
      title="Professional verification"
      description="Verified veterinarians are marked across the community, so pet owners know whose advice to trust."
    >
      <div className="mt-5 space-y-4">
        {isLoading ? (
          <div className="flex justify-center py-6">
            <Spinner />
          </div>
        ) : (
          <>
            {status === "verified" && (
              <div className="flex items-start gap-3 rounded-lg bg-teal-50 p-4 ring-1 ring-teal-200">
                <ShieldCheckIcon className="mt-0.5 h-5 w-5 shrink-0 text-teal-700" />
                <div>
                  <p className="text-sm font-semibold text-teal-800">
                    Your licence is verified
                  </p>
                  <p className="mt-1 text-sm text-teal-700">
                    Your answers in the community carry the verified veterinarian badge.
                  </p>
                </div>
              </div>
            )}

            {status === "pending" && (
              <div className="flex items-start gap-3 rounded-lg bg-amber-50 p-4 ring-1 ring-amber-200">
                <ClockIcon className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" />
                <div>
                  <p className="text-sm font-semibold text-amber-900">Under review</p>
                  <p className="mt-1 text-sm text-amber-800">
                    Submitted {latest ? formatRelativeTime(latest.created_at) : "recently"}. You
                    can keep using the platform while an administrator checks your document.
                  </p>
                </div>
              </div>
            )}

            {status === "rejected" && (
              <div className="rounded-lg bg-rose-50 p-4 ring-1 ring-rose-200">
                <p className="text-sm font-semibold text-rose-800">
                  Your last submission was rejected
                </p>
                {latest?.review_note && (
                  <p className="mt-1 text-sm text-rose-700">
                    Reviewer&apos;s note: {latest.review_note}
                  </p>
                )}
                <p className="mt-1 text-sm text-rose-700">
                  You can upload a clearer or different document below.
                </p>
              </div>
            )}

            {status === "unverified" && (
              <p className="text-sm text-slate-600">
                Upload proof of your veterinary licence (licence card, diploma, or chamber
                registration). Only administrators can see the document.
              </p>
            )}

            {canSubmit && (
              <div>
                <Button
                  onClick={() => fileInputRef.current?.click()}
                  loading={uploading}
                  disabled={!user.license_number}
                >
                  {status === "rejected" ? "Upload a new document" : "Upload licence document"}
                </Button>
                <p className="mt-2 text-xs text-slate-500">
                  {user.license_number
                    ? "JPEG, PNG, WebP, or PDF up to 10 MB."
                    : "Add your licence number above and save your profile first."}
                </p>
              </div>
            )}

            <input
              ref={fileInputRef}
              type="file"
              accept={DOCUMENT_TYPES.join(",")}
              onChange={handleFileChange}
              className="hidden"
            />

            {history.length > 0 && (
              <div className="border-t border-slate-100 pt-4">
                <h3 className="text-xs font-medium uppercase tracking-wide text-slate-500">
                  Submission history
                </h3>
                <ul className="mt-2 space-y-2">
                  {history.map((item) => (
                    <li
                      key={item.id}
                      className="flex flex-wrap items-center justify-between gap-2 text-sm"
                    >
                      <span className="text-slate-600">
                        {formatRelativeTime(item.created_at)}
                      </span>
                      <Badge
                        variant={
                          item.status === "verified"
                            ? "success"
                            : item.status === "rejected"
                              ? "danger"
                              : "warning"
                        }
                      >
                        {item.status}
                      </Badge>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </Card>
  );
}
