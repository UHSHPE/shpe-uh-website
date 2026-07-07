import { useState } from "react";
import { Link } from "react-router-dom";
import { requestPasswordReset } from "../api/api";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    try {
      await requestPasswordReset(email);
    } catch {
      // Swallow errors — never reveal whether the email exists
    } finally {
      setSubmitted(true);
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
          Forgot password
        </h1>

        {submitted ? (
          <>
            <p style={{ color: "#374151", fontSize: "15px", marginTop: "16px", lineHeight: 1.6 }}>
              If an account with that email exists, a reset link has been sent.
              Check your CougarNet inbox — the link expires in 1 hour.
            </p>
            <p style={{ textAlign: "center", marginTop: "24px", fontSize: "14px", color: "#6b7280" }}>
              <Link to="/signin" style={{ color: "#0070C0", fontWeight: 600, textDecoration: "none" }}>
                Back to sign in
              </Link>
            </p>
          </>
        ) : (
          <>
            <p style={{ color: "#6b7280", fontSize: "15px", marginBottom: "32px" }}>
              Enter your CougarNet email and we'll send you a reset link
            </p>

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

              <button
                type="submit"
                className="primaryBtn"
                disabled={loading}
                style={{ width: "100%", padding: "12px", fontSize: "15px", marginTop: "4px", opacity: loading ? 0.7 : 1 }}
              >
                {loading ? "Sending…" : "Send reset link"}
              </button>
            </form>

            <p style={{ textAlign: "center", marginTop: "24px", fontSize: "14px", color: "#6b7280" }}>
              Remembered it?{" "}
              <Link to="/signin" style={{ color: "#0070C0", fontWeight: 600, textDecoration: "none" }}>
                Sign in
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
