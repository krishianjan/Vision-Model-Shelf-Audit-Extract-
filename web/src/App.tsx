import { useState } from "react";
import { isLoggedIn } from "./api";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";

export default function App() {
  const [authed, setAuthed] = useState(isLoggedIn());
  return authed
    ? <Dashboard onLogout={() => setAuthed(false)} />
    : <Login onLogin={() => setAuthed(true)} />;
}
