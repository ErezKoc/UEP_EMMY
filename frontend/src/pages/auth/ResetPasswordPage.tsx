import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, resetPassword } from "../../api/client";
import { useSession } from "../../auth/SessionContext";
import { Button, Card, Input, useToast } from "../../components/ui";

/**
 * Choose a new password, using a link from an email.
 *
 * The link is checked by spending it, not before. A "is this token still good?"
 * probe would be a second endpoint that reports whether a token exists, which is
 * the one thing a token endpoint should never be willing to say — so the page
 * shows the form, and turns the failure into a useful message if the token turns
 * out to be finished.
 *
 * On success the person is signed in, because the reset endpoint returns a
 * session. They have just proved they hold the inbox and chosen a password;
 * sending them to a login form to type it again protects nobody.
 */
export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const navigate = useNavigate();
  const { adoptSession } = useSession();
  const { toast } = useToast();

  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  // Set when the link itself is finished. Kept apart from `error` because the
  // two need different endings: a rejected password is worth retyping, and a
  // spent link is not.
  const [linkProblem, setLinkProblem] = useState<"expired" | "invalid" | null>(
    token ? null : "invalid",
  );
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (password !== confirmation) {
      setError("Those two passwords are not the same.");
      return;
    }
    if (password.length < 8) {
      setError("Pick a password of at least 8 characters.");
      return;
    }
    if (!token) {
      setLinkProblem("invalid");
      return;
    }

    setError(null);
    setSubmitting(true);
    try {
      const session = await resetPassword(token, password);
      adoptSession(session.token, session.user);
      toast("Your password has been changed.", "success");
      navigate("/dashboard", { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 410) setLinkProblem("expired");
      else if (err instanceof ApiError && err.status === 400) setLinkProblem("invalid");
      else
        setError(
          err instanceof ApiError
            ? err.message
            : "Could not change the password. Please try again.",
        );
      setSubmitting(false);
    }
  };

  if (linkProblem !== null) {
    return (
      <div className="mx-auto max-w-md">
        <Card title="This link no longer works">
          <div className="mt-5 space-y-4">
            <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900" role="alert">
              {linkProblem === "expired"
                ? "This reset link has expired or has already been used."
                : "This reset link is not valid. Check you copied the whole address from the email."}
            </p>
            <p className="text-sm text-slate-600">
              Reset links last an hour and work once. Asking for a new one takes a moment.
            </p>
            <Link to="/forgot-password">
              <Button>Send me a new link</Button>
            </Link>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md">
      <Card title="Choose a new password" description="At least 8 characters.">
        <form onSubmit={handleSubmit} className="mt-5 space-y-4" noValidate>
          <Input
            label="New password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="new-password"
            minLength={8}
            required
          />
          <Input
            label="Confirm new password"
            type="password"
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            autoComplete="new-password"
            minLength={8}
            required
          />
          {error && (
            <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
              {error}
            </p>
          )}
          <Button type="submit" loading={submitting} className="w-full">
            Change my password
          </Button>
        </form>

        <p className="mt-4 text-center text-sm text-slate-500">
          Changed your mind?{" "}
          <Link to="/login" className="font-medium text-primary-600 hover:text-primary-700">
            Sign in
          </Link>
        </p>
      </Card>
    </div>
  );
}
