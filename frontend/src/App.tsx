import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import RequireAdmin from "./auth/RequireAdmin";
import RequireAuth from "./auth/RequireAuth";
import { SessionProvider, useSession } from "./auth/SessionContext";
import AppLayout from "./components/layout/AppLayout";
import { Spinner } from "./components/ui";
import { ToastProvider } from "./components/ui/toast";
import ReportQueuePage from "./pages/admin/ReportQueuePage";
import VerificationQueuePage from "./pages/admin/VerificationQueuePage";
import Dashboard from "./pages/Dashboard";
import Landing from "./pages/Landing";
import NotFound from "./pages/NotFound";
import AnalysisHistoryPage from "./pages/analysis/AnalysisHistoryPage";
import AnalysisDetailPage from "./pages/analysis/AnalysisDetailPage";
import AnalyzePage from "./pages/analysis/AnalyzePage";
import LoginPage from "./pages/auth/LoginPage";
import ProfilePage from "./pages/auth/ProfilePage";
import SettingsPage from "./pages/auth/SettingsPage";
import SignupPage from "./pages/auth/SignupPage";
import CommunityPage from "./pages/community/CommunityPage";
import NewPostPage from "./pages/community/NewPostPage";
import PostDetailPage from "./pages/community/PostDetailPage";
import VetsPage from "./pages/community/VetsPage";
import PetDetailPage from "./pages/pets/PetDetailPage";
import PetsPage from "./pages/pets/PetsPage";
import CalendarPage from "./pages/reminders/CalendarPage";
import SymptomCheckHistoryPage from "./pages/triage/SymptomCheckHistoryPage";
import SymptomCheckPage from "./pages/triage/SymptomCheckPage";

/**
 * "/" is the public promotional page, but only for visitors who have no
 * session: once signed in there is a real dashboard to show instead, so the
 * marketing page is never the destination.
 */
function LandingOrDashboard() {
  const { user, initializing } = useSession();
  // Wait for the stored token to resolve: rendering the marketing page first
  // would flash it at a signed-in member every time they reload "/".
  if (initializing) {
    return (
      <div className="flex justify-center py-16">
        <Spinner />
      </div>
    );
  }
  return user ? <Navigate to="/dashboard" replace /> : <Landing />;
}

/*
 * Route registry — one route per page, stub pages included, so every member's
 * area is reachable from day one. Replace the stub component inside your page
 * file; you should rarely need to touch this file.
 *
 * Ownership:
 *   Member 2 — /login /signup /profile /settings
 *   Member 3 — /pets /pets/:petId
 *   Member 4 — /analyze /analysis/history /symptom-check
 *   Member 5 — /community /community/new /community/:postId /vets
 *   Shared    — /admin/verifications (vet credential review, admins only)
 *   Shared    — /admin/reports (community report review, admins only)
 */
export default function App() {
  return (
    <ToastProvider>
      <SessionProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<AppLayout />}>
              <Route path="/" element={<LandingOrDashboard />} />
              <Route
                path="/dashboard"
                element={
                  <RequireAuth>
                    <Dashboard />
                  </RequireAuth>
                }
              />

              <Route path="/login" element={<LoginPage />} />
              <Route path="/signup" element={<SignupPage />} />
              <Route
                path="/profile"
                element={
                  <RequireAuth>
                    <ProfilePage />
                  </RequireAuth>
                }
              />
              <Route
                path="/settings"
                element={
                  <RequireAuth>
                    <SettingsPage />
                  </RequireAuth>
                }
              />

              <Route
                path="/pets"
                element={
                  <RequireAuth>
                    <PetsPage />
                  </RequireAuth>
                }
              />
              <Route
                path="/pets/:petId"
                element={
                  <RequireAuth>
                    <PetDetailPage />
                  </RequireAuth>
                }
              />

              <Route
                path="/calendar"
                element={
                  <RequireAuth>
                    <CalendarPage />
                  </RequireAuth>
                }
              />

              <Route
                path="/analyze"
                element={
                  <RequireAuth>
                    <AnalyzePage />
                  </RequireAuth>
                }
              />
              {/* Advice needs no photo and no account — deliberately public.
                  Saving it does need an account, so the history is gated. */}
              <Route path="/symptom-check" element={<SymptomCheckPage />} />
              <Route
                path="/symptom-check/history"
                element={
                  <RequireAuth>
                    <SymptomCheckHistoryPage />
                  </RequireAuth>
                }
              />
              <Route
                path="/analysis/history"
                element={
                  <RequireAuth>
                    <AnalysisHistoryPage />
                  </RequireAuth>
                }
              />
              <Route
                path="/analysis/:analysisId"
                element={
                  <RequireAuth>
                    <AnalysisDetailPage />
                  </RequireAuth>
                }
              />

              <Route path="/community" element={<CommunityPage />} />
              <Route
                path="/community/new"
                element={
                  <RequireAuth>
                    <NewPostPage />
                  </RequireAuth>
                }
              />
              <Route path="/community/:postId" element={<PostDetailPage />} />
              <Route path="/vets" element={<VetsPage />} />

              <Route
                path="/admin/verifications"
                element={
                  <RequireAdmin>
                    <VerificationQueuePage />
                  </RequireAdmin>
                }
              />
              <Route
                path="/admin/reports"
                element={
                  <RequireAdmin>
                    <ReportQueuePage />
                  </RequireAdmin>
                }
              />

              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </SessionProvider>
    </ToastProvider>
  );
}
