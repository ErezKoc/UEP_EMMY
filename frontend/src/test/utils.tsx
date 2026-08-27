import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { ToastProvider } from "../components/ui/toast";
import type { CurrentUser } from "../types";

/**
 * Render a page inside the two providers every page assumes.
 *
 * The session is NOT one of them: pages that need a user get it from a mocked
 * `useSession`, because driving the real provider would mean stubbing the token
 * in localStorage and waiting on a `/auth/me` round trip to set up a test about
 * something else entirely.
 */
export function renderPage(
  element: ReactElement,
  { route = "/" }: { route?: string } = {},
) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <ToastProvider>{element}</ToastProvider>
    </MemoryRouter>,
  );
}

/** A complete `CurrentUser`, so tests only state the fields they care about. */
export function aUser(overrides: Partial<CurrentUser> = {}): CurrentUser {
  return {
    id: "user-1",
    email: "alex@example.com",
    display_name: "Alex",
    role: "owner",
    bio: null,
    avatar_url: null,
    clinic_name: null,
    license_number: null,
    verification_status: "unverified",
    is_verified_vet: false,
    account_status: "active",
    created_at: "2026-01-01T00:00:00Z",
    clinic_phone: null,
    clinic_emergency_phone: null,
    clinic_email: null,
    clinic_website: null,
    clinic_address_line: null,
    clinic_city: null,
    clinic_postcode: null,
    clinic_country: null,
    clinic_hours: null,
    clinic_hours_grid: null,
    clinic_timezone: null,
    clinic_latitude: null,
    clinic_longitude: null,
    specialties: [],
    consultation_fee_min: null,
    consultation_fee_max: null,
    fee_currency: null,
    accepts_appointments: false,
    notify_in_app: true,
    notify_email: true,
    notify_lead_days: 1,
    notify_time: "09:00:00",
    notify_timezone: null,
    notify_leads: [],
    email_verified_at: null,
    pending_email: null,
    suspended_until: null,
    moderation_note: null,
    can_participate: true,
    ...overrides,
  } as CurrentUser;
}
