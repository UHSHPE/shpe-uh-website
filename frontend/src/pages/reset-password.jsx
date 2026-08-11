import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { confirmPasswordReset } from "../api/api";
import useDocumentTitle from "../hooks/useDocumentTitle";

export default function ResetPassword() {
  useDocumentTitle("Reset Password");
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");

    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    if (password.length < 10) {
      setError("Password must be at least 10 characters.");
      return;
    }

    setLoading(true);
    try {
      await confirmPasswordReset(token, password);
      navigate("/signin", {
        replace: true,
        state: { message: "Password reset. Sign in with your new password." },
      });
    } catch (err) {
      if (err.response?.status === 400) {
        setError("This reset link is invalid or has expired. Request a new one.");
      } else if (err.response?.status === 422) {
        // Surface the server's reason. detail is pydantic's array for schema
        // failures (length) but a plain string for the HIBP breach rejection.
        const detail = err.response?.data?.detail;
        const msg = Array.isArray(detail)
          ? detail[0]?.msg
          : typeof detail === "string"
            ? detail
            : null;
        setError(
          msg
            ? msg.replace(/^Value error, /, "")
            : "Password must be at least 10 characters."
        );
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
          Reset password
        </h1>

        {!token ? (
          <>
            <p style={{ color: "#374151", fontSize: "15px", marginTop: "16px", lineHeight: 1.6 }}>
              This reset link is missing its token. Use the link from your email,
              or request a new one.
            </p>
            <p style={{ textAlign: "center", marginTop: "24px", fontSize: "14px", color: "#6b7280" }}>
              <Link to="/forgot-password" style={{ color: "#0070C0", fontWeight: 600, textDecoration: "none" }}>
                Request a new link
              </Link>
            </p>
          </>
        ) : (
          <>
            <p style={{ color: "#6b7280", fontSize: "15px", marginBottom: "32px" }}>
              Choose a new password for your SHPE UH account
            </p>

            <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                <label style={{ fontSize: "14px", fontWeight: 600, color: "#374151" }}>
                  New password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={10}
                  placeholder="••••••••"
                  style={inputStyle}
                />
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                <label style={{ fontSize: "14px", fontWeight: 600, color: "#374151" }}>
                  Confirm new password
                </label>
                <input
                  type="password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  required
                  minLength={10}
                  placeholder="••••••••"
                  style={inputStyle}
                />
              </div>

              {error && (
                <p style={{ color: "#D33A02", fontSize: "14px", fontWeight: 500, margin: 0 }}>
                  {error}
                </p>
              )}

              <button
                type="submit"
                className="primaryBtn"
                disabled={loading}
                style={{ width: "100%", padding: "12px", fontSize: "15px", marginTop: "4px", opacity: loading ? 0.7 : 1 }}
              >
                {loading ? "Resetting…" : "Reset password"}
              </button>
            </form>

            <p style={{ textAlign: "center", marginTop: "24px", fontSize: "14px", color: "#6b7280" }}>
              <Link to="/signin" style={{ color: "#0070C0", fontWeight: 600, textDecoration: "none" }}>
                Back to sign in
              </Link>
            </p>
          </>
        )}
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
