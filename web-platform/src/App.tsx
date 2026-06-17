import { useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useAtom } from "jotai";
import { userAtom, accessTokenAtom } from "./atoms";
import { authApi } from "./api/auth";
import { LoginPage } from "./pages/Login";
import { DashboardPage } from "./pages/Dashboard";
import { ChatPage } from "./pages/Chat";
import { SessionsPage } from "./pages/Sessions";
import { SettingsPage } from "./pages/Settings";
import { AppLayout } from "./components/layout/AppLayout";
import { ProtectedRoute } from "./components/auth/ProtectedRoute";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { ToastContainer } from "./components/Toast";

function AuthInitializer({ children }: { children: React.ReactNode }) {
  const [, setUser] = useAtom(userAtom);
  const [, setToken] = useAtom(accessTokenAtom);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token) {
      setToken(token);
      authApi
        .refresh(localStorage.getItem("refresh_token") || "")
        .then((data) => setUser(data.user))
        .catch(() => {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
        });
    }
  }, [setUser, setToken]);

  return <>{children}</>;
}

function App() {
  return (
    <BrowserRouter>
      <AuthInitializer>
        <ErrorBoundary>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <AppLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="chat" element={<ChatPage />} />
              <Route path="chat/:sessionId" element={<ChatPage />} />
              <Route path="sessions" element={<SessionsPage />} />
              <Route path="settings" element={<SettingsPage />} />
            </Route>
          </Routes>
          <ToastContainer />
        </ErrorBoundary>
      </AuthInitializer>
    </BrowserRouter>
  );
}

export default App;
