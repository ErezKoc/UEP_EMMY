import { BrowserRouter, Route, Routes } from "react-router-dom";
import RequireAuth from "./auth/RequireAuth";
import { SessionProvider } from "./auth/SessionContext";
import AppLayout from "./components/layout/AppLayout";
import { ToastProvider } from "./components/ui/toast";
import Dashboard from "./pages/Dashboard";
import Landing from "./pages/Landing";
import NotFound from "./pages/NotFound";
import AnalysisHistoryPage from "./pages/analysis/AnalysisHistoryPage";
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

/*
 * Route registry — one route per page, stub pages included, so every member's
 * area is reachable from day one. Replace the stub component inside your page
 * file; you should rarely need to touch this file.
 *
 * Ownership:
 *   Member 2 — /login /signup /profile /settings
 *   Member 3 — /pets /pets/:petId
 *   Member 4 — /analyze /analysis/history
 *   Member 5 — /community /community/new /community/:postId /vets
 */
export default function App() {
  return (
    <ToastProvider>
      <SessionProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<AppLayout />}>
              <Route path="/" element={<Landing />} />
              <Route path="/dashboard" element={<Dashboard />} />

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

              <Route path="/pets" element={<PetsPage />} />
              <Route path="/pets/:petId" element={<PetDetailPage />} />

              <Route path="/analyze" element={<AnalyzePage />} />
              <Route path="/analysis/history" element={<AnalysisHistoryPage />} />

              <Route path="/community" element={<CommunityPage />} />
              <Route path="/community/new" element={<NewPostPage />} />
              <Route path="/community/:postId" element={<PostDetailPage />} />
              <Route path="/vets" element={<VetsPage />} />

              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </SessionProvider>
    </ToastProvider>
  );
}
