import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { loginUser } from "../api/api";
import { useAuth } from "../context/AuthContext";

export default function SignIn() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  // Shown after a successful password reset (set by /reset-password)
  const successMessage = location.state?.message;

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await loginUser(email, password);
      login(res.data.access_token);
      const destination = location.state?.from?.pathname ?? "/dashboard";
      navigate(destination, { replace: true });
    } catch (err) {
      if (err.response?.status === 401) {
        setError("Incorrect email or password.");
      } else if (err.response?.status === 429) {
        setError("Too many attempts. Please wait a minute and try again.");
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(135deg, #001F5B 0%, #003A70 60%, #0070C0 100%)",
        padding: "24px 16px",
        fontFamily: "Work Sans, sans-serif",
      }}
    >
      <div
        style={{
          background: "#fff",
          borderRadius: "16px",
          padding: "48px 40px",
          width: "100%",
          maxWidth: "420px",
          boxShadow: "0 20px 60px rgba(0,0,0,0.25)",
        }}
      >
        <h1
          style={{
            fontSize: "28px",
            fontWeight: 700,
            color: "#001F5B",
            marginBottom: "6px",
            fontFamily: "Work Sans, sans-serif",
          }}
        >
          Welcome back
        </h1>
        <p style={{ color: "#6b7280", fontSize: "15px", marginBottom: "32px" }}>
          Sign in to your SHPE UH account
        </p>

        {successMessage && (
          <p style={{ color: "#15803d", fontSize: "14px", fontWeight: 500, marginBottom: "18px" }}>
            {successMessage}
          </p>
        )}

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <label style={{ fontSize: "14px", fontWeight: 600, color: "#374151" }}>
              CougarNet Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="username@cougarnet.uh.edu"
              style={inputStyle}
            />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <label style={{ fontSize: "14px", fontWeight: 600, color: "#374151" }}>
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="••••••••"
              style={inputStyle}
            />
          </div>

          {error && (
            <p style={{ color: "#D33A02", fontSize: "14px", fontWeight: 500, margin: 0 }}>
              {error}
            </p>
          )}

          <p style={{ textAlign: "right", fontSize: "14px", margin: 0 }}>
            <Link to="/forgot-password" style={{ color: "#0070C0", fontWeight: 600, textDecoration: "none" }}>
              Forgot password?
            </Link>
          </p>

          <button
            type="submit"
            className="primaryBtn"
            disabled={loading}
            style={{ width: "100%", padding: "12px", fontSize: "15px", marginTop: "4px", opacity: loading ? 0.7 : 1 }}
          >
            {loading ? "Signing in…" : "Sign In"}
          </button>
        </form>

        <p style={{ textAlign: "center", marginTop: "24px", fontSize: "14px", color: "#6b7280" }}>
          Don't have an account?{" "}
          <Link to="/signup" style={{ color: "#0070C0", fontWeight: 600, textDecoration: "none" }}>
            Sign up
          </Link>
        </p>
      </div>
    </div>
  );
}

const inputStyle = {
  padding: "10px 14px",
  borderRadius: "8px",
  border: "1.5px solid #d1d5db",
  fontSize: "15px",
  outline: "none",
  fontFamily: "Work Sans, sans-serif",
  transition: "border-color 0.2s",
};
