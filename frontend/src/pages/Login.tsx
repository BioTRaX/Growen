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
      await login(u.trim(), p);
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
  navigate("/guest");
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
        background: "var(--bg)",
        color: "var(--text)",
        padding: "1rem",
      }}
    >
      <div className="login-panel">
        <h1 className="fs-xl fw-600 mb-4 text-center">Growen</h1>

        <form onSubmit={submit}>
          <input
            className="input w-100 mb-3"
            placeholder="Usuario o email"
            value={u}
            onChange={(e) => setU(e.target.value)}
            autoFocus
          />
          <div className="row">
            <input
              className="input w-100"
              placeholder="Contraseña"
              type="password"
              value={p}
              onChange={(e) => setP(e.target.value)}
            />
            <button type="submit" disabled={loading} className="btn-primary">
              {loading ? "..." : "Ingresar"}
            </button>
          </div>
        </form>

  <button type="button" onClick={loginGuest} disabled={loading} className="mt-3 btn-secondary w-100" aria-label="Ingresar como invitado">
          Ingresar como invitado
        </button>

        {err && (
          <div className="mt-3 text-sm" style={{ color: "#fca5a5" }}>
            {err}
          </div>
        )}
      </div>
    </div>
  );
}
