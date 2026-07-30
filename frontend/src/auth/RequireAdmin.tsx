import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { Spinner } from "../components/ui";
import { useSession } from "./SessionContext";

/**
 * Admin-only route guard. Signed-out visitors go to /login; signed-in
 * non-admins are sent home rather than shown an admin screen they cannot use.
 * (The backend enforces this too — this is only for the UI.)
 */
export default function RequireAdmin({ children }: { children: ReactNode }) {
  const { user, initializing } = useSession();

  if (initializing) {
    return (
      <div className="flex justify-center py-16">
        <Spinner />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace state={{ from: "/admin/verifications" }} />;
  if (user.role !== "admin") return <Navigate to="/" replace />;
  return <>{children}</>;
}
