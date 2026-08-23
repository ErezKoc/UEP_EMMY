import { useRef, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { ApiError, updateProfile, uploadAvatar } from "../../api/client";
import { useSession } from "../../auth/SessionContext";
import { Avatar, Button, Card, CameraIcon, Input, RoleBadge, Textarea, useToast } from "../../components/ui";
import type { CurrentUser } from "../../types";
import VerificationCard from "./VerificationCard";

const AVATAR_TYPES = ["image/jpeg", "image/png", "image/webp"];

export default function ProfilePage() {
  const { user } = useSession();
  // RequireAuth guarantees a user; the split keeps hooks unconditional and
  // lets the form initialize its state directly from the loaded user.
  if (!user) return null;
  return <ProfileContent user={user} />;
}

function ProfileContent({ user }: { user: CurrentUser }) {
  const { setUser } = useSession();
  const { toast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [displayName, setDisplayName] = useState(user.display_name);
  const [bio, setBio] = useState(user.bio ?? "");
  const [clinicName, setClinicName] = useState(user.clinic_name ?? "");
  const [licenseNumber, setLicenseNumber] = useState(user.license_number ?? "");
  // The practice's public details. One state entry each rather than an object,
  // to match the two fields above and keep the form uncontroversial.
  const [clinicPhone, setClinicPhone] = useState(user.clinic_phone ?? "");
  const [clinicEmergencyPhone, setClinicEmergencyPhone] = useState(
    user.clinic_emergency_phone ?? "",
  );
  const [clinicEmail, setClinicEmail] = useState(user.clinic_email ?? "");
  const [clinicWebsite, setClinicWebsite] = useState(user.clinic_website ?? "");
  const [clinicAddressLine, setClinicAddressLine] = useState(user.clinic_address_line ?? "");
  const [clinicCity, setClinicCity] = useState(user.clinic_city ?? "");
  const [clinicPostcode, setClinicPostcode] = useState(user.clinic_postcode ?? "");
  const [clinicCountry, setClinicCountry] = useState(user.clinic_country ?? "");
  const [clinicHours, setClinicHours] = useState(user.clinic_hours ?? "");
  const [acceptsAppointments, setAcceptsAppointments] = useState(
    user.accepts_appointments ?? false,
  );
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);

  const isVet = user.role === "veterinarian";

  const handleAvatarChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!AVATAR_TYPES.includes(file.type)) {
      toast("Please choose a JPEG, PNG, or WebP image.", "error");
      return;
    }
    setUploadingAvatar(true);
    try {
      setUser(await uploadAvatar(file));
      toast("Profile photo updated.", "success");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not upload the photo.", "error");
    } finally {
      setUploadingAvatar(false);
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const updated = await updateProfile({
        display_name: displayName.trim(),
        bio: bio.trim(),
        ...(isVet
          ? {
              clinic_name: clinicName.trim(),
              license_number: licenseNumber.trim(),
              clinic_phone: clinicPhone.trim(),
              clinic_emergency_phone: clinicEmergencyPhone.trim(),
              clinic_email: clinicEmail.trim(),
              clinic_website: clinicWebsite.trim(),
              clinic_address_line: clinicAddressLine.trim(),
              clinic_city: clinicCity.trim(),
              clinic_postcode: clinicPostcode.trim(),
              clinic_country: clinicCountry.trim(),
              clinic_hours: clinicHours.trim(),
              accepts_appointments: acceptsAppointments,
            }
          : {}),
      });
      setUser(updated);
      toast("Profile saved.", "success");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the profile.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Card>
        <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
          <div className="relative">
            <Avatar name={user.display_name} src={user.avatar_url} size="lg" />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadingAvatar}
              aria-label="Change profile photo"
              className="absolute -bottom-1 -right-1 rounded-full bg-primary-600 p-1.5 text-white shadow hover:bg-primary-700 disabled:bg-primary-300"
            >
              <CameraIcon className="h-3.5 w-3.5" />
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept={AVATAR_TYPES.join(",")}
              onChange={handleAvatarChange}
              className="hidden"
            />
          </div>

          <div className="text-center sm:text-left">
            <div className="flex flex-wrap items-center justify-center gap-2 sm:justify-start">
              <h1 className="text-xl font-bold text-slate-800">{user.display_name}</h1>
              <RoleBadge user={user} />
            </div>
            <p className="mt-1 text-sm text-slate-500">{user.email}</p>
            {isVet && user.clinic_name && (
              <p className="mt-1 text-sm text-slate-600">{user.clinic_name}</p>
            )}
            {user.bio && <p className="mt-3 max-w-md text-sm text-slate-600">{user.bio}</p>}
          </div>
        </div>
      </Card>

      <Card title="Edit profile" description="This is how the community sees you.">
        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          <Input
            label="Display name"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            maxLength={120}
            required
          />
          <Textarea
            label="Bio"
            value={bio}
            onChange={(event) => setBio(event.target.value)}
            placeholder={
              isVet
                ? "Your specialty, experience, and how you help pet owners."
                : "Tell the community about you and your pets."
            }
            maxLength={1000}
          />

          {isVet && (
            <>
              <Input
                label="Clinic name"
                value={clinicName}
                onChange={(event) => setClinicName(event.target.value)}
                maxLength={255}
              />
              <Input
                label="License number"
                value={licenseNumber}
                onChange={(event) => setLicenseNumber(event.target.value)}
                hint="Required to request professional verification."
                maxLength={64}
              />

              {/*
                Everything below is published in the directory. Said once, here,
                rather than repeated as a hint on nine fields — and said before
                them rather than after, so nobody types an address they did not
                mean to publish and finds out underneath the box.
              */}
              <div className="border-t border-slate-100 pt-4">
                <h3 className="text-sm font-semibold text-slate-800">Practice details</h3>
                <p className="mt-1 text-sm text-slate-500">
                  Shown publicly on the Vets page so owners can reach you. Leave anything blank
                  that you would rather not publish. Your sign-in email is never shown.
                </p>
              </div>

              <Input
                label="Phone"
                value={clinicPhone}
                onChange={(event) => setClinicPhone(event.target.value)}
                maxLength={40}
              />
              <Input
                label="Out-of-hours phone"
                value={clinicEmergencyPhone}
                onChange={(event) => setClinicEmergencyPhone(event.target.value)}
                hint="Shown first and marked urgent. Leave blank if you have no out-of-hours line."
                maxLength={40}
              />
              <Input
                label="Public email"
                type="email"
                value={clinicEmail}
                onChange={(event) => setClinicEmail(event.target.value)}
                maxLength={255}
              />
              <Input
                label="Website"
                value={clinicWebsite}
                onChange={(event) => setClinicWebsite(event.target.value)}
                placeholder="https://"
                maxLength={1024}
              />
              <Input
                label="Street address"
                value={clinicAddressLine}
                onChange={(event) => setClinicAddressLine(event.target.value)}
                maxLength={255}
              />
              <div className="grid gap-4 sm:grid-cols-3">
                <Input
                  label="City"
                  value={clinicCity}
                  onChange={(event) => setClinicCity(event.target.value)}
                  maxLength={120}
                />
                <Input
                  label="Postcode"
                  value={clinicPostcode}
                  onChange={(event) => setClinicPostcode(event.target.value)}
                  maxLength={20}
                />
                <Input
                  label="Country"
                  value={clinicCountry}
                  onChange={(event) => setClinicCountry(event.target.value)}
                  maxLength={120}
                />
              </div>
              <Textarea
                label="Opening hours"
                value={clinicHours}
                onChange={(event) => setClinicHours(event.target.value)}
                placeholder="Mon-Fri 08:00-18:00, Sat 09:00-13:00. Closed Sundays."
                hint="Free text, so split hours and seasonal closures can be written as they are."
                rows={2}
                maxLength={500}
              />

              <label className="flex items-start gap-3 rounded-lg bg-slate-50 px-3 py-3 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={acceptsAppointments}
                  onChange={(event) => setAcceptsAppointments(event.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
                />
                <span>
                  <span className="font-medium">Take appointment requests here.</span>{" "}
                  Owners can send you a request with a reason and a preferred day; you confirm,
                  offer another day, or decline. Leave this off and owners will only see your
                  contact details — a request nobody is watching for is worse than no button.
                </span>
              </label>
            </>
          )}

          {error && (
            <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
              {error}
            </p>
          )}

          <div className="flex justify-end">
            <Button type="submit" loading={saving}>
              Save changes
            </Button>
          </div>
        </form>
      </Card>

      {isVet && <VerificationCard user={user} />}
    </div>
  );
}
