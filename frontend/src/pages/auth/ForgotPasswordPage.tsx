import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError, requestPasswordReset } from "../../api/client";
import EmailDeliveryNotice from "../../components/EmailDeliveryNotice";
import { Button, Card, Input } from "../../components/ui";

/**
 * Ask for a password-reset link.
 *
 * Same shape as the resend page and for the same reason: the answer must not
 * differ between an address that has an account and one that does not. It is
 * the one screen where saying less is the security property.
 *
 * A 429 is shown as itself rather than folded into the success message. Being
 * told "we sent it" three times while a rate limit quietly drops the request is
 * how somebody ends up waiting an hour for an email nobody sent.
 */
export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const response = await requestPasswordReset(email.trim());
      setSent(response.detail);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not send that. Please try again in a moment.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-md">
      <Card
        title="Forgot your password?"
        description="Give us the address on your account and we will send you a link to choose a new password."
      >
        {sent ? (
          <div className="mt-5 space-y-4">
            <p
              className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800"
              role="status"
            >
              {sent}
            </p>
            <p className="text-sm text-slate-600">
              The link expires in an hour and can only be used once. Asking again sends a new
              one and stops the old one working.
            </p>
            <EmailDeliveryNotice what="password reset emails" />
            <div className="flex flex-wrap gap-2">
              <Link to="/login">
                <Button variant="secondary">Back to sign in</Button>
              </Link>
              <Button variant="ghost" onClick={() => setSent(null)}>
                Use a different address
              </Button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="mt-5 space-y-4" noValidate>
            <Input
              label="Email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              required
            />
            {error && (
              <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
                {error}
              </p>
            )}
            <EmailDeliveryNotice what="password reset emails" />
            <Button type="submit" loading={submitting} className="w-full">
              Send me a reset link
            </Button>
          </form>
        )}

        <p className="mt-4 text-center text-sm text-slate-500">
          Remembered it?{" "}
          <Link to="/login" className="font-medium text-primary-600 hover:text-primary-700">
            Sign in
          </Link>
        </p>
      </Card>
    </div>
  );
}
