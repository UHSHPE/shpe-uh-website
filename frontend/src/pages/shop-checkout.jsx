import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createShopOrder } from "../api/api";
import { CardIcon, CheckIcon, BoxIcon } from "../components/shopIcons";
import { useAuth } from "../context/AuthContext";
import { useCart } from "../context/CartContext";
import { formatCents } from "../utils/shop";

// Two-step checkout: contact details, then a SIMULATED payment step (a
// placeholder for the future Square integration — the flow stays the same).
export default function ShopCheckout() {
  const { user } = useAuth();
  const { lines, subtotalCents, clearCart } = useCart();
  const navigate = useNavigate();

  const [step, setStep] = useState("contact"); // 'contact' | 'payment'
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [prefilled, setPrefilled] = useState(false);
  const [paying, setPaying] = useState(false);
  const [error, setError] = useState(null);

  // Prefill contact info once the signed-in user's profile arrives (it loads
  // async). Render-phase adjustment instead of an effect — see "You Might Not
  // Need an Effect" (React docs).
  if (user && !prefilled) {
    setPrefilled(true);
    setName((v) => v || `${user.first_name} ${user.last_name}`);
    setEmail((v) => v || user.personal_email || user.cougarnet_email || "");
    setPhone((v) => v || user.phone_num || "");
  }

  const canContinue = name.trim() !== "" && email.trim() !== "";

  async function handlePay() {
    setPaying(true);
    setError(null);
    const payload = {
      buyer_name: name.trim(),
      buyer_email: email.trim(),
      buyer_phone: phone.trim(),
      items: lines.map((l) => ({
        product_id: l.productId,
        size: l.size,
        quantity: l.qty,
      })),
    };
    // Simulated processing delay so the payment step reads as a real charge.
    await new Promise((resolve) => setTimeout(resolve, 1300));
    try {
      const res = await createShopOrder(payload);
      const order = res.data;
      // Let the confirmation page (and later revisits) look the order up.
      sessionStorage.setItem(
        "shpe_last_order",
        JSON.stringify({ code: order.order_code, email: order.buyer_email })
      );
      clearCart();
      navigate(`/shop/order/${order.order_code}`, { state: { order } });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(
        err.response?.status === 429
          ? "Too many orders placed from this connection — try again in a minute."
          : typeof detail === "string"
            ? detail
            : "Something went wrong placing the order. Please try again."
      );
      setPaying(false);
    }
  }

  if (lines.length === 0) {
    return (
      <div style={{ maxWidth: "640px", margin: "0 auto", padding: "140px 20px 72px", textAlign: "center", fontFamily: "var(--font-body)" }}>
        <p style={{ margin: "0 0 6px", fontSize: "18px", fontWeight: 700, color: "var(--ink)" }}>Your cart is empty</p>
        <p style={{ margin: "0 0 18px", color: "var(--muted)", fontSize: "14px" }}>Add something from the shop to check out.</p>
        <Link to="/shop" className="primaryBtn" style={{ display: "inline-block", padding: "11px 22px", fontSize: "14px" }}>
          Browse the shop
        </Link>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: "960px", margin: "0 auto", padding: "108px 20px 72px", fontFamily: "var(--font-body)" }}>
      {/* Title + step indicator */}
      <div style={{ display: "flex", alignItems: "center", gap: "14px", marginBottom: "24px", flexWrap: "wrap" }}>
        <h1 style={{ margin: 0, fontSize: "28px", fontWeight: 800, color: "var(--shpe-blue)" }}>Checkout</h1>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginLeft: "auto" }}>
          {step === "contact" ? (
            <StepChip n="1" label="Contact" state="active" />
          ) : (
            <StepChip label="Contact" state="done" />
          )}
          <span style={{ width: "22px", height: "1px", background: "var(--border-strong)" }} />
          <StepChip n="2" label="Payment" state={step === "payment" ? "active" : "todo"} />
        </div>
      </div>

      <div className="checkoutGrid">
        <div>
          {step === "contact" && (
            <div style={cardStyle}>
              <h2 style={{ margin: "0 0 4px", fontSize: "18px", fontWeight: 700, color: "var(--shpe-blue)" }}>
                Contact details
              </h2>
              <p style={{ margin: "0 0 18px", fontSize: "13px", color: "var(--muted)" }}>
                We'll email pickup updates to this address.
              </p>

              {!user && (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: "12px",
                    background: "var(--surface-tint)",
                    border: "1px solid var(--info-border)",
                    borderRadius: "12px",
                    padding: "12px 16px",
                    marginBottom: "20px",
                  }}
                >
                  <span style={{ fontSize: "13px", color: "var(--shpe-navy-700)", fontWeight: 500 }}>
                    Have an account? <strong>Log in for faster checkout</strong> — we'll prefill this for you.
                  </span>
                  <button
                    onClick={() => navigate("/signin", { state: { from: "/shop/checkout" } })}
                    style={{
                      borderRadius: "999px",
                      padding: "7px 16px",
                      fontSize: "13px",
                      fontWeight: 700,
                      border: "1px solid var(--shpe-blue)",
                      background: "#fff",
                      color: "var(--shpe-blue)",
                      cursor: "pointer",
                      whiteSpace: "nowrap",
                    }}
                  >
                    Log in
                  </button>
                </div>
              )}
              {user && (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "9px",
                    background: "var(--success-bg)",
                    border: "1px solid var(--success-border)",
                    borderRadius: "12px",
                    padding: "11px 16px",
                    marginBottom: "20px",
                  }}
                >
                  <CheckIcon size={16} stroke="var(--success-deep)" strokeWidth={2.2} />
                  <span style={{ fontSize: "13px", color: "var(--success-deep)", fontWeight: 600 }}>
                    Prefilled from your account · saved to your order history
                  </span>
                </div>
              )}

              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                <label style={labelStyle}>
                  Full name
                  <input className="shopInput" value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" />
                </label>
                <label style={labelStyle}>
                  Email
                  <input className="shopInput" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@cougarnet.uh.edu" />
                </label>
                <label style={labelStyle}>
                  <span>
                    Phone <span style={{ color: "var(--muted-soft)", fontWeight: 500 }}>(optional)</span>
                  </span>
                  <input className="shopInput" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="(713) 555-0123" />
                </label>
              </div>

              <button
                className="primaryBtn"
                disabled={!canContinue}
                onClick={() => setStep("payment")}
                style={{ marginTop: "22px", width: "100%", padding: "13px 20px", fontSize: "15px" }}
              >
                Continue to payment
              </button>
            </div>
          )}

          {step === "payment" && (
            <div style={cardStyle}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", marginBottom: "6px" }}>
                <h2 style={{ margin: 0, fontSize: "18px", fontWeight: 700, color: "var(--shpe-blue)" }}>Payment</h2>
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    fontSize: "11px",
                    fontWeight: 700,
                    color: "var(--status-ready-text)",
                    background: "var(--status-ready-bg)",
                    border: "1px solid var(--status-ready-border)",
                    borderRadius: "999px",
                    padding: "4px 10px",
                  }}
                >
                  SIMULATED · no real charge
                </span>
              </div>
              <p style={{ margin: "0 0 18px", fontSize: "13px", color: "var(--muted)" }}>
                This is a placeholder checkout. It will be replaced by Square — the flow and buttons stay the same.
              </p>

              {/* Read-only demo card block */}
              <div
                style={{
                  border: "1px solid var(--border)",
                  borderRadius: "12px",
                  padding: "16px",
                  background: "var(--surface-muted)",
                  display: "flex",
                  flexDirection: "column",
                  gap: "14px",
                  opacity: 0.92,
                }}
              >
                <div>
                  <span style={demoLabel}>Card number</span>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", background: "#fff", border: "1px solid var(--border-strong)", borderRadius: "10px", padding: "11px 13px" }}>
                    <CardIcon size={20} stroke="var(--muted-soft)" strokeWidth={1.7} />
                    <span style={{ fontSize: "14px", color: "var(--muted-soft)", letterSpacing: ".04em" }}>
                      4242 4242 4242 4242
                    </span>
                    <span style={{ marginLeft: "auto", fontSize: "11px", color: "#C7CDD6" }}>DEMO</span>
                  </div>
                </div>
                <div style={{ display: "flex", gap: "12px" }}>
                  <div style={{ flex: 1 }}>
                    <span style={demoLabel}>Expiry</span>
                    <div style={demoField}>12 / 28</div>
                  </div>
                  <div style={{ flex: 1 }}>
                    <span style={demoLabel}>CVC</span>
                    <div style={demoField}>•••</div>
                  </div>
                </div>
              </div>

              {error && (
                <p style={{ margin: "14px 0 0", fontSize: "13px", fontWeight: 600, color: "var(--shpe-red)" }}>{error}</p>
              )}

              <button
                className="primaryBtn"
                onClick={handlePay}
                disabled={paying}
                style={{
                  marginTop: "20px",
                  width: "100%",
                  padding: "14px 20px",
                  fontSize: "15px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "9px",
                  cursor: paying ? "wait" : "pointer",
                }}
              >
                {paying ? (
                  <>
                    <span
                      style={{
                        width: "17px",
                        height: "17px",
                        border: "2.5px solid rgba(255,255,255,.4)",
                        borderTopColor: "#fff",
                        borderRadius: "999px",
                        display: "inline-block",
                        animation: "shopSpin .7s linear infinite",
                      }}
                    />
                    Processing…
                  </>
                ) : (
                  <>
                    <CardIcon size={17} />
                    Pay {formatCents(subtotalCents)}
                  </>
                )}
              </button>
              <button
                onClick={() => setStep("contact")}
                disabled={paying}
                style={{
                  marginTop: "10px",
                  width: "100%",
                  background: "transparent",
                  border: "none",
                  color: "var(--muted)",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: "pointer",
                  padding: "6px",
                }}
              >
                ← Back to contact
              </button>
            </div>
          )}
        </div>

        {/* Order summary */}
        <div style={{ ...cardStyle, padding: "22px 24px" }}>
          <h3 style={{ margin: "0 0 16px", fontSize: "15px", fontWeight: 700, color: "var(--ink)" }}>Order summary</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {lines.map((l) => (
              <div key={`${l.productId}|${l.size ?? ""}`} style={{ display: "flex", justifyContent: "space-between", gap: "12px", fontSize: "14px" }}>
                <span style={{ color: "var(--ink-soft)" }}>
                  {l.qty}× {l.name}
                  {l.size ? ` (${l.size})` : ""}
                </span>
                <span style={{ color: "var(--ink)", fontWeight: 700, whiteSpace: "nowrap" }}>
                  {formatCents(l.priceCents * l.qty)}
                </span>
              </div>
            ))}
          </div>
          <div style={{ height: "1px", background: "var(--border)", margin: "16px 0" }} />
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <span style={{ fontSize: "15px", fontWeight: 700, color: "var(--ink)" }}>Total</span>
            <span style={{ fontSize: "22px", fontWeight: 800, color: "var(--shpe-blue)" }}>
              {formatCents(subtotalCents)}
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "flex-start", gap: "9px", marginTop: "16px", paddingTop: "16px", borderTop: "1px dashed var(--border)" }}>
            <BoxIcon size={16} stroke="var(--muted)" style={{ flexShrink: 0, marginTop: "1px" }} />
            <p style={{ margin: 0, fontSize: "12px", color: "var(--muted)", lineHeight: 1.5 }}>
              Pay now, pick up at a chapter event once marked ready.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function StepChip({ n, label, state }) {
  if (state === "done") {
    return (
      <span style={{ display: "flex", alignItems: "center", gap: "7px", fontSize: "13px", fontWeight: 700, color: "var(--success-deep)" }}>
        <span style={{ width: "22px", height: "22px", borderRadius: "999px", background: "var(--success-bg)", border: "1px solid var(--success-border)", color: "var(--success-deep)", display: "grid", placeItems: "center" }}>
          <CheckIcon size={12} strokeWidth={3} />
        </span>
        {label}
      </span>
    );
  }
  const active = state === "active";
  return (
    <span style={{ display: "flex", alignItems: "center", gap: "7px", fontSize: "13px", fontWeight: 700, color: active ? "var(--shpe-blue)" : "var(--muted-soft)" }}>
      <span
        style={{
          width: "22px",
          height: "22px",
          borderRadius: "999px",
          background: active ? "var(--shpe-blue)" : "var(--surface-soft)",
          color: active ? "#fff" : "var(--muted-soft)",
          display: "grid",
          placeItems: "center",
          fontSize: "12px",
        }}
      >
        {n}
      </span>
      {label}
    </span>
  );
}

const cardStyle = {
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-xl)",
  background: "#fff",
  boxShadow: "var(--shadow-card)",
  padding: "24px 26px",
};

const labelStyle = {
  display: "flex",
  flexDirection: "column",
  gap: "6px",
  fontSize: "12px",
  fontWeight: 700,
  color: "var(--ink-soft)",
};

const demoLabel = {
  display: "block",
  fontSize: "12px",
  fontWeight: 700,
  color: "var(--ink-soft)",
  marginBottom: "6px",
};

const demoField = {
  background: "#fff",
  border: "1px solid var(--border-strong)",
  borderRadius: "10px",
  padding: "11px 13px",
  fontSize: "14px",
  color: "var(--muted-soft)",
};
