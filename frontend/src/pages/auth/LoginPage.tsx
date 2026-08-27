import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { ApiError, EMAIL_UNVERIFIED } from "../../api/client";
import { useSession } from "../../auth/SessionContext";
import { Button, Card, Input } from "../../components/ui";

export default function LoginPage() {
  const { user, login } = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  // Where RequireAuth sent us from, so we can return there after signing in —
  // and the state that route was carrying, which has to be handed back with it
  // or a link that prefills its destination arrives empty.
  const sentFrom = location.state as { from?: string; fromState?: unknown } | null;
  const from = sentFrom?.from ?? "/dashboard";
  const fromState = sentFrom?.fromState ?? null;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  /*
   * Kept apart from `error`, because it is the one refusal with something to do
   * about it.
   *
   * `/login` answers 403 for a ban and for an unconfirmed address, and the two
   * need opposite endings: a ban is final, an unconfirmed address is one click
   * from being fixed. The server sends a code so this does not have to match on
   * the wording.
   */
  const [needsVerification, setNeedsVerification] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Also covers the just-logged-in re-render: the session user appears before
  // handleSubmit's navigate runs, and this redirect must honor `from` too.
  if (user) return <Navigate to={from} replace state={fromState} />;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setNeedsVerification(null);
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      navigate(from, { replace: true, state: fromState });
    } catch (err) {
      if (err instanceof ApiError && err.code === EMAIL_UNVERIFIED) {
        setNeedsVerification(err.message);
      } else {
        setError(
          err instanceof ApiError ? err.message : "Could not sign in. Is the backend running?",
        );
      }
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-md">
      <Card title="Sign in" description="Welcome back to UEP EMMY.">
        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          <Input
            label="Email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
            autoComplete="email"
            required
          />
          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Your password"
            autoComplete="current-password"
            required
          />

          {error && (
            <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
              {error}
            </p>
          )}

          {needsVerification && (
            <div
              className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-3 text-sm text-amber-900"
              role="alert"
            >
              <p className="font-medium">Confirm your email address first</p>
              <p className="mt-1 leading-relaxed">{needsVerification}</p>
              <Link
                to="/resend-verification"
                className="mt-2 inline-block font-medium text-amber-900 underline"
              >
                Send the confirmation link again
              </Link>
            </div>
          )}

          <Button type="submit" loading={submitting} className="w-full">
            Sign in
          </Button>
        </form>

        <p className="mt-4 text-center text-sm">
          <Link
            to="/forgot-password"
            className="font-medium text-primary-600 hover:text-primary-700"
          >
            Forgot your password?
          </Link>
        </p>

        <p className="mt-4 text-center text-sm text-slate-500">
          No account yet?{" "}
          <Link to="/signup" className="font-medium text-primary-600 hover:text-primary-700">
            Create one
          </Link>
        </p>
      </Card>
    </div>
  );
}
