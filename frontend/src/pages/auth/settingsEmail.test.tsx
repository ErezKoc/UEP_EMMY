import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage, aUser } from "../../test/utils";
import type { CurrentUser } from "../../types";
import SettingsPage from "./SettingsPage";

let sessionUser: CurrentUser = aUser();
const setUser = vi.fn();

vi.mock("../../auth/SessionContext", () => ({
  useSession: () => ({
    user: sessionUser,
    initializing: false,
    login: vi.fn(),
    signup: vi.fn(),
    logout: vi.fn(),
    setUser,
    adoptSession: vi.fn(),
  }),
}));

vi.mock("../../api/client", async () => {
  const actual = await vi.importActual<typeof import("../../api/client")>("../../api/client");
  return {
    ...actual,
    updateProfile: vi.fn(),
    changePassword: vi.fn(),
    resendVerification: vi.fn(),
    getEmailDelivery: vi.fn(),
  };
});

const api = await import("../../api/client");

const WORKING = { available: true, mode: "smtp" as const };
const NO_SERVER = { available: false, mode: "outbox" as const };

beforeEach(() => {
  vi.clearAllMocks();
  sessionUser = aUser();
  vi.mocked(api.getEmailDelivery).mockResolvedValue(WORKING);
});

describe("what Settings says about email delivery", () => {
  it("says plainly that this server cannot send email", async () => {
    vi.mocked(api.getEmailDelivery).mockResolvedValue(NO_SERVER);

    renderPage(<SettingsPage />);

    expect(await screen.findByText(/this server cannot send email/i)).toBeInTheDocument();
    expect(screen.getByText(/written to the server's outbox/i)).toBeInTheDocument();
  });

  it("says nothing at all when email is working", async () => {
    /*
     * Working email is the state people expect, so announcing it is noise on a
     * page somebody opened to change something else. The version of this that
     * named the sending address also published a deployment detail to every
     * reader, for no benefit they could act on.
     */
    renderPage(<SettingsPage />);

    await waitFor(() => expect(api.getEmailDelivery).toHaveBeenCalled());
    expect(screen.queryByText(/email is working/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/cannot send email/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/no-reply@/i)).not.toBeInTheDocument();
  });

  it("claims nothing while the answer is still loading", () => {
    vi.mocked(api.getEmailDelivery).mockReturnValue(new Promise(() => {}));

    renderPage(<SettingsPage />);

    expect(screen.queryByText(/cannot send email/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/email is working/i)).not.toBeInTheDocument();
  });

  it("no longer uses the old 'not emailed' wording anywhere", async () => {
    vi.mocked(api.getEmailDelivery).mockResolvedValue(NO_SERVER);

    const { container } = renderPage(<SettingsPage />);
    await screen.findByText(/this server cannot send email/i);

    expect(container.textContent).not.toMatch(/not emailed/i);
  });

  it("explains that security email still goes out when notifications are off", async () => {
    sessionUser = aUser({ notify_email: false });

    renderPage(<SettingsPage />);

    expect(
      await screen.findByText(/confirmation and password-reset messages are still sent/i),
    ).toBeInTheDocument();
  });
});

describe("the state of the address itself", () => {
  it("offers to resend the link when the address is not confirmed", async () => {
    vi.mocked(api.resendVerification).mockResolvedValue({ detail: "On its way if it exists." });

    renderPage(<SettingsPage />);
    expect(screen.getByText(/this address is not confirmed\./i)).toBeInTheDocument();
    // No longer says "nothing is blocked" - signing in now needs a confirmed
    // address, so that reassurance became false.
    expect(screen.getByText(/confirm it to keep signing in/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /send me the confirmation link/i }));

    await waitFor(() => expect(api.resendVerification).toHaveBeenCalledWith("alex@example.com"));
  });

  it("says so once the address is confirmed", () => {
    sessionUser = aUser({ email_verified_at: "2026-02-01T00:00:00Z" });

    renderPage(<SettingsPage />);

    expect(screen.getByText(/this address is confirmed/i)).toBeInTheDocument();
    expect(screen.queryByText(/this address is not confirmed\./i)).not.toBeInTheDocument();
  });

  it("shows a pending change and says which address still signs you in", () => {
    sessionUser = aUser({ pending_email: "new@example.com" });

    renderPage(<SettingsPage />);

    expect(screen.getByText(/waiting for confirmation/i)).toBeInTheDocument();
    expect(screen.getByText("new@example.com")).toBeInTheDocument();
    expect(screen.getByText(/you keep signing in with/i)).toBeInTheDocument();
  });

  it("never claims the address changed when only a link was sent", async () => {
    vi.mocked(api.updateProfile).mockResolvedValue(
      aUser({ pending_email: "new@example.com" }),
    );

    renderPage(<SettingsPage />);
    const field = screen.getByLabelText("Email");
    await userEvent.clear(field);
    await userEvent.type(field, "new@example.com");
    await userEvent.click(screen.getByRole("button", { name: /send confirmation link/i }));

    const notice = await screen.findByText(/we have sent a confirmation link/i);
    expect(notice).toHaveTextContent("new@example.com");
    expect(notice).toHaveTextContent(/stays alex@example.com until you open it/i);
  });

  it("surfaces an address that is already taken", async () => {
    const { ApiError } = await import("../../api/client");
    vi.mocked(api.updateProfile).mockRejectedValue(
      new ApiError(409, "An account with this email already exists."),
    );

    renderPage(<SettingsPage />);
    const field = screen.getByLabelText("Email");
    await userEvent.clear(field);
    await userEvent.type(field, "taken@example.com");
    await userEvent.click(screen.getByRole("button", { name: /send confirmation link/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/already exists/i);
  });
});

describe("lead times", () => {
  it("saves a second lead time alongside the first", async () => {
    vi.mocked(api.updateProfile).mockResolvedValue(aUser({ notify_leads: [7] }));

    renderPage(<SettingsPage />);
    await userEvent.click(screen.getByLabelText(/a week before/i));

    await waitFor(() =>
      expect(api.updateProfile).toHaveBeenCalledWith({ notify_leads: [7] }),
    );
  });

  it("falls back to the single setting when the last one is unticked", async () => {
    sessionUser = aUser({ notify_leads: [7] });
    vi.mocked(api.updateProfile).mockResolvedValue(aUser({ notify_leads: [] }));

    renderPage(<SettingsPage />);
    await userEvent.click(screen.getByLabelText(/a week before/i));

    // null, not [] - the API reads "no list" as "use notify_lead_days".
    await waitFor(() =>
      expect(api.updateProfile).toHaveBeenCalledWith({ notify_leads: null }),
    );
  });
});
