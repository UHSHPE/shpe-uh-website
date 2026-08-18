import { useState, useEffect, useRef } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { verifyEmail, getMe } from "../api/api";
import { useAuth } from "../context/AuthContext";
import { useCart } from "../context/CartContext";
import { startDuesCheckout } from "../utils/dues";
import useDocumentTitle from "../hooks/useDocumentTitle";

export default function VerifyEmail() {
  useDocumentTitle("Verify Email");
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const { login } = useAuth();
  const { addItem, showToast } = useCart();

  // "verifying" | "already" | "error" — success navigates away, so there is no
  // success state. "already" is the 409 from /verify-email: the token was
  // spent but the account really is verified, which is the ordinary outcome
  // when a mail scanner (Microsoft Defender Safe Links, on cougarnet.uh.edu)
  // opened the link first, or the member refreshed this page.
  const [status, setStatus] = useState(token ? "verifying" : "error");
  // Verification issues a login token and must run exactly once, even under
  // React 18 StrictMode's double-invoke, or the single-use token 400s itself.
  const ran = useRef(false);

  useEffect(() => {
    if (!token || ran.current) return;
    ran.current = true;

    verifyEmail(token)
      .then(async (res) => {
        const jwt = res.data.access_token;
        login(jwt);

        // New members are routed into dues checkout, same as the old signup
        // flow — now that they're verified and signed in. Best-effort: any
        // failure just lands them on the home page.
        try {
          const me = await getMe(jwt);
          const dest = await startDuesCheckout({ shirtSize: me.data.shirt_size, addItem });
          if (dest) {
            showToast(
              dest === "/shop/checkout"
                ? "Email verified! One last step — pay your chapter dues."
                : "Email verified! Pick a shirt size to pay your dues."
            );
            navigate(dest, { replace: true });
            return;
          }
        } catch {
          // fall through to the default landing
        }
        navigate("/", { replace: true });
      })
      .catch((err) =>
        setStatus(err.response?.status === 409 ? "already" : "error")
      );
  }, [token, login, addItem, showToast, navigate]);

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
          maxWidth: "440px",
          boxShadow: "0 20px 60px rgba(0,0,0,0.25)",
          textAlign: "center",
        }}
      >
        {status === "verifying" && (
          <>
            <h1 style={{ fontSize: "26px", fontWeight: 700, color: "#001F5B", marginBottom: "12px" }}>
              Verifying your email…
            </h1>
            <p style={{ color: "#6b7280", fontSize: "15px" }}>Hang tight for a moment.</p>
          </>
        )}

        {status === "already" && (
          <>
            <h1 style={{ fontSize: "26px", fontWeight: 700, color: "#001F5B", marginBottom: "12px" }}>
              You&rsquo;re all set
            </h1>
            <p style={{ color: "#374151", fontSize: "15px", lineHeight: 1.6 }}>
              This email is already verified — your account is ready to use. Sign
              in to continue.
            </p>
            <p style={{ marginTop: "28px", fontSize: "14px" }}>
              <Link to="/signin" style={{ color: "#0070C0", fontWeight: 600, textDecoration: "none" }}>
                Go to sign in
              </Link>
            </p>
          </>
        )}

        {status === "error" && (
          <>
            <h1 style={{ fontSize: "26px", fontWeight: 700, color: "#001F5B", marginBottom: "12px" }}>
              Verification link invalid
            </h1>
            {/* Verification links are single-use and are replaced every time
                signup is re-submitted, so "already used" and "superseded by a
                newer email" are both far more common than a genuinely broken
                link. Say so, and offer sign-in first — the account may well
                already be verified. */}
            <p style={{ color: "#374151", fontSize: "15px", lineHeight: 1.6 }}>
              This link is missing, expired, or has already been used. If you
              requested more than one email, only the most recent link works —
              try that one first, or sign in to check whether your account is
              already verified.
            </p>
            <p style={{ marginTop: "28px", fontSize: "14px" }}>
              <Link to="/signin" style={{ color: "#0070C0", fontWeight: 600, textDecoration: "none" }}>
                Go to sign in
              </Link>
              <span style={{ color: "#9ca3af", margin: "0 10px" }}>·</span>
              <Link to="/signup" style={{ color: "#0070C0", fontWeight: 600, textDecoration: "none" }}>
                Back to sign up
              </Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
