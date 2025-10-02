import React, { useEffect, useState } from "react";
import Topbar from "./components/Topbar.jsx";
import FieldsList from "./views/FieldsList.jsx";
import CreateField from "./views/CreateField.jsx";
import FieldDetails from "./views/FieldDetails.jsx";
import AuthScreen from "./views/AuthScreen.jsx";
import { getToken, setToken as saveToken } from "./lib/auth.js";

export default function App() {
  const [token, setTok] = useState(getToken());
  const [view, setView] = useState("list"); // list | create | details
  const [selected, setSelected] = useState(null);

  useEffect(() => {}, [token]);

  const handleAuthed = (t) => {
    saveToken(t);
    setTok(t); // state -> AuthScreen
    setView("list");
  };

  if (!token) return <AuthScreen onAuthed={handleAuthed} />;

  const logout = () => {
    saveToken(null);
    setTok(null);
  };

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <Topbar onLogout={logout} />
      <main className="mx-auto max-w-6xl p-4 md:p-6">
        {view === "list" && (
          <FieldsList
            token={token}
            onCreate={() => setView("create")}
            onOpen={(f) => {
              setSelected(f);
              setView("details");
            }}
          />
        )}
        {view === "create" && (
          <CreateField
            token={token}
            onCancel={() => setView("list")}
            onCreated={(f) => {
              setSelected(f);
              setView("details");
            }}
          />
        )}
        {view === "details" && selected && (
          <FieldDetails
            token={token}
            field={selected}
            onBack={() => setView("list")}
            onUpdated={setSelected}
          />
        )}
      </main>
    </div>
  );
}
