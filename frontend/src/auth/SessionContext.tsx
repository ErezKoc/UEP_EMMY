import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import * as api from "../api/client";
import type { CurrentUser, SignupPayload, SignupResponse } from "../types";

/*
 * Session state for the whole app (Member 2).
 *
 * The token lives in localStorage (via api/client) so a page refresh keeps the
 * user signed in; on mount we call /v1/auth/me to turn the stored token back
 * into a user object. `initializing` is true during that first check so pages
 * can wait before deciding to redirect to /login.
 */

interface SessionContextValue {
  /** The signed-in user, or null when signed out. */
  user: CurrentUser | null;
  /** True while the stored token is being validated on first load. */
  initializing: boolean;
  login: (email: string, password: string) => Promise<CurrentUser>;
  /**
   * Create an account. Does NOT start a session.
   *
   * Returns what the server said instead of a user, because there is no user to
   * return yet: signing in needs a confirmed address, and confirming it happens
   * in the reader's inbox rather than here.
   */
  signup: (payload: SignupPayload) => Promise<SignupResponse>;
  logout: () => void;
  /** Merge freshly saved profile data into the session (e.g. after PATCH). */
  setUser: (user: CurrentUser) => void;
  /**
   * Adopt a session the caller already obtained.
   *
   * For the password-reset page, which is handed a token and a user by the
   * reset endpoint itself. Sending somebody who has just proved they hold the
   * inbox AND chosen a password to a login form to type it again is a step that
   * protects nobody.
   */
  adoptSession: (token: string, user: CurrentUser) => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUserState] = useState<CurrentUser | null>(null);
  const [initializing, setInitializing] = useState(() => api.getStoredToken() !== null);

  useEffect(() => {
    if (api.getStoredToken() === null) return;
    let cancelled = false;
    api
      .fetchCurrentUser()
      .then((restored) => {
        if (!cancelled) setUserState(restored);
      })
      .catch((error) => {
        // Expired/invalid token: drop it and stay signed out. Keep the token
        // on network errors so a backend restart doesn't log everyone out.
        if (error instanceof api.ApiError) api.setStoredToken(null);
      })
      .finally(() => {
        if (!cancelled) setInitializing(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string): Promise<CurrentUser> => {
    const { token, user: loggedIn } = await api.login(email, password);
    api.setStoredToken(token);
    setUserState(loggedIn);
    return loggedIn;
  }, []);

  const signup = useCallback(async (payload: SignupPayload): Promise<SignupResponse> => {
    // No token is stored and no user is set: the account exists but cannot be
    // used until the link in its confirmation email has been opened.
    return api.signup(payload);
  }, []);

  const logout = useCallback(() => {
    api.setStoredToken(null);
    setUserState(null);
  }, []);

  const setUser = useCallback((updated: CurrentUser) => setUserState(updated), []);

  const adoptSession = useCallback((token: string, adopted: CurrentUser) => {
    api.setStoredToken(token);
    setUserState(adopted);
  }, []);

  return (
    <SessionContext.Provider
      value={{ user, initializing, login, signup, logout, setUser, adoptSession }}
    >
      {children}
    </SessionContext.Provider>
  );
}

/** Access the session: `const { user, login, logout } = useSession();` */
export function useSession(): SessionContextValue {
  const context = useContext(SessionContext);
  if (!context) throw new Error("useSession must be used within SessionProvider");
  return context;
}
