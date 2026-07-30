import Badge from "./Badge";
import { ShieldCheckIcon } from "./icons";
import type { User } from "../../types";

/**
 * The single source of truth for how an author is labelled across the app.
 *
 * The teal "Verified vet" badge is reserved for veterinarians whose licence an
 * administrator approved — that distinction is the point of the verification
 * flow, so unverified veterinarians deliberately get a plain badge instead.
 */
export default function RoleBadge({
  user,
  className = "",
}: {
  user: Pick<User, "role" | "is_verified_vet">;
  className?: string;
}) {
  if (user.role === "admin") {
    return (
      <Badge variant="warning" className={className}>
        Admin
      </Badge>
    );
  }

  if (user.role === "veterinarian") {
    return user.is_verified_vet ? (
      <Badge variant="vet" className={className}>
        <ShieldCheckIcon className="h-3.5 w-3.5" />
        Verified vet
      </Badge>
    ) : (
      <Badge variant="neutral" className={className}>
        Veterinarian
      </Badge>
    );
  }

  return (
    <Badge variant="neutral" className={className}>
      Pet owner
    </Badge>
  );
}
