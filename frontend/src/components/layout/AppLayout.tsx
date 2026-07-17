import { useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import Button from "../ui/Button";
import { MenuIcon, PawIcon } from "../ui/icons";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/analyze", label: "Analyze" },
  { to: "/pets", label: "My Pets" },
  { to: "/community", label: "Community" },
  { to: "/vets", label: "Vets" },
];

function navLinkClasses({ isActive }: { isActive: boolean }): string {
  return `rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
    isActive ? "bg-primary-50 text-primary-700" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
  }`;
}

export default function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
          <Link to="/" className="flex items-center gap-2">
            <PawIcon className="h-6 w-6 text-primary-600" />
            <span className="text-lg font-bold text-slate-800">UEP EMMY</span>
          </Link>

          <nav className="ml-4 hidden items-center gap-1 md:flex" aria-label="Main">
            {NAV_ITEMS.map((item) => (
              <NavLink key={item.to} to={item.to} className={navLinkClasses}>
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto hidden items-center gap-2 md:flex">
            {/* Member 2: replace with session-aware user menu (avatar, profile, logout). */}
            <Link to="/login">
              <Button variant="secondary" size="sm">
                Sign in
              </Button>
            </Link>
            <Link to="/signup">
              <Button size="sm">Get started</Button>
            </Link>
          </div>

          <button
            onClick={() => setMobileOpen((open) => !open)}
            aria-label="Toggle navigation menu"
            aria-expanded={mobileOpen}
            className="ml-auto rounded-lg p-2 text-slate-600 hover:bg-slate-100 md:hidden"
          >
            <MenuIcon className="h-5 w-5" />
          </button>
        </div>

        {mobileOpen && (
          <nav
            aria-label="Main"
            className="flex flex-col gap-1 border-t border-slate-200 px-4 py-3 md:hidden"
          >
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={navLinkClasses}
                onClick={() => setMobileOpen(false)}
              >
                {item.label}
              </NavLink>
            ))}
            <NavLink to="/login" className={navLinkClasses} onClick={() => setMobileOpen(false)}>
              Sign in
            </NavLink>
          </nav>
        )}
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        <Outlet />
      </main>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-6 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <p>UEP EMMY — AI-assisted veterinary platform (student project MVP).</p>
          <p>AI estimates are informational only, not a substitute for a veterinary examination.</p>
        </div>
      </footer>
    </div>
  );
}
