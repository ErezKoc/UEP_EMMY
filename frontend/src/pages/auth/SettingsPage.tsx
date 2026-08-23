import { useState } from "react";
import type { FormEvent } from "react";
import { ApiError, changePassword, updateProfile } from "../../api/client";
import { useSession } from "../../auth/SessionContext";
import { Button, Card, Input, useToast } from "../../components/ui";
import type { CurrentUser } from "../../types";

export default function SettingsPage() {
  const { user } = useSession();
  // RequireAuth guarantees a user; split keeps hooks unconditional.
  if (!user) return null;
  return <SettingsContent user={user} />;
}

// `CurrentUser`, not `User`: the notification preferences below live on the
// signed-in account rather than on a public profile, and `useSession` already
// hands us the fuller type.
function SettingsContent({ user }: { user: CurrentUser }) {
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

  const [notifyInApp, setNotifyInApp] = useState(user.notify_in_app ?? true);
  const [notifyEmail, setNotifyEmail] = useState(user.notify_email ?? true);
  const [leadDays, setLeadDays] = useState(user.notify_lead_days ?? 1);

  /*
   * Saved on change rather than behind a Save button. Every control here is a
   * single independent preference, and the person reaching this page is
   * usually here to turn something off - which should take one click, not two.
   */
  const saveNotifications = async (changes: {
    notify_in_app?: boolean;
    notify_email?: boolean;
    notify_lead_days?: number;
  }) => {
    if (changes.notify_in_app !== undefined) setNotifyInApp(changes.notify_in_app);
    if (changes.notify_email !== undefined) setNotifyEmail(changes.notify_email);
    try {
      setUser(await updateProfile(changes));
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not save that.", "error");
      // Put the switch back where it was, so the interface never claims a
      // preference the server did not accept.
      setNotifyInApp(user.notify_in_app ?? true);
      setNotifyEmail(user.notify_email ?? true);
      setLeadDays(user.notify_lead_days ?? 1);
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

      <Card
        title="Notifications"
        description="How you hear about reminders coming due and changes to your appointments."
      >
        <div className="mt-5 space-y-4">
          <label className="flex items-start gap-3 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={notifyInApp}
              onChange={(event) => void saveNotifications({ notify_in_app: event.target.checked })}
              className="mt-0.5 h-4 w-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
            />
            <span>
              <span className="font-medium">In the app.</span> The bell in the header, with a
              count of anything you have not read.
            </span>
          </label>

          <label className="flex items-start gap-3 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={notifyEmail}
              onChange={(event) => void saveNotifications({ notify_email: event.target.checked })}
              className="mt-0.5 h-4 w-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
            />
            <span>
              <span className="font-medium">By email.</span> Sent to the address above.
            </span>
          </label>

          <div>
            <label
              htmlFor="lead-days"
              className="block text-sm font-medium text-slate-700"
            >
              Tell me this many days before a reminder is due
            </label>
            <input
              id="lead-days"
              type="number"
              min={0}
              max={30}
              value={leadDays}
              onChange={(event) => setLeadDays(Math.min(30, Math.max(0, Number(event.target.value) || 0)))}
              onBlur={() => void saveNotifications({ notify_lead_days: leadDays })}
              className="mt-1 w-24 rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
            <p className="mt-1 text-xs text-slate-500">
              0 means on the day itself. Repeating reminders are announced once per occurrence,
              never twice for the same one.
            </p>
          </div>

          {/*
            Said plainly rather than left for somebody to discover by not
            receiving anything. Email only leaves this machine when SMTP is
            configured; otherwise the message is written to an outbox file and
            the notification is marked "not emailed" in the bell.
          */}
          <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">
            Email is only delivered when this deployment has a mail server configured. Without one,
            messages are written to the server&apos;s outbox instead and the alert is marked
            &ldquo;not emailed&rdquo;.
          </p>
        </div>
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
