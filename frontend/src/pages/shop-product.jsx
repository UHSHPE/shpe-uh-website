import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { DUES_PRODUCT_NAME } from "../utils/dues";
import { Link, useParams } from "react-router-dom";
import { getShopProduct } from "../api/api";
import ProductImage from "../components/ProductImage";
import { BackIcon, BoxIcon, CartIcon, MinusIcon, PlusIcon } from "../components/shopIcons";
import { useCart } from "../context/CartContext";
import { formatCents, typeLabel } from "../utils/shop";
import useDocumentTitle from "../hooks/useDocumentTitle";

// Product detail (own shareable route): size selector for apparel, quantity
// stepper, add to cart.
export default function ShopProduct() {
  const { productId } = useParams();
  const { addItem, showToast, itemCap } = useCart();
  const { user } = useAuth();

  const [product, setProduct] = useState(null);
  const [missing, setMissing] = useState(false);
  const [size, setSize] = useState(null);
  const [needSize, setNeedSize] = useState(false);
  const [qty, setQty] = useState(1);

  // Falls back to "Shop" rather than a falsy value, so the tab doesn't flash
  // the site default while the product is still loading.
  useDocumentTitle(product ? product.name : "Shop");

  // Reset selection when navigating between products. Render-phase reset
  // instead of an effect — see "You Might Not Need an Effect" (React docs).
  const [prevId, setPrevId] = useState(productId);
  if (prevId !== productId) {
    setPrevId(productId);
    setProduct(null);
    setMissing(false);
    setSize(null);
    setNeedSize(false);
    setQty(1);
  }

  useEffect(() => {
    let stale = false;
    getShopProduct(productId)
      .then((res) => {
        if (!stale) setProduct(res.data);
      })
      .catch(() => {
        if (!stale) setMissing(true);
      });
    return () => {
      stale = true;
    };
  }, [productId]);

  const isApparel = product?.product_type === "apparel";

  // Dues are one-per-member: quantity locked to 1, and members who already
  // paid see a confirmation instead of the add-to-cart button.
  const isDues = product?.name === DUES_PRODUCT_NAME;
  const effectiveCap = isDues ? 1 : itemCap;
  const alreadyPaidDues = isDues && user?.has_paid_dues;

  function handleAdd() {
    if (isApparel && !size) {
      setNeedSize(true);
      showToast("Select a size first");
      return;
    }
    addItem(product, isApparel ? size : null, qty);
  }

  return (
    <div
      style={{
        maxWidth: "1040px",
        margin: "0 auto",
        padding: "108px 20px 72px",
        fontFamily: "var(--font-body)",
      }}
    >
      <Link
        to="/shop"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "7px",
          color: "var(--muted)",
          fontSize: "14px",
          fontWeight: 600,
          marginBottom: "20px",
        }}
      >
        <BackIcon size={16} />
        Back to shop
      </Link>

      {missing && (
        <div
          style={{
            border: "1px dashed var(--border-strong)",
            borderRadius: "var(--radius-xl)",
            background: "#fff",
            padding: "64px 24px",
            textAlign: "center",
          }}
        >
          <p style={{ margin: "0 0 4px", fontSize: "18px", fontWeight: 700, color: "var(--ink)" }}>
            This product isn't available right now
          </p>
          <p style={{ margin: 0, color: "var(--muted)", fontSize: "14px" }}>
            It may be sold out or no longer in the catalog.
          </p>
        </div>
      )}

      {!missing && !product && (
        <div className="shopDetailGrid">
          <div style={{ aspectRatio: "1/1", borderRadius: "var(--radius-2xl)", background: "#e9eef6", animation: "shopPulse 1.4s ease-in-out infinite" }} />
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <div style={{ height: "30px", width: "60%", borderRadius: "6px", background: "#e9eef6", animation: "shopPulse 1.4s ease-in-out infinite" }} />
            <div style={{ height: "20px", width: "30%", borderRadius: "6px", background: "#eef2f8", animation: "shopPulse 1.4s ease-in-out infinite" }} />
          </div>
        </div>
      )}

      {product && (
        <div className="shopDetailGrid">
          <div
            style={{
              position: "relative",
              borderRadius: "var(--radius-2xl)",
              border: "1px solid var(--border)",
              overflow: "hidden",
            }}
          >
            <ProductImage product={product} aspectRatio="1/1" labelSize={12} />
          </div>

          <div>
            <span
              style={{
                fontSize: "12px",
                fontWeight: 700,
                letterSpacing: ".06em",
                textTransform: "uppercase",
                color: "var(--muted-soft)",
              }}
            >
              {typeLabel(product.product_type)}
            </span>
            <h1 style={{ margin: "6px 0 8px", fontSize: "30px", fontWeight: 800, color: "var(--ink)", lineHeight: 1.1 }}>
              {product.name}
            </h1>
            <p style={{ margin: "0 0 16px", fontSize: "24px", fontWeight: 800, color: "var(--shpe-blue)" }}>
              {formatCents(product.price_cents)}
            </p>
            <p style={{ margin: "0 0 22px", color: "var(--ink-soft)", fontSize: "15px", lineHeight: 1.6, textWrap: "pretty" }}>
              {product.description}
            </p>

            {isApparel && (
              <div style={{ marginBottom: "20px" }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    marginBottom: "8px",
                  }}
                >
                  <span style={{ fontSize: "13px", fontWeight: 700, color: "var(--ink)" }}>Size</span>
                  {needSize && (
                    <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--shpe-red)" }}>
                      Select a size
                    </span>
                  )}
                </div>
                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                  {(product.sizes ?? []).map((sz) => {
                    const active = size === sz;
                    return (
                      <button
                        key={sz}
                        onClick={() => {
                          setSize(sz);
                          setNeedSize(false);
                        }}
                        style={{
                          minWidth: "48px",
                          borderRadius: "10px",
                          padding: "10px 12px",
                          fontSize: "14px",
                          fontWeight: active ? 700 : 600,
                          border: active ? "1.5px solid var(--shpe-blue)" : "1.5px solid var(--border)",
                          background: active ? "var(--shpe-blue)" : "#fff",
                          color: active ? "#fff" : "var(--ink-soft)",
                          cursor: "pointer",
                        }}
                      >
                        {sz}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            <div style={{ marginBottom: "22px" }}>
              <span style={{ display: "block", fontSize: "13px", fontWeight: 700, color: "var(--ink)", marginBottom: "8px" }}>
                Quantity
              </span>
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  border: "1.5px solid var(--border)",
                  borderRadius: "10px",
                  overflow: "hidden",
                }}
              >
                <button onClick={() => setQty((q) => Math.max(1, q - 1))} aria-label="Decrease quantity" style={qtyBtn}>
                  <MinusIcon size={16} strokeWidth={2.2} />
                </button>
                <span style={{ minWidth: "48px", textAlign: "center", fontSize: "16px", fontWeight: 700, color: "var(--ink)" }}>
                  {qty}
                </span>
                <button
                  onClick={() => setQty((q) => Math.min(effectiveCap, q + 1))}
                  aria-label="Increase quantity"
                  style={{ ...qtyBtn, opacity: qty >= effectiveCap ? 0.4 : 1 }}
                >
                  <PlusIcon size={16} strokeWidth={2.2} />
                </button>
              </div>
              {qty >= effectiveCap && (
                <p style={{ margin: "6px 0 0", fontSize: "12px", color: "var(--muted)" }}>
                  {isDues
                    ? "One per member — dues are a one-time purchase."
                    : `Limit ${itemCap} per item per order.`}
                </p>
              )}
            </div>

            {alreadyPaidDues ? (
              <div
                style={{
                  width: "100%",
                  padding: "14px 20px",
                  fontSize: "14px",
                  fontWeight: 700,
                  textAlign: "center",
                  borderRadius: "12px",
                  background: "var(--success-bg)",
                  border: "1px solid var(--success-border)",
                  color: "var(--success-deep)",
                }}
              >
                ✓ You've already paid your T-Shirt Dues — thank you!
              </div>
            ) : (
              <button
                className="primaryBtn"
                onClick={handleAdd}
                style={{
                  width: "100%",
                  padding: "14px 20px",
                  fontSize: "15px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "9px",
                }}
              >
                <CartIcon size={18} strokeWidth={1.9} />
                Add to cart
              </button>
            )}

            <div
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: "10px",
                marginTop: "18px",
                padding: "14px 16px",
                background: "var(--surface-tint)",
                border: "1px solid var(--info-border)",
                borderRadius: "12px",
              }}
            >
              <BoxIcon size={18} stroke="var(--shpe-blue-pro)" style={{ flexShrink: 0, marginTop: "1px" }} />
              <p style={{ margin: 0, fontSize: "13px", color: "var(--shpe-navy-700)", lineHeight: 1.5 }}>
                <strong>In-person pickup.</strong> Pay now and pick up at an upcoming chapter event
                once your order is marked ready. No shipping.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const qtyBtn = {
  width: "42px",
  height: "42px",
  border: "none",
  background: "#fff",
  color: "var(--shpe-blue)",
  cursor: "pointer",
  display: "grid",
  placeItems: "center",
};
