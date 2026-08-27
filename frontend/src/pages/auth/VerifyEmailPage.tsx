import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError, fetchCurrentUser, verifyEmail } from "../../api/client";
import { useSession } from "../../auth/SessionContext";
import { Button, Card, Spinner } from "../../components/ui";
import type { EmailVerificationResult } from "../../types";

/**
 * Where a verification link lands.
 *
 * Five states, because collapsing them loses the only thing the reader needs:
 * what to do next. "Expired" and "already used" both send somebody to the
 * resend page; "not a valid link" sends them back to the email to check they
 * copied the whole address; a failure to reach the server is worth retrying and
 * the other three are not.
 *
 * Spends the token on mount without asking. The click already was the consent —
 * a "confirm your confirmation" button would only add a step, and mail clients
 * that pre-fetch links are the reason tokens are one-use rather than the reason
 * to make people click twice.
 */
type State =
  | { kind: "working" }
  | { kind: "done"; result: EmailVerificationResult }
  | { kind: "expired"; message: string }
  | { kind: "invalid"; message: string }
  | { kind: "failed"; message: string };

export default function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const { user, setUser } = useSession();
  const [state, setState] = useState<State>({ kind: "working" });
  // React 18 mounts effects twice in development StrictMode. Without this the
  // page spends the token, then spends it again, and shows "already used" for
  // a link that had just worked.
  const attempted = useRef(false);

  useEffect(() => {
    if (attempted.current) return;
    attempted.current = true;

    if (!token) {
      setState({
        kind: "invalid",
        message: "This address has no confirmation code in it.",
      });
      return;
    }

    verifyEmail(token)
      .then(async (result) => {
        setState({ kind: "done", result });
        // The signed-in session is now stale: the account may have a new
        // address on it, and it certainly has a verification timestamp.
        // Refreshed only when there IS a session — this page is reached
        // signed out at least as often as signed in.
        if (user) {
          try {
            setUser(await fetchCurrentUser());
          } catch {
            /* The confirmation stands whether or not the refresh worked. */
          }
        }
      })
      .catch((error) => {
        if (!(error instanceof ApiError)) {
          setState({ kind: "failed", message: "Something went wrong. Please try again." });
          return;
        }
        // 410 is a link that was real and is finished; 400 is one that never
        // was. The backend draws that line so this page can act on it.
        if (error.status === 410) setState({ kind: "expired", message: error.message });
        else if (error.status === 400) setState({ kind: "invalid", message: error.message });
        else setState({ kind: "failed", message: error.message });
      });
    // Runs once, deliberately: re-running on a session change would spend a
    // second token.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  return (
    <div className="mx-auto max-w-md">
      <Card title="Confirming your email address">
        <div className="mt-5 space-y-4">
          {state.kind === "working" && (
            <div
              className="flex items-center gap-3 text-sm text-slate-600"
              role="status"
              aria-live="polite"
            >
              <Spinner />
              <span>Checking your link…</span>
            </div>
          )}

          {state.kind === "done" && (
            <>
              <p
                className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800"
                role="status"
              >
                {state.result.detail}
              </p>
              <p className="text-sm text-slate-600">
                {state.result.email_changed ? (
                  <>
                    You now sign in with{" "}
                    <span className="font-medium">{state.result.email}</span>.
                  </>
                ) : (
                  <>
                    <span className="font-medium">{state.result.email}</span> is confirmed.
                  </>
                )}
              </p>
              <div className="flex flex-wrap gap-2">
                <Link to={user ? "/dashboard" : "/login"}>
                  <Button>{user ? "Go to your dashboard" : "Sign in"}</Button>
                </Link>
              </div>
            </>
          )}

          {state.kind === "expired" && (
            <>
              <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900" role="alert">
                {state.message}
              </p>
              <p className="text-sm text-slate-600">
                Links stop working after a while, and each one can only be used once. Ask for
                a fresh one and we will send another.
              </p>
              <Link to="/resend-verification">
                <Button>Send me a new link</Button>
              </Link>
            </>
          )}

          {state.kind === "invalid" && (
            <>
              <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
                {state.message}
              </p>
              <p className="text-sm text-slate-600">
                Some mail clients split long links across two lines. Copying the whole address
                from the email usually fixes it — or ask for a new one.
              </p>
              <Link to="/resend-verification">
                <Button variant="secondary">Send me a new link</Button>
              </Link>
            </>
          )}

          {state.kind === "failed" && (
            <>
              <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
                {state.message}
              </p>
              <Button
                onClick={() => {
                  attempted.current = false;
                  setState({ kind: "working" });
                  // Re-runs the effect by remounting the guard above.
                  window.location.reload();
                }}
              >
                Try again
              </Button>
            </>
          )}
        </div>
      </Card>
    </div>
  );
}
