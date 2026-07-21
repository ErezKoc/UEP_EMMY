import { useState } from "react";
import type { FormEvent } from "react";
import { ApiError, changePassword, updateProfile } from "../../api/client";
import { useSession } from "../../auth/SessionContext";
import { Button, Card, Input, useToast } from "../../components/ui";
import type { User } from "../../types";

export default function SettingsPage() {
  const { user } = useSession();
  // RequireAuth guarantees a user; split keeps hooks unconditional.
  if (!user) return null;
  return <SettingsContent user={user} />;
}

function SettingsContent({ user }: { user: User }) {
  const { setUser } = useSession();
  const { toast } = useToast();

  const [email, setEmail] = useState(user.email);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [savingEmail, setSavingEmail] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [savingPassword, setSavingPassword] = useState(false);

  const handleEmailSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setEmailError(null);
    setSavingEmail(true);
    try {
      setUser(await updateProfile({ email: email.trim() }));
      toast("Email updated.", "success");
    } catch (err) {
      setEmailError(err instanceof ApiError ? err.message : "Could not update the email.");
    } finally {
      setSavingEmail(false);
    }
  };

  const handlePasswordSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (newPassword !== confirmPassword) {
      setPasswordError("New passwords do not match.");
      return;
    }
    setPasswordError(null);
    setSavingPassword(true);
    try {
      await changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      toast("Password changed.", "success");
    } catch (err) {
      setPasswordError(err instanceof ApiError ? err.message : "Could not change the password.");
    } finally {
      setSavingPassword(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold text-slate-800">Settings</h1>

      <Card title="Email address" description="Used to sign in to your account.">
        <form onSubmit={handleEmailSubmit} className="mt-5 space-y-4">
          <Input
            label="Email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
            required
          />
          {emailError && (
            <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
              {emailError}
            </p>
          )}
          <div className="flex justify-end">
            <Button type="submit" loading={savingEmail} disabled={email.trim() === user.email}>
              Update email
            </Button>
          </div>
        </form>
      </Card>

      <Card title="Change password" description="Pick a new password of at least 8 characters.">
        <form onSubmit={handlePasswordSubmit} className="mt-5 space-y-4">
          <Input
            label="Current password"
            type="password"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
            autoComplete="current-password"
            required
          />
          <Input
            label="New password"
            type="password"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            autoComplete="new-password"
            minLength={8}
            required
          />
          <Input
            label="Confirm new password"
            type="password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            autoComplete="new-password"
            minLength={8}
            required
          />
          {passwordError && (
            <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
              {passwordError}
            </p>
          )}
          <div className="flex justify-end">
            <Button type="submit" loading={savingPassword}>
              Change password
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
