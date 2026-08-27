import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, EMAIL_UNVERIFIED } from "../../api/client";
import { renderPage } from "../../test/utils";
import LoginPage from "./LoginPage";
import SignupPage from "./SignupPage";

const login = vi.fn();
const signup = vi.fn();
const navigate = vi.fn();

vi.mock("../../auth/SessionContext", () => ({
  useSession: () => ({
    user: null,
    initializing: false,
    login,
    signup,
    logout: vi.fn(),
    setUser: vi.fn(),
    adoptSession: vi.fn(),
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
    getEmailDelivery: vi.fn(),
  };
});

const api = await import("../../api/client");

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getEmailDelivery).mockResolvedValue({
    available: true,
    mode: "smtp",
  });
});

async function fillSignup() {
  await userEvent.type(screen.getByLabelText(/full name/i), "Alex");
  await userEvent.type(screen.getByLabelText(/^email$/i), "alex@example.com");
  await userEvent.type(screen.getByLabelText(/^password$/i), "hunter2hunter2");
  await userEvent.click(screen.getByRole("button", { name: /create account/i }));
}

describe("signing up no longer signs you in", () => {
  it("shows 'check your email' instead of going to the dashboard", async () => {
    signup.mockResolvedValue({
      email: "alex@example.com",
      verification_required: true,
      detail: "Account created. We have sent a confirmation link to alex@example.com.",
    });

    renderPage(<SignupPage />);
    await fillSignup();

    expect(await screen.findByText(/check your email/i)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/confirmation link to alex@example.com/i);
    // The old behaviour: straight to the dashboard on a session that should
    // not exist yet.
    expect(navigate).not.toHaveBeenCalled();
  });

  it("says plainly that sign-in is blocked until the link is opened", async () => {
    signup.mockResolvedValue({
      email: "alex@example.com",
      verification_required: true,
      detail: "Account created.",
    });

    renderPage(<SignupPage />);
    await fillSignup();
    await screen.findByText(/check your email/i);

    expect(screen.getByText(/cannot sign you in until you have opened it/i)).toBeInTheDocument();
  });

  it("offers a way to sign in and a way to get the link again", async () => {
    signup.mockResolvedValue({ email: "a@b.c", verification_required: true, detail: "ok" });

    renderPage(<SignupPage />);
    await fillSignup();
    await screen.findByText(/check your email/i);

    expect(screen.getByRole("link", { name: /go to sign in/i })).toHaveAttribute("href", "/login");
    expect(screen.getByRole("link", { name: /send the link again/i })).toHaveAttribute(
      "href",
      "/resend-verification",
    );
  });

  it("warns before the account exists when this server cannot send email", async () => {
    vi.mocked(api.getEmailDelivery).mockResolvedValue({
      available: false,
      mode: "outbox",
    });

    renderPage(<SignupPage />);

    // On the form itself, not only on the screen afterwards: a confirmation
    // that cannot be delivered is a locked account, and that is worth knowing
    // before you make one.
    expect(await screen.findByText(/this server cannot send email/i)).toBeInTheDocument();
  });

  it("keeps the form up and shows the error when signup is refused", async () => {
    signup.mockRejectedValue(new ApiError(409, "An account with this email already exists."));

    renderPage(<SignupPage />);
    await fillSignup();

    expect(await screen.findByRole("alert")).toHaveTextContent(/already exists/i);
    expect(screen.getByRole("button", { name: /create account/i })).toBeInTheDocument();
  });
});

describe("signing in with an unconfirmed address", () => {
  async function attemptLogin() {
    await userEvent.type(screen.getByLabelText(/email/i), "alex@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "hunter2hunter2");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
  }

  it("explains the block and links to the resend page", async () => {
    login.mockRejectedValue(
      new ApiError(
        403,
        "Confirm your email address before signing in.",
        EMAIL_UNVERIFIED,
      ),
    );

    renderPage(<LoginPage />);
    await attemptLogin();

    expect(await screen.findByText(/confirm your email address first/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /send the confirmation link again/i })).toHaveAttribute(
      "href",
      "/resend-verification",
    );
    expect(navigate).not.toHaveBeenCalled();
  });

  it("shows a ban as a plain refusal, with no resend link", async () => {
    // Same 403, different reason, opposite ending. This is why the server
    // sends a code rather than leaving the interface to read the wording.
    login.mockRejectedValue(
      new ApiError(403, "Your account has been banned for violating the community rules."),
    );

    renderPage(<LoginPage />);
    await attemptLogin();

    expect(await screen.findByRole("alert")).toHaveTextContent(/banned/i);
    expect(
      screen.queryByRole("link", { name: /send the confirmation link again/i }),
    ).not.toBeInTheDocument();
  });

  it("shows a wrong password as a wrong password", async () => {
    login.mockRejectedValue(new ApiError(401, "Incorrect email or password."));

    renderPage(<LoginPage />);
    await attemptLogin();

    expect(await screen.findByRole("alert")).toHaveTextContent(/incorrect email or password/i);
    expect(screen.queryByText(/confirm your email address first/i)).not.toBeInTheDocument();
  });

  it("goes through when the account is confirmed", async () => {
    login.mockResolvedValue({ id: "user-1" });

    renderPage(<LoginPage />);
    await attemptLogin();

    await waitFor(() => expect(navigate).toHaveBeenCalled());
    expect(screen.queryByText(/confirm your email address first/i)).not.toBeInTheDocument();
  });

  it("offers the forgotten-password route as well", () => {
    renderPage(<LoginPage />);

    expect(screen.getByRole("link", { name: /forgot your password/i })).toHaveAttribute(
      "href",
      "/forgot-password",
    );
  });
});
