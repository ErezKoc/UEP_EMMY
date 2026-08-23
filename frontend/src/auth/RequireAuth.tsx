import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { Spinner } from "../components/ui";
import { useSession } from "./SessionContext";

/**
 * Route guard: renders children only for signed-in users, otherwise redirects
 * to /login (remembering where the user wanted to go, so LoginPage can send
 * them back after signing in).
 *
 * Usage in App.tsx: <Route path="/profile" element={<RequireAuth><ProfilePage /></RequireAuth>} />
 */
export default function RequireAuth({ children }: { children: ReactNode }) {
  const { user, initializing } = useSession();
  const location = useLocation();

  if (initializing) {
    return (
      <div className="flex justify-center py-16">
        <Spinner />
      </div>
    );
  }
  if (!user) {
    return (
      <Navigate
        to="/login"
        replace
        // `fromState` carries whatever the link that aimed here was passing —
        // a prefilled community post, for one — so signing in resumes what the
        // owner was doing instead of dropping them on an empty form. Forwarded
        // as an opaque value: this component knows nothing about what any
        // destination puts in its state, and does not need to.
        state={{ from: location.pathname, fromState: location.state }}
      />
    );
  }
  return <>{children}</>;
}
