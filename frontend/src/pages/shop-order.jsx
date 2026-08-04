import { useEffect, useState } from "react";
import { Link, useLocation, useParams, useSearchParams } from "react-router-dom";
import { getShopOrder } from "../api/api";
import { BoxIcon, CheckIcon } from "../components/shopIcons";
import { useAuth } from "../context/AuthContext";
import StatusPill from "../components/StatusPill";
import { formatCents } from "../utils/shop";

// Order confirmation / status page. Arrives with the order in route state
// right after checkout; on a revisit it looks the order up by code + email
// (from sessionStorage, the ?email= param, or a small prompt — the backend
// never reveals an order without the matching buyer email).
export default function ShopOrder() {
  const { code } = useParams();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { user } = useAuth();

  const [order, setOrder] = useState(location.state?.order ?? null);
  const [emailInput, setEmailInput] = useState("");
  const [lookupState, setLookupState] = useState(order ? "done" : "loading"); // loading | prompt | done | error

  useEffect(() => {
    if (order) return;
    let stored = null;
    try {
      stored = JSON.parse(sessionStorage.getItem("shpe_last_order"));
    } catch {
      stored = null;
    }
    const email =
      searchParams.get("email") ||
      (stored?.code === code ? stored.email : null);
    if (!email) {
      setLookupState("prompt");
      return;
    }
    lookup(email);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);

  function lookup(email) {
    setLookupState("loading");
    getShopOrder(code, email)
      .then((res) => {
        setOrder(res.data);
        setLookupState("done");
      })
      .catch(() => setLookupState("error"));
  }

  const wrap = {
    maxWidth: "640px",
    margin: "0 auto",
    padding: "120px 20px 72px",
    fontFamily: "var(--font-body)",
  };

  if (lookupState === "loading" && !order) {
    return (
      <div style={wrap}>
        <div style={{ height: "320px", borderRadius: "20px", background: "#e9eef6", animation: "shopPulse 1.4s ease-in-out infinite" }} />
      </div>
    );
  }

  if (lookupState === "prompt" || lookupState === "error") {
    return (
      <div style={wrap}>
        <div style={{ border: "1px solid var(--border)", borderRadius: "20px", background: "#fff", boxShadow: "var(--shadow-card)", padding: "28px 30px" }}>
          <h1 style={{ margin: "0 0 6px", fontSize: "22px", fontWeight: 800, color: "var(--ink)" }}>
            Check your order
          </h1>
          <p style={{ margin: "0 0 16px", fontSize: "14px", color: "var(--muted)" }}>
            Enter the email you used at checkout to see the status of order{" "}
            <strong style={{ fontFamily: "var(--font-mono)", color: "var(--shpe-blue)" }}>{code}</strong>.
          </p>
          {lookupState === "error" && (
            <p style={{ margin: "0 0 14px", fontSize: "13px", fontWeight: 600, color: "var(--shpe-red)" }}>
              We couldn't find that order with this email — double-check both and try again.
            </p>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (emailInput.trim()) lookup(emailInput.trim());
            }}
            style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}
          >
            <input
              className="shopInput"
              type="email"
              value={emailInput}
              onChange={(e) => setEmailInput(e.target.value)}
              placeholder="you@cougarnet.uh.edu"
              style={{ flex: 1, minWidth: "220px" }}
            />
            <button type="submit" className="primaryBtn" style={{ padding: "11px 22px", fontSize: "14px" }}>
              View order
            </button>
          </form>
        </div>
      </div>
    );
  }

  const isFresh = Boolean(location.state?.order);
  const firstName = order.buyer_name.split(" ")[0];

  return (
    <div style={wrap}>
      <div style={{ border: "1px solid var(--border)", borderRadius: "20px", background: "#fff", boxShadow: "0 4px 30px rgba(0,31,91,0.10)", overflow: "hidden" }}>
        {/* Success header */}
        <div style={{ background: "var(--gradient-success)", padding: "34px", textAlign: "center", color: "#fff" }}>
          <div
            style={{
              width: "64px",
              height: "64px",
              borderRadius: "999px",
              background: "rgba(255,255,255,.16)",
              border: "2px solid rgba(255,255,255,.4)",
              display: "grid",
              placeItems: "center",
              margin: "0 auto 14px",
              animation: "shopRiseIn .5s ease",
            }}
          >
            <CheckIcon size={32} strokeWidth={2.4} />
          </div>
          <h1 style={{ margin: 0, fontSize: "26px", fontWeight: 800 }}>
            {isFresh ? "Payment successful" : "Order status"}
          </h1>
          <p style={{ margin: "6px 0 0", opacity: 0.9, fontSize: "14px" }}>
            {isFresh
              ? `Thanks, ${firstName} — your order is confirmed.`
              : `Order for ${order.buyer_name}`}
          </p>
        </div>

        <div style={{ padding: "28px 30px" }}>
          {/* Order code */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "12px",
              background: "var(--surface-muted)",
              border: "1px solid var(--border)",
              borderRadius: "12px",
              padding: "14px 18px",
              marginBottom: "22px",
            }}
          >
            <div>
              <p style={{ margin: 0, fontSize: "11px", fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--muted-soft)" }}>
                Order code
              </p>
              <p style={{ margin: "2px 0 0", fontSize: "22px", fontWeight: 800, color: "var(--shpe-blue)", letterSpacing: ".02em", fontFamily: "var(--font-mono)" }}>
                {order.order_code}
              </p>
            </div>
            <StatusPill status={order.status} />
          </div>

          {/* Items */}
          <p style={{ margin: "0 0 10px", fontSize: "13px", fontWeight: 700, letterSpacing: ".04em", textTransform: "uppercase", color: "var(--muted-soft)" }}>
            Your items
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "22px" }}>
            {order.items.map((item, i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", gap: "12px", fontSize: "14px", color: "var(--ink-soft)" }}>
                <span>
                  {item.quantity}× {item.product_name}
                  {item.size ? ` (${item.size})` : ""}
                </span>
                <span style={{ fontWeight: 700, color: "var(--ink)" }}>
                  {formatCents(item.unit_price_cents * item.quantity)}
                </span>
              </div>
            ))}
            <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", fontSize: "15px", fontWeight: 800, color: "var(--shpe-blue)", borderTop: "1px solid var(--border)", paddingTop: "10px", marginTop: "2px" }}>
              <span>Total paid</span>
              <span>{formatCents(order.total_cents)}</span>
            </div>
          </div>

          {/* Pickup instructions */}
          <div style={{ display: "flex", alignItems: "flex-start", gap: "12px", background: "var(--surface-tint)", border: "1px solid var(--info-border)", borderRadius: "12px", padding: "16px 18px", marginBottom: "22px" }}>
            <BoxIcon size={20} stroke="var(--shpe-blue-pro)" style={{ flexShrink: 0, marginTop: "1px" }} />
            <div>
              <p style={{ margin: "0 0 3px", fontSize: "14px", fontWeight: 700, color: "var(--shpe-navy-700)" }}>
                Pickup instructions
              </p>
              <p style={{ margin: 0, fontSize: "13px", color: "var(--ink-soft)", lineHeight: 1.55 }}>
                Pick up at an upcoming chapter event once your order is marked{" "}
                <strong>ready for pickup</strong> — you'll get an email. Bring your order code{" "}
                <strong>{order.order_code}</strong>.
              </p>
            </div>
          </div>

          {/* Guest nudge */}
          {!user && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", border: "1px dashed var(--border-strong)", borderRadius: "12px", padding: "14px 18px", marginBottom: "20px" }}>
              <span style={{ fontSize: "13px", color: "var(--ink-soft)" }}>
                <strong>Track your orders.</strong> Create an account to see status updates.
              </span>
              <Link to="/signup" className="primaryBtn" style={{ padding: "7px 16px", fontSize: "13px", whiteSpace: "nowrap" }}>
                Create account
              </Link>
            </div>
          )}

          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
            <Link
              to="/shop"
              style={{
                flex: 1,
                borderRadius: "999px",
                padding: "12px 18px",
                fontSize: "14px",
                fontWeight: 700,
                border: "1px solid var(--border-strong)",
                background: "#fff",
                color: "var(--ink)",
                textAlign: "center",
                minWidth: "160px",
              }}
            >
              Continue shopping
            </Link>
            {user && (
              <Link
                to="/profile#orders"
                className="primaryBtn"
                style={{ flex: 1, padding: "12px 18px", fontSize: "14px", textAlign: "center", minWidth: "160px" }}
              >
                View my orders
              </Link>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
