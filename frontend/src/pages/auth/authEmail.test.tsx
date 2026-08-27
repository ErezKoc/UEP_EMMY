import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import { renderPage } from "../../test/utils";
import ForgotPasswordPage from "./ForgotPasswordPage";
import ResendVerificationPage from "./ResendVerificationPage";
import ResetPasswordPage from "./ResetPasswordPage";
import VerifyEmailPage from "./VerifyEmailPage";

const navigate = vi.fn();
const adoptSession = vi.fn();
const setUser = vi.fn();
let sessionUser: unknown = null;

vi.mock("../../auth/SessionContext", () => ({
  useSession: () => ({
    user: sessionUser,
    initializing: false,
    login: vi.fn(),
    signup: vi.fn(),
    logout: vi.fn(),
    setUser,
    adoptSession,
  }),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => navigate };
});

vi.mock("../../api/client", async () => {
  const actual = await vi.importActual<typeof import("../../api/client")>("../../api/client");
  return {
    ...actual,
    verifyEmail: vi.fn(),
    resendVerification: vi.fn(),
    requestPasswordReset: vi.fn(),
    resetPassword: vi.fn(),
    fetchCurrentUser: vi.fn(),
    // Every auth screen probes this to decide whether to warn that the server
    // cannot send mail. Configured per test where it matters.
    getEmailDelivery: vi.fn().mockResolvedValue({
      available: true,
      mode: "smtp",
    }),
  };
});

const api = await import("../../api/client");

beforeEach(() => {
  vi.clearAllMocks();
  sessionUser = null;
  vi.mocked(api.getEmailDelivery).mockResolvedValue({
    available: true,
    mode: "smtp",
  });
});

// ------------------------------------------------------------- verify email

describe("the page a verification link lands on", () => {
  it("shows that it is working while the link is being checked", () => {
    vi.mocked(api.verifyEmail).mockReturnValue(new Promise(() => {}));

    renderPage(<VerifyEmailPage />, { route: "/verify-email?token=abc" });

    // Not `getByRole("status")` - the spinner inside carries that role too.
    expect(screen.getByText(/checking your link/i)).toBeInTheDocument();
  });

  it("confirms the address when the link is good", async () => {
    vi.mocked(api.verifyEmail).mockResolvedValue({
      email: "alex@example.com",
      verified: true,
      email_changed: false,
      detail: "Thank you - your email address is confirmed.",
    });

    renderPage(<VerifyEmailPage />, { route: "/verify-email?token=abc" });

    expect(await screen.findByText(/your email address is confirmed/i)).toBeInTheDocument();
    expect(api.verifyEmail).toHaveBeenCalledWith("abc");
  });

  it("says which address you now sign in with after a change", async () => {
    vi.mocked(api.verifyEmail).mockResolvedValue({
      email: "new@example.com",
      verified: true,
      email_changed: true,
      detail: "Your new email address is confirmed.",
    });

    renderPage(<VerifyEmailPage />, { route: "/verify-email?token=abc" });

    expect(await screen.findByText(/you now sign in with/i)).toBeInTheDocument();
    expect(screen.getByText("new@example.com")).toBeInTheDocument();
  });

  it("offers a fresh link when this one has expired", async () => {
    vi.mocked(api.verifyEmail).mockRejectedValue(
      new ApiError(410, "This link has expired. Ask for a new one and we will send another."),
    );

    renderPage(<VerifyEmailPage />, { route: "/verify-email?token=abc" });

    expect(await screen.findByRole("alert")).toHaveTextContent(/expired/i);
    expect(screen.getByRole("link", { name: /send me a new link/i })).toHaveAttribute(
      "href",
      "/resend-verification",
    );
  });

  it("tells somebody to check they copied the whole link when it is not valid", async () => {
    vi.mocked(api.verifyEmail).mockRejectedValue(new ApiError(400, "This link is not valid."));

    renderPage(<VerifyEmailPage />, { route: "/verify-email?token=nonsense" });

    expect(await screen.findByRole("alert")).toHaveTextContent(/not valid/i);
    expect(screen.getByText(/copying the whole address/i)).toBeInTheDocument();
  });

  it("does not call the API at all when the address carries no token", async () => {
    renderPage(<VerifyEmailPage />, { route: "/verify-email" });

    expect(await screen.findByRole("alert")).toHaveTextContent(/no confirmation code/i);
    expect(api.verifyEmail).not.toHaveBeenCalled();
  });

  it("offers a retry when the server could not be reached", async () => {
    vi.mocked(api.verifyEmail).mockRejectedValue(new ApiError(0, "Could not reach the server."));

    renderPage(<VerifyEmailPage />, { route: "/verify-email?token=abc" });

    expect(await screen.findByRole("alert")).toHaveTextContent(/could not reach the server/i);
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("spends the token exactly once even though effects run twice in StrictMode", async () => {
    vi.mocked(api.verifyEmail).mockResolvedValue({
      email: "alex@example.com",
      verified: true,
      email_changed: false,
      detail: "Confirmed.",
    });

    renderPage(<VerifyEmailPage />, { route: "/verify-email?token=abc" });
    await screen.findByText("Confirmed.");

    expect(api.verifyEmail).toHaveBeenCalledTimes(1);
  });
});

// ----------------------------------------------------------------- resend

describe("asking for another verification email", () => {
  it("reports back without confirming whether the address is registered", async () => {
    vi.mocked(api.resendVerification).mockResolvedValue({
      detail: "If that address has an account with us, we have sent it an email.",
    });

    renderPage(<ResendVerificationPage />);
    await userEvent.type(screen.getByLabelText(/email/i), "alex@example.com");
    await userEvent.click(screen.getByRole("button", { name: /send the link/i }));

    const message = await screen.findByRole("status");
    expect(message).toHaveTextContent(/if that address has an account/i);
    // The one thing this screen must never say.
    expect(message.textContent).not.toMatch(/we found your account/i);
  });

  it("shows the rate limit rather than pretending an email went out", async () => {
    vi.mocked(api.resendVerification).mockRejectedValue(
      new ApiError(429, "Too many requests for this address. Please wait a few minutes."),
    );

    renderPage(<ResendVerificationPage />);
    await userEvent.type(screen.getByLabelText(/email/i), "alex@example.com");
    await userEvent.click(screen.getByRole("button", { name: /send the link/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/too many requests/i);
  });

  it("warns when this deployment cannot send email at all", async () => {
    vi.mocked(api.getEmailDelivery).mockResolvedValue({
      available: false,
      mode: "outbox",
    });

    renderPage(<ResendVerificationPage />);

    expect(await screen.findByText(/this server cannot send email/i)).toBeInTheDocument();
  });

  it("says nothing about delivery when email is working", async () => {
    renderPage(<ResendVerificationPage />);

    await waitFor(() => expect(api.getEmailDelivery).toHaveBeenCalled());
    expect(screen.queryByText(/cannot send email/i)).not.toBeInTheDocument();
  });
});

// -------------------------------------------------------- forgotten password

describe("asking for a password reset", () => {
  it("gives the same answer whatever address was typed", async () => {
    vi.mocked(api.requestPasswordReset).mockResolvedValue({
      detail: "If that address has an account with us, we have sent it an email.",
    });

    renderPage(<ForgotPasswordPage />);
    await userEvent.type(screen.getByLabelText(/email/i), "nobody@example.com");
    await userEvent.click(screen.getByRole("button", { name: /send me a reset link/i }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      /if that address has an account/i,
    );
    expect(screen.getByText(/expires in an hour/i)).toBeInTheDocument();
  });

  it("surfaces a failure instead of claiming success", async () => {
    vi.mocked(api.requestPasswordReset).mockRejectedValue(
      new ApiError(429, "Too many requests for this address."),
    );

    renderPage(<ForgotPasswordPage />);
    await userEvent.type(screen.getByLabelText(/email/i), "alex@example.com");
    await userEvent.click(screen.getByRole("button", { name: /send me a reset link/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/too many requests/i);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("lets somebody go back and try a different address", async () => {
    vi.mocked(api.requestPasswordReset).mockResolvedValue({ detail: "Sent if it exists." });

    renderPage(<ForgotPasswordPage />);
    await userEvent.type(screen.getByLabelText(/email/i), "alex@example.com");
    await userEvent.click(screen.getByRole("button", { name: /send me a reset link/i }));
    await screen.findByRole("status");
    await userEvent.click(screen.getByRole("button", { name: /different address/i }));

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------- choosing a new one

describe("the reset page", () => {
  it("refuses two passwords that do not match, without calling the API", async () => {
    renderPage(<ResetPasswordPage />, { route: "/reset-password?token=abc" });

    await userEvent.type(screen.getByLabelText(/^new password$/i), "long-enough-1");
    await userEvent.type(screen.getByLabelText(/confirm new password/i), "different-one");
    await userEvent.click(screen.getByRole("button", { name: /change my password/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/not the same/i);
    expect(api.resetPassword).not.toHaveBeenCalled();
  });

  it("refuses a password that is too short", async () => {
    renderPage(<ResetPasswordPage />, { route: "/reset-password?token=abc" });

    await userEvent.type(screen.getByLabelText(/^new password$/i), "short");
    await userEvent.type(screen.getByLabelText(/confirm new password/i), "short");
    await userEvent.click(screen.getByRole("button", { name: /change my password/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/at least 8 characters/i);
    expect(api.resetPassword).not.toHaveBeenCalled();
  });

  it("signs the person in once the password is changed", async () => {
    vi.mocked(api.resetPassword).mockResolvedValue({
      token: "session-token",
      // The page only forwards this; its shape is the API's business.
      user: { id: "user-1" } as never,
    });

    renderPage(<ResetPasswordPage />, { route: "/reset-password?token=abc" });
    await userEvent.type(screen.getByLabelText(/^new password$/i), "brand-new-secret");
    await userEvent.type(screen.getByLabelText(/confirm new password/i), "brand-new-secret");
    await userEvent.click(screen.getByRole("button", { name: /change my password/i }));

    await waitFor(() => expect(adoptSession).toHaveBeenCalled());
    expect(api.resetPassword).toHaveBeenCalledWith("abc", "brand-new-secret");
    expect(navigate).toHaveBeenCalledWith("/dashboard", { replace: true });
  });

  it("explains a spent link and offers a new one", async () => {
    vi.mocked(api.resetPassword).mockRejectedValue(new ApiError(410, "gone"));

    renderPage(<ResetPasswordPage />, { route: "/reset-password?token=abc" });
    await userEvent.type(screen.getByLabelText(/^new password$/i), "brand-new-secret");
    await userEvent.type(screen.getByLabelText(/confirm new password/i), "brand-new-secret");
    await userEvent.click(screen.getByRole("button", { name: /change my password/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/expired or has already been used/i);
    expect(screen.getByRole("link", { name: /send me a new link/i })).toHaveAttribute(
      "href",
      "/forgot-password",
    );
  });

  it("shows the dead-link page immediately when there is no token at all", () => {
    renderPage(<ResetPasswordPage />, { route: "/reset-password" });

    expect(screen.getByRole("alert")).toHaveTextContent(/not valid/i);
    expect(screen.queryByLabelText(/^new password$/i)).not.toBeInTheDocument();
  });

  it("keeps the form up when the password itself was refused", async () => {
    vi.mocked(api.resetPassword).mockRejectedValue(
      new ApiError(422, "Pick a longer password."),
    );

    renderPage(<ResetPasswordPage />, { route: "/reset-password?token=abc" });
    await userEvent.type(screen.getByLabelText(/^new password$/i), "brand-new-secret");
    await userEvent.type(screen.getByLabelText(/confirm new password/i), "brand-new-secret");
    await userEvent.click(screen.getByRole("button", { name: /change my password/i }));

    // A rejected password is worth retyping; a spent link is not, and the two
    // must not be shown the same way.
    expect(await screen.findByRole("alert")).toHaveTextContent(/pick a longer password/i);
    expect(screen.getByLabelText(/^new password$/i)).toBeInTheDocument();
  });
});
