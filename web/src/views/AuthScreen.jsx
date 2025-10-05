import { useState } from "react";
import { Loader2 } from "lucide-react";
import { apiFetch } from "../lib/api.js";
import { useLocation, useNavigate } from "react-router-dom";

export default function AuthScreen() {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const nav = useNavigate();
  const loc = useLocation();
  const redirectTo = loc.state?.from?.pathname || "/fields";

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      if (mode === "register") {
        await apiFetch("/api/auth/register", {
          method: "POST",
          body: { username, email, password },
        });
      }
      const res = await apiFetch("/api/auth/login", {
        method: "POST",
        body: { email, password },
      });
      localStorage.setItem("token", res.token);
      nav(redirectTo, { replace: true });
    } catch (e) {
      console.log(e);
      if (e.status === 401) {
        setErr("Incorrect email or password");
      } else {
        setErr(e.message || "An unexpected error occurred");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[70vh] grid place-items-center p-4">
      <div className="w-full max-w-md rounded-2xl border bg-white p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <img src="/favicon.svg" className="h-16 w-16" />
          <h1 className="text-xl font-semibold">DemeterEye</h1>
        </div>
        <p className="text-gray-600 mb-4">
          {mode === "login" ? "Sign in to your account" : "Create your account"}
        </p>
        <form onSubmit={submit} className="space-y-3">
          {mode === "register" && (
            <input
              className="w-full rounded-xl border px-3 py-2"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          )}
          <input
            className="w-full rounded-xl border px-3 py-2"
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <input
            className="w-full rounded-xl border px-3 py-2"
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {err && <div className="text-sm text-red-600">{err}</div>}
          <button
            disabled={loading}
            className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-600 text-white py-2 hover:bg-emerald-700"
          >
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            {mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>
        <div className="mt-4 text-sm text-gray-600">
          {mode === "login" ? (
            <>
              No account?{" "}
              <button
                className="text-emerald-600 hover:underline"
                onClick={() => setMode("register")}
              >
                Register
              </button>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <button
                className="text-emerald-600 hover:underline"
                onClick={() => setMode("login")}
              >
                Sign in
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
