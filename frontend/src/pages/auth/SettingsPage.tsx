import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError, changePassword, resendVerification, updateProfile } from "../../api/client";
import { useSession } from "../../auth/SessionContext";
import { useEmailDelivery } from "../../components/EmailDeliveryNotice";
import { Button, Card, Input, useToast } from "../../components/ui";
import type { CurrentUser } from "../../types";

export default function SettingsPage() {
  const { user } = useSession();
  // RequireAuth guarantees a user; split keeps hooks unconditional.
  if (!user) return null;
  return <SettingsContent user={user} />;
}

/** The lead times the checkboxes offer. Anything else is left to the API. */
const LEAD_CHOICES: Array<{ days: number; label: string }> = [
  { days: 14, label: "Two weeks before" },
  { days: 7, label: "A week before" },
  { days: 3, label: "Three days before" },
  { days: 1, label: "The day before" },
  { days: 0, label: "On the day" },
];

// `CurrentUser`, not `User`: the notification preferences below live on the
// signed-in account rather than on a public profile, and `useSession` already
// hands us the fuller type.
function SettingsContent({ user }: { user: CurrentUser }) {
  const { setUser } = useSession();
  const { toast } = useToast();
  /*
   * What this deployment can actually do, asked rather than assumed.
   *
   * The page used to state, unconditionally, that email "is only delivered when
   * this deployment has a mail server configured" - true, and useless, because
   * it left every reader to work out for themselves which case they were in.
   * Null while it loads; the card below says nothing rather than guessing.
   */
  const delivery = useEmailDelivery();

  const [email, setEmail] = useState(user.email);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [emailNotice, setEmailNotice] = useState<string | null>(null);
  const [savingEmail, setSavingEmail] = useState(false);
  const [resending, setResending] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [savingPassword, setSavingPassword] = useState(false);

  const handleEmailSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setEmailError(null);
    setEmailNotice(null);
    setSavingEmail(true);
    const wanted = email.trim();
    try {
      const updated = await updateProfile({ email: wanted });
      setUser(updated);
      /*
       * The address has NOT changed yet, and the message has to say so.
       *
       * It changes when the link we just sent to the new address is clicked.
       * A toast reading "Email updated." would be a straightforward lie, and
       * the person would then wonder why signing in with the new address does
       * not work.
       */
      if (updated.pending_email) {
        setEmailNotice(
          `We have sent a confirmation link to ${updated.pending_email}. Your address stays ` +
            `${updated.email} until you open it.`,
        );
      } else {
        toast("Pending email change cancelled.", "success");
      }
    } catch (err) {
      setEmailError(err instanceof ApiError ? err.message : "Could not update the email.");
    } finally {
      setSavingEmail(false);
    }
  };

  const handleResend = async () => {
    setResending(true);
    try {
      const response = await resendVerification(user.email);
      setEmailNotice(response.detail);
    } catch (err) {
      setEmailError(
        err instanceof ApiError ? err.message : "Could not send that. Try again shortly.",
      );
    } finally {
      setResending(false);
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
   * Several lead times, not one.
   *
   * A booster is worth a week's warning because it needs an appointment AND a
   * nudge the night before; one number can only ever be one of those. An empty
   * list means "just the single value above", which is what every account meant
   * before this existed — so nobody's alerts changed when it arrived.
   */
  const [leads, setLeads] = useState<number[]>(user.notify_leads ?? []);
  // "09:00:00" from the server; an <input type="time"> wants "09:00".
  const [notifyTime, setNotifyTime] = useState((user.notify_time ?? "09:00:00").slice(0, 5));
  /*
   * The browser knows its own zone; the server cannot guess it.
   *
   * Without one, "09:00" is read in UTC, which is the middle of the night for
   * a good half of the people using this. Offered as a one-click fix rather
   * than a dropdown of six hundred zone names, and the current state is said
   * out loud so nobody believes a preference was honoured that never was.
   */
  const browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  /*
   * Saved on change rather than behind a Save button. Every control here is a
   * single independent preference, and the person reaching this page is
   * usually here to turn something off - which should take one click, not two.
   */
  const saveNotifications = async (changes: {
    notify_in_app?: boolean;
    notify_email?: boolean;
    notify_lead_days?: number;
    notify_leads?: number[] | null;
    notify_time?: string;
    notify_timezone?: string | null;
  }) => {
    if (changes.notify_in_app !== undefined) setNotifyInApp(changes.notify_in_app);
    if (changes.notify_email !== undefined) setNotifyEmail(changes.notify_email);
    if (changes.notify_leads !== undefined) setLeads(changes.notify_leads ?? []);
    try {
      setUser(await updateProfile(changes));
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not save that.", "error");
      // Put the switch back where it was, so the interface never claims a
      // preference the server did not accept.
      setNotifyInApp(user.notify_in_app ?? true);
      setNotifyEmail(user.notify_email ?? true);
      setLeadDays(user.notify_lead_days ?? 1);
      setLeads(user.notify_leads ?? []);
      setNotifyTime((user.notify_time ?? "09:00:00").slice(0, 5));
    }
  };

  const toggleLead = (days: number, on: boolean) => {
    const next = on ? [...leads, days] : leads.filter((day) => day !== days);
    void saveNotifications({ notify_leads: next.length > 0 ? next : null });
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold text-slate-800">Settings</h1>

      <Card title="Email address" description="Used to sign in to your account.">
        <div className="mt-4 space-y-3">
          {user.pending_email && (
            <p
              className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900"
              role="status"
            >
              <span className="font-medium">Waiting for confirmation.</span> We sent a link to{" "}
              <span className="font-medium">{user.pending_email}</span>. You keep signing in
              with {user.email} until that link is opened. Entering your current address here
              again cancels the change.
            </p>
          )}

          {!user.email_verified_at && !user.pending_email && (
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
              {/*
                Reachable only by an account confirmed before the sign-in rule
                existed and since changed — signing in requires a confirmed
                address, so nobody arrives here by the ordinary route. It used
                to say "nothing is blocked", which is no longer true.
              */}
              <p>
                <span className="font-medium">This address is not confirmed.</span> Confirm it to
                keep signing in — it is also how a password reset would reach you.
              </p>
              <Button
                variant="secondary"
                size="sm"
                className="mt-2"
                loading={resending}
                onClick={() => void handleResend()}
              >
                Send me the confirmation link
              </Button>
            </div>
          )}

          {user.email_verified_at && !user.pending_email && (
            <p className="text-sm text-emerald-700">This address is confirmed.</p>
          )}
        </div>

        <form onSubmit={handleEmailSubmit} className="mt-4 space-y-4">
          <Input
            label="Email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
            hint="Changing this sends a confirmation link to the new address. Your current address keeps working until you open it."
            required
          />
          {emailNotice && (
            <p
              className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800"
              role="status"
            >
              {emailNotice}
            </p>
          )}
          {emailError && (
            <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
              {emailError}
            </p>
          )}
          <div className="flex justify-end">
            <Button
              type="submit"
              loading={savingEmail}
              disabled={email.trim() === user.email && !user.pending_email}
            >
              {email.trim() === user.email ? "Cancel the change" : "Send confirmation link"}
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
              never twice for the same one. Any single reminder can override this on the
              calendar page — a booster is worth a week&apos;s warning, tonight&apos;s tablet is
              not.
            </p>
          </div>

          <fieldset>
            <legend className="text-sm font-medium text-slate-700">
              Or remind me more than once
            </legend>
            <p className="mt-1 text-xs text-slate-500">
              Tick as many as you like and each gets its own alert. Leave them all unticked to
              use the single setting above.
            </p>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {LEAD_CHOICES.map((choice) => (
                <label
                  key={choice.days}
                  className="flex items-center gap-2 text-sm text-slate-700"
                >
                  <input
                    type="checkbox"
                    checked={leads.includes(choice.days)}
                    onChange={(event) => toggleLead(choice.days, event.target.checked)}
                    className="h-4 w-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
                  />
                  {choice.label}
                </label>
              ))}
            </div>
          </fieldset>

          <div>
            <label htmlFor="notify-time" className="block text-sm font-medium text-slate-700">
              Send them at
            </label>
            <input
              id="notify-time"
              type="time"
              value={notifyTime}
              onChange={(event) => setNotifyTime(event.target.value)}
              onBlur={() =>
                void saveNotifications({ notify_time: `${notifyTime}:00` })
              }
              className="mt-1 w-32 rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
            <p className="mt-1 text-xs text-slate-500">
              {user.notify_timezone ? (
                <>
                  Read in <span className="font-medium">{user.notify_timezone}</span>.
                </>
              ) : (
                <>
                  Read in <span className="font-medium">UTC</span>, because you have not told us
                  where you are — so this may not be the hour you meant.
                </>
              )}
            </p>
            {user.notify_timezone !== browserZone && (
              <button
                type="button"
                onClick={() => void saveNotifications({ notify_timezone: browserZone })}
                className="mt-2 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700"
              >
                Use this device&apos;s timezone ({browserZone})
              </button>
            )}
          </div>

          {/*
            Shown ONLY when email cannot be delivered.

            Working email is the state people expect, so announcing it is noise
            on a page somebody opened to change something else - and the version
            of this that named the sending address published a deployment detail
            to every reader for no benefit they could act on.

            Nothing is rendered while the answer is still loading either: a guess
            here is worse than a short gap.
          */}
          {delivery !== null && !delivery.available && (
            <p
              role="status"
              className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-900"
            >
              <span className="font-semibold">This server cannot send email.</span> No mail
              server is set up here, so messages are written to the server&apos;s outbox as
              files instead of being delivered. Alerts still appear in the app, and each one
              says that email was unavailable rather than claiming it was sent.
            </p>
          )}

          {!notifyEmail && (
            <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">
              Email is switched off, so alerts appear in the app only. Confirmation and
              password-reset messages are still sent — those are how you get back into your
              account, so they are not something a preference can turn off.
            </p>
          )}
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
        <p className="mt-4 text-sm text-slate-500">
          Cannot remember it?{" "}
          <Link
            to="/forgot-password"
            className="font-medium text-primary-600 hover:text-primary-700"
          >
            Get a reset link by email
          </Link>
          .
        </p>
      </Card>
    </div>
  );
}
