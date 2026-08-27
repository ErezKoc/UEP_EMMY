import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage, aUser } from "../test/utils";
import type { AppNotification, EmailState } from "../types";
import NotificationBell from "./NotificationBell";

vi.mock("../auth/SessionContext", () => ({
  useSession: () => ({
    user: aUser(),
    initializing: false,
    login: vi.fn(),
    signup: vi.fn(),
    logout: vi.fn(),
    setUser: vi.fn(),
    adoptSession: vi.fn(),
  }),
}));

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    getUnreadCount: vi.fn().mockResolvedValue(1),
    getNotifications: vi.fn(),
    markNotificationRead: vi.fn(),
    markAllNotificationsRead: vi.fn(),
  };
});

const api = await import("../api/client");

function aNotification(email_state: EmailState): AppNotification {
  return {
    id: "n1",
    kind: "reminder_due",
    title: "Reminder: Rabies booster",
    body: "Rabies booster for Buddy is due tomorrow.",
    link: null,
    read_at: null,
    emailed: email_state === "sent",
    email_state,
    created_at: new Date().toISOString(),
  };
}

async function openBell(email_state: EmailState) {
  vi.mocked(api.getNotifications).mockResolvedValue([aNotification(email_state)]);
  const rendered = renderPage(<NotificationBell />);
  await userEvent.click(screen.getByRole("button", { name: /notifications/i }));
  await screen.findByText(/rabies booster for buddy/i);
  return rendered;
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getUnreadCount).mockResolvedValue(1);
});

describe("what the bell says about the email half", () => {
  it("says nothing when the email was sent", async () => {
    const { container } = await openBell("sent");

    // A note on every row that the email arrived is noise.
    expect(container.textContent).not.toMatch(/email/i);
  });

  it("says nothing when the reader has email switched off", async () => {
    const { container } = await openBell("not_requested");

    // Nothing was meant to go out. A mark here would send somebody hunting for
    // a problem they created on purpose.
    expect(container.textContent).not.toMatch(/email/i);
  });

  it("says an email is on its way while it is queued", async () => {
    await openBell("queued");

    expect(screen.getByText(/email on its way/i)).toBeInTheDocument();
  });

  it("says an email could not be delivered when it was refused", async () => {
    await openBell("failed");

    expect(screen.getByText(/email could not be delivered/i)).toBeInTheDocument();
  });

  it("distinguishes a server that cannot send from one that failed", async () => {
    const { container } = await openBell("unavailable");

    expect(screen.getByText(/email unavailable on this server/i)).toBeInTheDocument();
    // "Failed" would send somebody looking for a fault that does not exist.
    expect(container.textContent).not.toMatch(/could not be delivered/i);
  });

  it("has dropped the old 'not emailed' wording", async () => {
    for (const state of ["queued", "failed", "unavailable", "not_requested"] as const) {
      const { container, unmount } = await openBell(state);
      expect(container.textContent).not.toMatch(/not emailed/i);
      unmount();
    }
  });
});
