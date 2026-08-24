import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  getNotifications,
  getUnreadCount,
  markAllNotificationsRead,
  markNotificationRead,
} from "../api/client";
import { useSession } from "../auth/SessionContext";
import {
  AlertTriangleIcon,
  CalendarIcon,
  ChatIcon,
  CheckCircleIcon,
  ClockIcon,
  Spinner,
} from "./ui";
import { formatRelativeTime } from "../lib/format";
import type { AppNotification, NotificationKind } from "../types";

/** How often the badge re-checks. Reminders are day-grained; this is plenty. */
const POLL_MS = 60_000;

const KIND_ICON: Record<NotificationKind, (props: { className?: string }) => React.ReactNode> = {
  reminder_due: ClockIcon,
  appointment_requested: CalendarIcon,
  appointment_confirmed: CheckCircleIcon,
  appointment_declined: AlertTriangleIcon,
  appointment_cancelled: AlertTriangleIcon,
  // A suggested time is a question waiting on the reader, so it gets the clock
  // rather than the warning triangle - nothing has gone wrong.
  appointment_reschedule_proposed: ClockIcon,
  appointment_rescheduled: CheckCircleIcon,
  appointment_reschedule_declined: CalendarIcon,
  appointment_message: ChatIcon,
};

/*
 * The in-app half of notifications.
 *
 * Polls the count, not the list. A badge is a digit and the list is fifty
 * bodies; fetching the second to render the first would make the most frequent
 * request in the app also the largest. The list is only fetched when the panel
 * is actually opened.
 */
export default function NotificationBell() {
  const { user } = useSession();
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [items, setItems] = useState<AppNotification[] | null>(null);
  const [loading, setLoading] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  const refreshCount = useCallback(async () => {
    try {
      setUnread(await getUnreadCount());
    } catch {
      /* A badge that cannot load is not worth an error message. */
    }
  }, []);

  useEffect(() => {
    if (!user) return;
    void refreshCount();
    const timer = setInterval(() => void refreshCount(), POLL_MS);
    return () => clearInterval(timer);
  }, [user, refreshCount]);

  // Close on a click outside, matching the account menu beside it.
  useEffect(() => {
    if (!open) return;
    const handleClick = (event: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const openPanel = async () => {
    setOpen((current) => !current);
    if (items !== null) return;
    setLoading(true);
    try {
      setItems(await getNotifications());
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  const readOne = async (notification: AppNotification) => {
    if (notification.read_at) return;
    // Optimistic: the panel is closing as this fires, and waiting for a round
    // trip to grey out a row the reader is already navigating away from would
    // only ever be visible as a flicker.
    setItems((current) =>
      (current ?? []).map((item) =>
        item.id === notification.id ? { ...item, read_at: new Date().toISOString() } : item,
      ),
    );
    setUnread((current) => Math.max(0, current - 1));
    try {
      await markNotificationRead(notification.id);
    } catch {
      void refreshCount();
    }
  };

  const readAll = async () => {
    setItems((current) =>
      (current ?? []).map((item) => ({ ...item, read_at: item.read_at ?? new Date().toISOString() })),
    );
    setUnread(0);
    try {
      await markAllNotificationsRead();
    } catch {
      void refreshCount();
    }
  };

  if (!user) return null;

  return (
    <div ref={panelRef} className="relative">
      <button
        onClick={() => void openPanel()}
        aria-label={unread > 0 ? `Notifications, ${unread} unread` : "Notifications"}
        aria-expanded={open}
        aria-haspopup="menu"
        className="relative rounded-lg p-2 text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600"
      >
        <BellIcon className="h-5 w-5" />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 inline-flex min-w-5 items-center justify-center rounded-full bg-rose-600 px-1.5 py-0.5 text-[10px] font-bold leading-none text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full z-50 mt-2 w-96 max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl bg-white shadow-lg ring-1 ring-slate-200"
        >
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2">
            <p className="text-sm font-semibold text-slate-800">Notifications</p>
            {unread > 0 && (
              <button
                onClick={() => void readAll()}
                className="text-xs font-medium text-primary-600 hover:text-primary-700"
              >
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-96 overflow-y-auto">
            {loading && (
              <div className="flex justify-center py-8">
                <Spinner />
              </div>
            )}

            {!loading && items !== null && items.length === 0 && (
              <p className="px-4 py-8 text-center text-sm text-slate-500">
                Nothing yet. Reminders and appointment updates will appear here.
              </p>
            )}

            {!loading &&
              (items ?? []).map((item) => {
                const Icon = KIND_ICON[item.kind] ?? ClockIcon;
                const body = (
                  <div
                    className={`flex gap-3 px-4 py-3 ${item.read_at ? "bg-white" : "bg-primary-50/50"}`}
                  >
                    <span className="mt-0.5 shrink-0 text-slate-400">
                      <Icon className="h-4 w-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-slate-800">{item.title}</p>
                      <p className="mt-0.5 text-sm leading-relaxed text-slate-600">{item.body}</p>
                      <p className="mt-1 text-xs text-slate-400">
                        {formatRelativeTime(item.created_at)}
                        {/*
                          Only mentioned when it did NOT go out. Saying "emailed"
                          on every row is noise; saying nothing when the email
                          silently failed is how "I never got it" becomes
                          unanswerable.
                        */}
                        {!item.emailed && " · not emailed"}
                      </p>
                    </div>
                    {!item.read_at && (
                      <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary-600" aria-label="Unread" />
                    )}
                  </div>
                );

                return item.link ? (
                  <Link
                    key={item.id}
                    to={item.link}
                    onClick={() => {
                      void readOne(item);
                      setOpen(false);
                    }}
                    className="block border-b border-slate-50 last:border-0 hover:bg-slate-50"
                  >
                    {body}
                  </Link>
                ) : (
                  <button
                    key={item.id}
                    onClick={() => void readOne(item)}
                    className="block w-full border-b border-slate-50 text-left last:border-0 hover:bg-slate-50"
                  >
                    {body}
                  </button>
                );
              })}
          </div>

          <div className="border-t border-slate-100 px-4 py-2">
            <Link
              to="/settings"
              onClick={() => setOpen(false)}
              className="text-xs font-medium text-slate-500 hover:text-slate-700"
            >
              Notification settings
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

function BellIcon({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      className={className}
    >
      <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.7 21a2 2 0 0 1-3.4 0" />
    </svg>
  );
}
