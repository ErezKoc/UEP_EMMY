import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { ApiError } from "../../api/client";
import { useSession } from "../../auth/SessionContext";
import { Button, Card, Input, PawIcon, StethoscopeIcon } from "../../components/ui";
import type { SignupPayload } from "../../types";

type SignupRole = SignupPayload["role"];

const ROLE_OPTIONS: Array<{
  value: SignupRole;
  label: string;
  description: string;
  icon: typeof PawIcon;
}> = [
  {
    value: "owner",
    label: "Pet owner",
    description: "Analyze photos of your pets and ask the community.",
    icon: PawIcon,
  },
  {
    value: "veterinarian",
    label: "Veterinarian",
    description: "Share professional advice and reach pet owners.",
    icon: StethoscopeIcon,
  },
];

export default function SignupPage() {
  const { user, signup } = useSession();
  const navigate = useNavigate();

  // Admin accounts are never self-registered, so the picker is owner/vet only.
  const [role, setRole] = useState<SignupRole>("owner");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [clinicName, setClinicName] = useState("");
  const [licenseNumber, setLicenseNumber] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Navigate to="/dashboard" replace />;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await signup({
        email: email.trim(),
        password,
        display_name: displayName.trim(),
        role,
        clinic_name: role === "veterinarian" && clinicName.trim() ? clinicName.trim() : undefined,
        license_number:
          role === "veterinarian" && licenseNumber.trim() ? licenseNumber.trim() : undefined,
      });
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not create the account. Is the backend running?",
      );
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-md">
      <Card title="Create an account" description="Join UEP EMMY as a pet owner or veterinarian.">
        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          <fieldset>
            <legend className="mb-1 block text-sm font-medium text-slate-700">I am a…</legend>
            <div className="grid grid-cols-2 gap-3">
              {ROLE_OPTIONS.map((option) => {
                const selected = role === option.value;
                const Icon = option.icon;
                return (
                  <label
                    key={option.value}
                    className={`flex cursor-pointer flex-col items-center gap-1 rounded-xl border-2 p-4 text-center transition-colors ${
                      selected
                        ? "border-primary-500 bg-primary-50"
                        : "border-slate-200 bg-white hover:border-primary-300"
                    }`}
                  >
                    <input
                      type="radio"
                      name="role"
                      value={option.value}
                      checked={selected}
                      onChange={() => setRole(option.value)}
                      className="sr-only"
                    />
                    <Icon
                      className={`h-6 w-6 ${selected ? "text-primary-600" : "text-slate-400"}`}
                    />
                    <span className="text-sm font-semibold text-slate-800">{option.label}</span>
                    <span className="text-xs text-slate-500">{option.description}</span>
                  </label>
                );
              })}
            </div>
          </fieldset>

          <Input
            label="Full name"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder={role === "veterinarian" ? "Dr. Jane Doe" : "Jane Doe"}
            autoComplete="name"
            maxLength={120}
            required
          />
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
            hint="At least 8 characters."
            autoComplete="new-password"
            minLength={8}
            required
          />

          {role === "veterinarian" && (
            <>
              <Input
                label="Clinic name"
                value={clinicName}
                onChange={(event) => setClinicName(event.target.value)}
                placeholder="Riverside Veterinary Clinic"
                hint="Optional — shown on your profile."
                maxLength={255}
              />
              <Input
                label="License number"
                value={licenseNumber}
                onChange={(event) => setLicenseNumber(event.target.value)}
                placeholder="VET-2026-0000"
                hint="Optional — used later for professional verification."
                maxLength={64}
              />
            </>
          )}

          {error && (
            <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
              {error}
            </p>
          )}

          <Button type="submit" loading={submitting} className="w-full">
            Create account
          </Button>
        </form>

        <p className="mt-4 text-center text-sm text-slate-500">
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-primary-600 hover:text-primary-700">
            Sign in
          </Link>
        </p>
      </Card>
    </div>
  );
}
