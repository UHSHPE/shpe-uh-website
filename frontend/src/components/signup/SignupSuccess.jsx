import { Link } from "react-router-dom";

export default function SignupSuccess({ email }) {
  return (
    <div
      style={{
        minHeight: "calc(100vh - var(--header-height))",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background:
          "linear-gradient(135deg, #001F5B 0%, #003A70 60%, #0070C0 100%)",
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
          maxWidth: "460px",
          boxShadow: "0 20px 60px rgba(0,0,0,0.25)",
          textAlign: "center",
        }}
      >
        <h1
          style={{
            fontSize: "26px",
            fontWeight: 700,
            color: "#001F5B",
            marginBottom: "12px",
          }}
        >
          Check your email
        </h1>
        <p style={{ color: "#374151", fontSize: "15px", lineHeight: 1.6 }}>
          We sent a verification link to{" "}
          <strong style={{ color: "#001F5B" }}>{email}</strong>. Click it to
          activate your account and pay your chapter dues.
        </p>
        <p
          style={{
            color: "#6b7280",
            fontSize: "14px",
            marginTop: "16px",
            lineHeight: 1.6,
          }}
        >
          The link expires in 24 hours. Didn't get it? Check your spam folder,
          or sign up again to resend.
        </p>
        <p style={{ marginTop: "28px", fontSize: "14px" }}>
          <Link
            to="/signin"
            style={{
              color: "#0070C0",
              fontWeight: 600,
              textDecoration: "none",
            }}
          >
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
