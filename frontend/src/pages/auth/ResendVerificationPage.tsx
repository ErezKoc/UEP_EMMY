import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError, resendVerification } from "../../api/client";
import EmailDeliveryNotice from "../../components/EmailDeliveryNotice";
import { Button, Card, Input } from "../../components/ui";

/**
 * "Send me the confirmation email again."
 *
 * Signed out on purpose: the person who cannot prove their address is
 * frequently the person who cannot get past a sign-in form either.
 *
 * The success message says "if that address has an account" rather than "sent".
 * That is not vagueness for its own sake — the backend answers identically for
 * a registered and an unregistered address so this endpoint cannot be used to
 * test whether somebody has an account here, and an interface that said "sent!"
 * for one and something else for the other would give away exactly what the API
 * refuses to.
 */
export default function ResendVerificationPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const response = await resendVerification(email.trim());
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
        title="Resend the confirmation email"
        description="We will send a fresh link to your address. The previous one stops working."
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
              The link is good for two days and can be used once.
            </p>
            <EmailDeliveryNotice what="confirmation emails" />
            <Link to="/login">
              <Button variant="secondary">Back to sign in</Button>
            </Link>
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
            <EmailDeliveryNotice what="confirmation emails" />
            <Button type="submit" loading={submitting} className="w-full">
              Send the link
            </Button>
          </form>
        )}

        <p className="mt-4 text-center text-sm text-slate-500">
          Remembered where you were?{" "}
          <Link to="/login" className="font-medium text-primary-600 hover:text-primary-700">
            Sign in
          </Link>
        </p>
      </Card>
    </div>
  );
}
