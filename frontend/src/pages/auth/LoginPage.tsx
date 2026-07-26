import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../../api/client";
import { useSession } from "../../auth/SessionContext";
import { Button, Card, Input } from "../../components/ui";

export default function LoginPage() {
  const { user, login } = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  // Where RequireAuth sent us from, so we can return there after signing in.
  const from = (location.state as { from?: string } | null)?.from ?? "/dashboard";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Also covers the just-logged-in re-render: the session user appears before
  // handleSubmit's navigate runs, and this redirect must honor `from` too.
  if (user) return <Navigate to={from} replace />;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not sign in. Is the backend running?");
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

          <Button type="submit" loading={submitting} className="w-full">
            Sign in
          </Button>
        </form>

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
