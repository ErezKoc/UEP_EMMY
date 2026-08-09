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
          ? { clinic_name: clinicName.trim(), license_number: licenseNumber.trim() }
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
