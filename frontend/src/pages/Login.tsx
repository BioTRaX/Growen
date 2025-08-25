import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Login() {
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { login, loginAsGuest } = useAuth();
  const navigate = useNavigate();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      await login(u, p);
      navigate("/");
    } catch (e: any) {
      const status = e?.response?.status;
      setErr(status === 401 ? "Usuario o contraseña inválidos" : "Error del servidor");
    } finally {
      setLoading(false);
    }
  };

  const loginGuest = async () => {
    setErr(null);
    setLoading(true);
    try {
      await loginAsGuest();
      navigate("/");
    } catch (e: any) {
      setErr("Error del servidor");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--bg, #0f1115)",
        color: "#fff",
      }}
    >
      <div className="w-full max-w-sm rounded-2xl p-6 bg-[#1a1d24] shadow-lg border border-[#2a2f3a]">
        <h1 className="text-xl font-semibold mb-4 text-center">Growen</h1>

        <form onSubmit={submit} className="space-y-3">
          <input
            className="w-full rounded-md bg-[#0f1115] border border-[#2a2f3a] px-3 py-2 outline-none focus:border-violet-500"
            placeholder="Usuario o email"
            value={u}
            onChange={(e) => setU(e.target.value)}
            autoFocus
          />
          <div className="flex gap-2">
            <input
              className="flex-1 rounded-md bg-[#0f1115] border border-[#2a2f3a] px-3 py-2 outline-none focus:border-violet-500"
              placeholder="Contraseña"
              type="password"
              value={p}
              onChange={(e) => setP(e.target.value)}
            />
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 rounded-md bg-violet-600 hover:bg-violet-500 disabled:opacity-60"
            >
              {loading ? "..." : "Ingresar"}
            </button>
          </div>
        </form>

        <button
          onClick={loginGuest}
          disabled={loading}
          className="mt-3 w-full text-left text-sm underline underline-offset-4 decoration-dotted hover:text-violet-400 disabled:opacity-60"
        >
          Ingresar como invitado
        </button>

        {err && (
          <div className="mt-3 text-sm text-red-400 bg-red-950/30 border border-red-800/40 rounded-md px-3 py-2">
            {err}
          </div>
        )}
      </div>
    </div>
  );
}
