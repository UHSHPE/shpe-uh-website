import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useCart } from "../context/CartContext";
import { startDuesCheckout } from "../utils/dues";

// Site-wide red banner for signed-in members who haven't paid their T-Shirt
// Dues (has_paid_dues comes from /me). Fixed just below the fixed header;
// disappears the moment a dues order exists (AuthContext.refreshUser runs
// after checkout, so no reload is needed).
export default function DuesBanner() {
  const { user } = useAuth();
  const { addItem } = useCart();
  const navigate = useNavigate();

  if (!user || user.has_paid_dues) return null;

  async function handlePay() {
    const dest = await startDuesCheckout({ shirtSize: user.shirt_size, addItem });
    navigate(dest || "/shop");
  }

  return (
    <div
      role="alert"
      style={{
        position: "fixed",
        top: "var(--header-height)",
        left: 0,
        right: 0,
        zIndex: 900, // below the fixed header (1000), above page content
        background: "var(--shpe-red)",
        color: "#fff",
        padding: "8px 16px",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "12px",
        flexWrap: "wrap",
        fontFamily: "var(--font-body)",
        fontSize: "13px",
        lineHeight: 1.45,
        textAlign: "center",
        boxShadow: "0 2px 10px rgba(0,0,0,.18)",
      }}
    >
      <span>
        <strong>Pay your T-Shirt Dues to unlock your SHPE benefits</strong> — Slack
        access, National convention sponsorship, over $10,000 in scholarships, the
        MentorSHPE Program, the Resume Book shared directly with our corporate
        sponsors, and your chapter shirt.
      </span>
      <button
        onClick={handlePay}
        style={{
          flexShrink: 0,
          border: "none",
          background: "#fff",
          color: "var(--shpe-red)",
          borderRadius: "999px",
          padding: "6px 15px",
          fontSize: "12px",
          fontWeight: 800,
          cursor: "pointer",
          whiteSpace: "nowrap",
        }}
      >
        Pay dues now →
      </button>
    </div>
  );
}
