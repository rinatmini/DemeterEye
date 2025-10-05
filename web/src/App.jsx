import {
  Routes,
  Route,
  Navigate,
  useLocation,
  Link,
  useNavigate,
} from "react-router-dom";
import AuthScreen from "./views/AuthScreen.jsx";
import FieldsList from "./views/FieldsList.jsx";
import CreateField from "./views/CreateField.jsx";
import FieldDetails from "./views/FieldDetails.jsx";
import { LogOut } from "lucide-react";

function RequireAuth({ children }) {
  const token = localStorage.getItem("token");
  const loc = useLocation();
  if (!token) return <Navigate to="/login" replace state={{ from: loc }} />;
  return children;
}

function Shell({ children }) {
  const nav = useNavigate();
  const token = localStorage.getItem("token");

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="sticky top-0 z-10 bg-white border-b">
        <div className="mx-auto max-w-6xl px-4 h-14 flex items-center justify-between">
          <Link to="/" className="inline-flex items-center gap-2 font-semibold">
            <img src="/favicon.svg" className="h-16 w-16" />
            DemeterEye
          </Link>
          {token && (
            <button
              className="text-sm inline-flex items-center gap-1 px-2 py-1 rounded-xl border hover:bg-gray-50"
              onClick={() => {
                localStorage.removeItem("token");
                nav("/login", { replace: true });
              }}
            >
              <LogOut className="h-4 w-4" /> Logout
            </button>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-4">{children}</main>
    </div>
  );
}

export default function App() {
  const token = localStorage.getItem("token");

  return (
    <Shell>
      <Routes>
        <Route
          path="/"
          element={<Navigate to={token ? "/fields" : "/login"} replace />}
        />

        <Route path="/login" element={<AuthScreen />} />

        <Route
          path="/fields"
          element={
            <RequireAuth>
              <FieldsList />
            </RequireAuth>
          }
        />
        <Route
          path="/fields/new"
          element={
            <RequireAuth>
              <CreateField />
            </RequireAuth>
          }
        />
        <Route
          path="/fields/:id"
          element={
            <RequireAuth>
              <FieldDetails />
            </RequireAuth>
          }
        />

        <Route
          path="*"
          element={<div className="p-6 text-gray-600">Not found</div>}
        />
      </Routes>
    </Shell>
  );
}
