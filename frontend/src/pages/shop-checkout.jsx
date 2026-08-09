import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createShopOrder } from "../api/api";
import { CardIcon, CheckIcon, BoxIcon } from "../components/shopIcons";
import { useAuth } from "../context/AuthContext";
import { useCart } from "../context/CartContext";
import { formatCents } from "../utils/shop";

// Two-step checkout: contact details, then payment. With VITE_SQUARE_* set,
// the payment step renders Square's secure card element (Web Payments SDK)
// and the backend charges for real; without it the step stays SIMULATED —
// matching the backend's no-SQUARE_* dev mode.
const SQUARE_APP_ID = import.meta.env.VITE_SQUARE_APP_ID;
const SQUARE_LOCATION_ID = import.meta.env.VITE_SQUARE_LOCATION_ID;
const SQUARE_CONFIGURED = Boolean(SQUARE_APP_ID && SQUARE_LOCATION_ID);
// square.js must load from Square's CDN (it serves the secure card iframe) —
// this is the one sanctioned non-api.js external script. Sandbox app ids
// start with "sandbox-", which picks the sandbox build.
const SQUARE_SDK_URL = SQUARE_APP_ID?.startsWith("sandbox-")
  ? "https://sandbox.web.squarecdn.com/v1/square.js"
  : "https://web.squarecdn.com/v1/square.js";

// destroy() rejects if an element is already gone (e.g. StrictMode's dev
// double-run) — swallow that, it just means there's nothing to clean up.
function safeDestroy(method) {
  try {
    method?.destroy();
  } catch {
    /* already destroyed */
  }
}

let squareSdkPromise = null;
function loadSquareSdk() {
  if (!squareSdkPromise) {
    squareSdkPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = SQUARE_SDK_URL;
      script.onload = resolve;
      script.onerror = () => {
        squareSdkPromise = null; // allow a retry on the next attempt
        reject(new Error("square.js failed to load"));
      };
      document.head.appendChild(script);
    });
  }
  return squareSdkPromise;
}
export default function ShopCheckout() {
  const { user, refreshUser } = useAuth();
  const { lines, subtotalCents, clearCart } = useCart();
  const navigate = useNavigate();

  const [step, setStep] = useState("contact"); // 'contact' | 'payment'
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [prefilled, setPrefilled] = useState(false);
  const [paying, setPaying] = useState(false);
  const [error, setError] = useState(null);
  const cardRef = useRef(null); // live Square card element (configured mode)
  const [cardReady, setCardReady] = useState(false);
  // Wallets ride the same tokenize → payment_token flow as the card. Each is
  // null when the device/browser/domain doesn't support it (its button hides).
  const [applePayMethod, setApplePayMethod] = useState(null);
  const [googlePayMethod, setGooglePayMethod] = useState(null);

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

  // Mount Square's card element while the payment step is showing. Cleanup
  // destroys it (and guards React StrictMode's dev double-run).
  useEffect(() => {
    if (!SQUARE_CONFIGURED || step !== "payment") return undefined;
    let cancelled = false;
    let cardInstance = null;
    let applePayInstance = null;
    let googlePayInstance = null;

    // The wallet sheet shows this amount; the backend still charges its own
    // recomputed total (they match — both come from the catalog prices).
    const buildPaymentRequest = (payments) =>
      payments.paymentRequest({
        countryCode: "US",
        currencyCode: "USD",
        total: { amount: (subtotalCents / 100).toFixed(2), label: "SHPE UH Shop" },
      });

    (async () => {
      try {
        if (!window.Square) await loadSquareSdk();
        if (cancelled) return;
        const payments = window.Square.payments(SQUARE_APP_ID, SQUARE_LOCATION_ID);
        const card = await payments.card();
        if (cancelled) return void safeDestroy(card);
        await card.attach("#square-card");
        if (cancelled) return void safeDestroy(card);
        cardInstance = card;
        cardRef.current = card;
        setCardReady(true);

        // Wallets are best-effort: each init throws when unsupported (Apple
        // Pay in sandbox / non-Safari / unregistered domain; Google Pay in
        // unsupported browsers) — the button just stays hidden.
        try {
          const applePay = await payments.applePay(buildPaymentRequest(payments));
          if (cancelled) return void safeDestroy(applePay);
          applePayInstance = applePay;
          setApplePayMethod(applePay);
        } catch {
          /* Apple Pay unavailable here */
        }
        try {
          const googlePay = await payments.googlePay(buildPaymentRequest(payments));
          await googlePay.attach("#google-pay-button", { buttonSizeMode: "fill" });
          if (cancelled) return void safeDestroy(googlePay);
          googlePayInstance = googlePay;
          setGooglePayMethod(googlePay);
        } catch {
          /* Google Pay unavailable here */
        }
      } catch {
        if (!cancelled) {
          setError("Couldn't load the secure payment form. Refresh the page and try again.");
        }
      }
    })();
    return () => {
      cancelled = true;
      setCardReady(false);
      setApplePayMethod(null);
      setGooglePayMethod(null);
      cardRef.current = null;
      safeDestroy(cardInstance);
      safeDestroy(applePayInstance);
      safeDestroy(googlePayInstance);
    };
  }, [step, subtotalCents]);

  async function handlePay(walletMethod = null) {
    if (paying) return;
    setPaying(true);
    setError(null);
    let paymentToken = null;
    if (SQUARE_CONFIGURED) {
      // Card data lives in Square's iframe (or the wallet's payment sheet) —
      // tokenize() swaps it for a one-time token; only that token ever
      // reaches our backend.
      try {
        const method = walletMethod || cardRef.current;
        const result = await method.tokenize();
        if (result.status !== "OK") {
          // "Cancel" = the buyer closed the wallet sheet — not an error.
          if (result.status !== "Cancel") {
            setError(result.errors?.[0]?.message || "Check your card details and try again.");
          }
          setPaying(false);
          return;
        }
        paymentToken = result.token;
      } catch {
        setError("Check your card details and try again.");
        setPaying(false);
        return;
      }
    } else {
      // Simulated processing delay so the dev-mode step reads as a real charge.
      await new Promise((resolve) => setTimeout(resolve, 1300));
    }
    const payload = {
      buyer_name: name.trim(),
      buyer_email: email.trim(),
      buyer_phone: phone.trim(),
      payment_token: paymentToken,
      items: lines.map((l) => ({
        product_id: l.productId,
        size: l.size,
        quantity: l.qty,
      })),
    };
    try {
      const res = await createShopOrder(payload);
      const order = res.data;
      // Let the confirmation page (and later revisits) look the order up.
      sessionStorage.setItem(
        "shpe_last_order",
        JSON.stringify({ code: order.order_code, email: order.buyer_email })
      );
      clearCart();
      // Computed /me fields (has_paid_dues) change with this order — refresh
      // so the dues banner clears immediately. No-op for guests.
      refreshUser();
      navigate(`/shop/order/${order.order_code}`, { state: { order } });
    } catch (err) {
      const detail = err.response?.data?.detail;
      // Two different 429s reach here. The failed-charge throttle sends a
      // `detail` explaining itself; slowapi's ORDER_LIMIT handler returns
      // {"error": ...} with no detail, so it still needs the fallback.
      setError(
        err.response?.status === 429
          ? typeof detail === "string"
            ? detail
            : "Too many orders placed from this connection — try again in a minute."
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
                  {SQUARE_CONFIGURED ? "Secured by Square" : "SIMULATED · no real charge"}
                </span>
              </div>
              <p style={{ margin: "0 0 18px", fontSize: "13px", color: "var(--muted)" }}>
                {SQUARE_CONFIGURED
                  ? "Payments are processed securely by Square — your card number never touches our servers."
                  : "This is a placeholder checkout. It will be replaced by Square — the flow and buttons stay the same."}
              </p>

              {SQUARE_CONFIGURED && (
                <div>
                  {/* Express wallets — buttons appear only where supported.
                      The Google Pay container must exist before attach(), so
                      it always renders and is display:none until ready. */}
                  <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginBottom: applePayMethod || googlePayMethod ? "16px" : 0 }}>
                    {applePayMethod && (
                      <button
                        type="button"
                        aria-label="Pay with Apple Pay"
                        className="applePayBtn"
                        onClick={() => handlePay(applePayMethod)}
                        disabled={paying}
                      />
                    )}
                    <div
                      id="google-pay-button"
                      onClick={() => googlePayMethod && handlePay(googlePayMethod)}
                      style={{
                        display: googlePayMethod ? "block" : "none",
                        pointerEvents: paying ? "none" : "auto",
                        opacity: paying ? 0.5 : 1,
                      }}
                    />
                    {(applePayMethod || googlePayMethod) && (
                      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                        <span style={{ flex: 1, height: "1px", background: "var(--border)" }} />
                        <span style={{ fontSize: "12px", color: "var(--muted)" }}>or pay with card</span>
                        <span style={{ flex: 1, height: "1px", background: "var(--border)" }} />
                      </div>
                    )}
                  </div>

                  {/* Square's secure card fields render into this container */}
                  <div id="square-card" style={{ minHeight: "94px" }} />
                  {!cardReady && !error && (
                    <p style={{ margin: "4px 0 0", fontSize: "13px", color: "var(--muted)" }}>
                      Loading secure payment form…
                    </p>
                  )}
                </div>
              )}

              {/* Read-only demo card block (dev mode only) */}
              {!SQUARE_CONFIGURED && (
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
              )}

              {error && (
                <p style={{ margin: "14px 0 0", fontSize: "13px", fontWeight: 600, color: "var(--shpe-red)" }}>{error}</p>
              )}

              <button
                className="primaryBtn"
                onClick={() => handlePay()}
                disabled={paying || (SQUARE_CONFIGURED && !cardReady)}
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
