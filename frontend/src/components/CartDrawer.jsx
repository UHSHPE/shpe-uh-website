import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useCart } from "../context/CartContext";
import { formatCents } from "../utils/shop";
import PriceChangeNotice from "./PriceChangeNotice";
import { CartIcon, CheckIcon, CloseIcon, MinusIcon, PlusIcon, TrashIcon } from "./shopIcons";

// Slide-out cart drawer (right side) + scrim. Rendered once in App so it can
// open from any route.
export default function CartDrawer() {
  const {
    lines,
    count,
    subtotalCents,
    changeQty,
    removeLine,
    isOpen,
    closeCart,
    repriceCart,
    priceChanges,
    unavailableLines,
  } = useCart();
  const navigate = useNavigate();

  // Prices are snapshotted at add-to-cart time, so re-match against the live
  // catalog whenever the drawer opens. The notice here is informational — the
  // acknowledgment gate lives on checkout, where money actually moves.
  useEffect(() => {
    if (isOpen) repriceCart();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  if (!isOpen) return null;

  const unavailableKeys = new Set(
    unavailableLines.map((u) => `${u.productId}|${u.size ?? ""}`)
  );

  function goCheckout() {
    closeCart();
    navigate("/shop/checkout");
  }

  return (
    <>
      <div
        onClick={closeCart}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(3,10,30,.45)",
          zIndex: 2900,
          animation: "shopFadeIn .2s ease",
        }}
      />
      <div
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          bottom: 0,
          width: "428px",
          maxWidth: "92vw",
          background: "#fff",
          boxShadow: "var(--shadow-modal)",
          zIndex: 3000,
          display: "flex",
          flexDirection: "column",
          animation: "shopSlideInRight .28s var(--ease-out)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "20px 22px",
            borderBottom: "1px solid var(--border)",
          }}
        >
          <h2 style={{ margin: 0, fontSize: "19px", fontWeight: 800, color: "var(--ink)" }}>
            Your cart{" "}
            {count > 0 && (
              <span style={{ fontSize: "14px", fontWeight: 600, color: "var(--muted-soft)" }}>
                · {count}
              </span>
            )}
          </h2>
          <button
            onClick={closeCart}
            aria-label="Close cart"
            style={{
              width: "34px",
              height: "34px",
              borderRadius: "999px",
              border: "none",
              background: "var(--surface-soft)",
              color: "var(--ink-soft)",
              cursor: "pointer",
              display: "grid",
              placeItems: "center",
            }}
          >
            <CloseIcon size={18} />
          </button>
        </div>

        {lines.length === 0 ? (
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              textAlign: "center",
              padding: "32px",
              gap: "14px",
            }}
          >
            <div
              style={{
                width: "64px",
                height: "64px",
                borderRadius: "999px",
                background: "var(--surface-tint)",
                color: "var(--shpe-blue)",
                display: "grid",
                placeItems: "center",
              }}
            >
              <CartIcon size={28} strokeWidth={1.7} />
            </div>
            <div>
              <p style={{ margin: "0 0 4px", fontSize: "17px", fontWeight: 700, color: "var(--ink)" }}>
                Your cart is empty
              </p>
              <p style={{ margin: 0, fontSize: "14px", color: "var(--muted)" }}>
                Add some gear to rep the familia.
              </p>
            </div>
            <button
              className="primaryBtn"
              style={{ padding: "11px 22px", fontSize: "14px" }}
              onClick={() => {
                closeCart();
                navigate("/shop");
              }}
            >
              Browse the shop
            </button>
          </div>
        ) : (
          <>
            <div
              style={{
                flex: 1,
                overflowY: "auto",
                padding: "16px 20px",
                display: "flex",
                flexDirection: "column",
                gap: "14px",
              }}
            >
              {lines.map((line) => (
                <div
                  key={`${line.productId}|${line.size ?? ""}`}
                  style={{
                    display: "flex",
                    gap: "14px",
                    opacity: unavailableKeys.has(`${line.productId}|${line.size ?? ""}`) ? 0.55 : 1,
                  }}
                >
                  <div
                    style={{
                      width: "70px",
                      height: "70px",
                      flexShrink: 0,
                      borderRadius: "10px",
                      border: "1px solid var(--border)",
                      background: "var(--placeholder-hatch)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      overflow: "hidden",
                    }}
                  >
                    <span
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: "8px",
                        color: "#7c8aa3",
                        textAlign: "center",
                        padding: "2px",
                      }}
                    >
                      IMG
                    </span>
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: "8px" }}>
                      <p style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "var(--ink)", lineHeight: 1.3 }}>
                        {line.name}
                      </p>
                      <button
                        onClick={() => removeLine(line.productId, line.size)}
                        aria-label="Remove"
                        style={{
                          background: "transparent",
                          border: "none",
                          color: "var(--muted-soft)",
                          cursor: "pointer",
                          padding: 0,
                          flexShrink: 0,
                        }}
                      >
                        <TrashIcon size={16} strokeWidth={1.7} />
                      </button>
                    </div>
                    <p style={{ margin: "2px 0 8px", fontSize: "12px", color: "var(--muted)" }}>
                      {line.size ? `Size ${line.size}` : "Item"} · {formatCents(line.priceCents)} each
                    </p>
                    {unavailableKeys.has(`${line.productId}|${line.size ?? ""}`) && (
                      <p style={{ margin: "-4px 0 8px", fontSize: "12px", fontWeight: 600, color: "var(--shpe-red)" }}>
                        No longer available
                      </p>
                    )}
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        gap: "8px",
                      }}
                    >
                      <div
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          border: "1px solid var(--border)",
                          borderRadius: "8px",
                          overflow: "hidden",
                        }}
                      >
                        <button
                          onClick={() => changeQty(line.productId, line.size, -1)}
                          aria-label="Decrease quantity"
                          style={stepperBtn}
                        >
                          <MinusIcon size={13} />
                        </button>
                        <span style={{ minWidth: "34px", textAlign: "center", fontSize: "14px", fontWeight: 700, color: "var(--ink)" }}>
                          {line.qty}
                        </span>
                        <button
                          onClick={() => changeQty(line.productId, line.size, 1)}
                          aria-label="Increase quantity"
                          style={stepperBtn}
                        >
                          <PlusIcon size={13} />
                        </button>
                      </div>
                      <span style={{ fontSize: "14px", fontWeight: 800, color: "var(--shpe-blue)" }}>
                        {unavailableKeys.has(`${line.productId}|${line.size ?? ""}`)
                          ? "—"
                          : formatCents(line.priceCents * line.qty)}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div style={{ borderTop: "1px solid var(--border)", padding: "18px 22px" }}>
              <PriceChangeNotice changes={priceChanges} />
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "baseline",
                  marginBottom: "4px",
                  marginTop: priceChanges.length > 0 ? "14px" : 0,
                }}
              >
                <span style={{ fontSize: "15px", fontWeight: 700, color: "var(--ink)" }}>Subtotal</span>
                <span style={{ fontSize: "20px", fontWeight: 800, color: "var(--shpe-blue)" }}>
                  {formatCents(subtotalCents)}
                </span>
              </div>
              <p style={{ margin: "0 0 14px", fontSize: "12px", color: "var(--muted)" }}>
                Pay now · pick up at a chapter event. No shipping.
              </p>
              <button
                className="primaryBtn"
                style={{ width: "100%", padding: "14px 20px", fontSize: "15px" }}
                onClick={goCheckout}
              >
                Checkout
              </button>
            </div>
          </>
        )}
      </div>
    </>
  );
}

const stepperBtn = {
  width: "30px",
  height: "30px",
  border: "none",
  background: "#fff",
  color: "var(--shpe-blue)",
  cursor: "pointer",
  display: "grid",
  placeItems: "center",
};

// Bottom-center toast (dark pill, green tick), auto-dismissed by CartContext.
export function ShopToast() {
  const { toast } = useCart();
  if (!toast) return null;
  return (
    <div
      style={{
        position: "fixed",
        bottom: "24px",
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 4000,
        background: "var(--ink)",
        color: "#fff",
        borderRadius: "999px",
        padding: "11px 20px",
        fontSize: "14px",
        fontWeight: 600,
        boxShadow: "0 12px 40px rgba(0,0,0,.3)",
        display: "flex",
        alignItems: "center",
        gap: "9px",
        animation: "shopToastIn .25s ease",
      }}
    >
      <CheckIcon size={16} stroke="#4ade80" strokeWidth={2.5} />
      {toast}
    </div>
  );
}
