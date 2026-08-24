import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import Avatar from "../ui/Avatar";
import Button from "../ui/Button";
import { MenuIcon, PawIcon } from "../ui/icons";
import type { CurrentUser } from "../../types";
import VoiceAssistantBubble from "../assistant/VoiceAssistantBubble";
import NotificationBell from "../NotificationBell";
import { formatShortDate } from "../../lib/format";

/*
 * `open: true` means the route works without an account.
 *
 * Every entry used to be shown to everyone, which on a phone meant a menu of
 * nine items where five of them bounced a signed-out visitor to the login
 * screen. A navigation menu is a list of places you can go; more than half of
 * this one was a list of places you could not.
 *
 * The flags mirror the route table in App.tsx — anything wrapped in
 * `RequireAuth` is gated here.
 */
const NAV_ITEMS: Array<{ to: string; label: string; open?: boolean }> = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/analyze", label: "Analyze" },
  { to: "/symptom-check", label: "Symptom checker", open: true },
  { to: "/pets", label: "My Pets" },
  { to: "/calendar", label: "Calendar" },
  { to: "/new-owner-guide", label: "Owner Guide", open: true },
  { to: "/community", label: "Community", open: true },
  { to: "/vets", label: "Vets", open: true },
  { to: "/appointments", label: "Appointments" },
];

function navLinkClasses({ isActive }: { isActive: boolean }): string {
  return `rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
    isActive ? "bg-primary-50 text-primary-700" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
  }`;
}

/** Signed-in avatar button with a small dropdown (desktop navbar). */
function UserMenu() {
  const { user, logout } = useSession();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close on click outside.
  useEffect(() => {
    if (!open) return;
    const handleClick = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  if (!user) return null;

  const handleLogout = () => {
    setOpen(false);
    logout();
    navigate("/");
  };

  const itemClasses = "block w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-50";

  return (
    <div ref={menuRef} className="relative">
      <button
        onClick={() => setOpen((current) => !current)}
        aria-label="Account menu"
        aria-expanded={open}
        aria-haspopup="menu"
        className="rounded-full ring-2 ring-transparent transition hover:ring-primary-200"
      >
        <Avatar name={user.display_name} src={user.avatar_url} size="sm" />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full z-50 mt-2 w-56 overflow-hidden rounded-xl bg-white py-1 shadow-lg ring-1 ring-slate-200"
        >
          <div className="border-b border-slate-100 px-4 py-2">
            <p className="truncate text-sm font-semibold text-slate-800">{user.display_name}</p>
            <p className="truncate text-xs text-slate-500">{user.email}</p>
          </div>
          <Link to="/profile" role="menuitem" className={itemClasses} onClick={() => setOpen(false)}>
            My profile
          </Link>
          <Link to="/settings" role="menuitem" className={itemClasses} onClick={() => setOpen(false)}>
            Settings
          </Link>
          {user.role === "admin" && (
            <>
              <Link
                to="/admin/verifications"
                role="menuitem"
                className={itemClasses}
                onClick={() => setOpen(false)}
              >
                Vet verification queue
              </Link>
              <Link
                to="/admin/reports"
                role="menuitem"
                className={itemClasses}
                onClick={() => setOpen(false)}
              >
                Reported content
              </Link>
            </>
          )}
          <button role="menuitem" onClick={handleLogout} className={`${itemClasses} text-rose-600`}>
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}

/** Explains an active suspension or ban to the account it applies to. */
function RestrictionBanner({ user }: { user: CurrentUser }) {
  const until = user.suspended_until ? new Date(user.suspended_until) : null;
  return (
    <div className="border-b border-amber-200 bg-amber-50" role="alert">
      <div className="mx-auto max-w-6xl px-4 py-3 text-sm text-amber-900">
        <p className="font-semibold">
          {user.account_status === "banned"
            ? "Your account has been banned."
            : until
              ? `Your account is suspended until ${formatShortDate(until)}.`
              : "Your account is suspended."}
        </p>
        <p className="mt-0.5">
          You can still browse, but posting, commenting, and reporting are turned off.
          {user.moderation_note ? ` Moderator's note: ${user.moderation_note}` : ""}
        </p>
      </div>
    </div>
  );
}

export default function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user, logout } = useSession();
  const navigate = useNavigate();

  const closeMobile = () => setMobileOpen(false);
  // Signed out, only the routes that actually work without an account.
  const navItems = user ? NAV_ITEMS : NAV_ITEMS.filter((item) => item.open);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
          <Link to="/dashboard" className="flex items-center gap-2">
            <PawIcon className="h-6 w-6 text-primary-600" />
            <span className="text-lg font-bold text-slate-800">UEP EMMY</span>
          </Link>

          <nav className="ml-4 hidden items-center gap-1 md:flex" aria-label="Main">
            {navItems.map((item) => (
              <NavLink key={item.to} to={item.to} className={navLinkClasses}>
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto hidden items-center gap-2 md:flex">
            {user ? (
              <>
                <NotificationBell />
                <UserMenu />
              </>
            ) : (
              <>
                <Link to="/login">
                  <Button variant="secondary" size="sm">
                    Sign in
                  </Button>
                </Link>
                <Link to="/signup">
                  <Button size="sm">Get started</Button>
                </Link>
              </>
            )}
          </div>

          {/*
            The bell lived only in the desktop cluster above, so on a phone
            there was no way to see a notification at all — the count, the
            panel and the mark-as-read were simply absent below `md`. In-app
            alerts that only exist on a laptop are not in-app alerts.
          */}
          <div className="ml-auto flex items-center gap-1 md:hidden">
            {user && <NotificationBell />}
            <button
              onClick={() => setMobileOpen((open) => !open)}
              aria-label="Toggle navigation menu"
              aria-expanded={mobileOpen}
              className="rounded-lg p-2 text-slate-600 hover:bg-slate-100"
            >
              <MenuIcon className="h-5 w-5" />
            </button>
          </div>
        </div>

        {mobileOpen && (
          <nav
            aria-label="Main"
            className="flex flex-col gap-1 border-t border-slate-200 px-4 py-3 md:hidden"
          >
            {navItems.map((item) => (
              <NavLink key={item.to} to={item.to} className={navLinkClasses} onClick={closeMobile}>
                {item.label}
              </NavLink>
            ))}

            {user ? (
              <>
                <div className="my-1 border-t border-slate-100" />
                <div className="flex items-center gap-2 px-3 py-2">
                  <Avatar name={user.display_name} src={user.avatar_url} size="sm" />
                  <span className="truncate text-sm font-medium text-slate-700">
                    {user.display_name}
                  </span>
                </div>
                <NavLink to="/profile" className={navLinkClasses} onClick={closeMobile}>
                  My profile
                </NavLink>
                <NavLink to="/settings" className={navLinkClasses} onClick={closeMobile}>
                  Settings
                </NavLink>
                <button
                  onClick={() => {
                    closeMobile();
                    logout();
                    navigate("/");
                  }}
                  className="rounded-lg px-3 py-2 text-left text-sm font-medium text-rose-600 hover:bg-rose-50"
                >
                  Sign out
                </button>
              </>
            ) : (
              /*
                Was a single "Sign in" link. The desktop header has offered both
                "Sign in" and "Get started" all along, so a phone visitor with no
                account saw the one option that assumes they already have one —
                and the primary action of the whole product was missing from the
                only navigation they had.
              */
              <>
                <div className="my-1 border-t border-slate-100" />
                <Link to="/signup" onClick={closeMobile} className="px-3 py-1">
                  <Button className="w-full">Get started</Button>
                </Link>
                <NavLink to="/login" className={navLinkClasses} onClick={closeMobile}>
                  Sign in
                </NavLink>
              </>
            )}
          </nav>
        )}
      </header>

      {user && !user.can_participate && <RestrictionBanner user={user} />}

      {/* Extra bottom padding on phones keeps the last control on a page clear
          of the fixed assistant bubble in the corner. */}
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 pb-24 pt-6 sm:pb-6">
        <Outlet />
      </main>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-6 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <p>UEP EMMY — AI-assisted veterinary platform (student project MVP).</p>
          <p>AI estimates are informational only, not a substitute for a veterinary examination.</p>
        </div>
      </footer>

      <VoiceAssistantBubble />
    </div>
  );
}
