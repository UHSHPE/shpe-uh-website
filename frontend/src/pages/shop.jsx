import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getShopProducts, getShopSettings } from "../api/api";
import ProductImage from "../components/ProductImage";
import { BoxIcon } from "../components/shopIcons";
import { formatCents, typeLabel } from "../utils/shop";
import useDocumentTitle from "../hooks/useDocumentTitle";

// Product-agnostic fallback while settings load (or if the fetch fails).
const DEFAULT_TAGLINE =
  "Buy merch to rep SHPE UH. Pay online, then pick up in person at an upcoming chapter event.";

// Public storefront: hero (tagline editable via shop settings), category
// filter pills (derived from the catalog's product types — never hardcoded),
// and the product grid.
export default function Shop() {
  useDocumentTitle("Shop");
  const [products, setProducts] = useState(null); // null = loading
  const [error, setError] = useState(false);
  const [category, setCategory] = useState("all");
  const [tagline, setTagline] = useState(DEFAULT_TAGLINE);

  useEffect(() => {
    getShopProducts()
      .then((res) => setProducts(res.data))
      .catch(() => {
        setProducts([]);
        setError(true);
      });
    getShopSettings()
      .then((res) => setTagline(res.data.tagline || DEFAULT_TAGLINE))
      .catch(() => {});
  }, []);

  const loading = products === null;
  const types = [...new Set((products ?? []).map((p) => p.product_type))];
  const visible = (products ?? []).filter(
    (p) => category === "all" || p.product_type === category
  );

  return (
    <div
      style={{
        maxWidth: "1200px",
        margin: "0 auto",
        padding: "108px 20px 72px",
        fontFamily: "var(--font-body)",
      }}
    >
      {/* Hero */}
      <div
        style={{
          background: "var(--gradient-navy)",
          borderRadius: "var(--radius-2xl)",
          padding: "34px 36px",
          color: "#fff",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <p
          style={{
            margin: 0,
            opacity: 0.78,
            fontSize: "13px",
            fontWeight: 600,
            letterSpacing: ".04em",
            textTransform: "uppercase",
          }}
        >
          SHPE UH · Chapter Store
        </p>
        <h1
          style={{
            margin: "6px 0 8px",
            fontSize: "38px",
            fontWeight: 800,
            lineHeight: 1.05,
            letterSpacing: "-.5px",
          }}
        >
          Shop the familia
        </h1>
        <p
          style={{
            margin: 0,
            maxWidth: "520px",
            fontSize: "16px",
            lineHeight: 1.5,
            color: "rgba(255,255,255,.9)",
          }}
        >
          {tagline}
        </p>
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            marginTop: "16px",
            background: "rgba(255,255,255,.14)",
            border: "1px solid rgba(255,255,255,.28)",
            borderRadius: "999px",
            padding: "6px 14px",
            fontSize: "13px",
            fontWeight: 600,
          }}
        >
          <BoxIcon size={15} />
          In-person pickup · no shipping
        </div>
      </div>

      {/* Category filter — one pill per product_type present in the data */}
      {!loading && types.length > 0 && (
        <div style={{ display: "flex", gap: "8px", margin: "26px 0 20px", flexWrap: "wrap" }}>
          {[{ value: "all", label: "All" }, ...types.map((t) => ({ value: t, label: typeLabel(t) }))].map(
            (option) => {
              const active = category === option.value;
              return (
                <button
                  key={option.value}
                  onClick={() => setCategory(option.value)}
                  style={{
                    borderRadius: "999px",
                    padding: "8px 16px",
                    fontSize: "14px",
                    fontWeight: active ? 700 : 600,
                    border: active ? "1px solid var(--shpe-blue)" : "1px solid var(--border)",
                    background: active ? "var(--shpe-blue)" : "#fff",
                    color: active ? "#fff" : "var(--ink-soft)",
                    cursor: "pointer",
                  }}
                >
                  {option.label}
                </button>
              );
            }
          )}
        </div>
      )}
      {loading && <div style={{ height: "26px" }} />}

      {/* Loading skeletons */}
      {loading && (
        <div style={gridStyle}>
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              style={{
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-xl)",
                background: "#fff",
                overflow: "hidden",
              }}
            >
              <div style={{ aspectRatio: "4/3", background: "#e9eef6", animation: "shopPulse 1.4s ease-in-out infinite" }} />
              <div style={{ padding: "16px", display: "flex", flexDirection: "column", gap: "10px" }}>
                <div style={{ height: "14px", width: "70%", borderRadius: "6px", background: "#e9eef6", animation: "shopPulse 1.4s ease-in-out infinite" }} />
                <div style={{ height: "12px", width: "40%", borderRadius: "6px", background: "#eef2f8", animation: "shopPulse 1.4s ease-in-out infinite" }} />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty catalog */}
      {!loading && visible.length === 0 && (
        <div
          style={{
            border: "1px dashed var(--border-strong)",
            borderRadius: "var(--radius-xl)",
            background: "#fff",
            padding: "64px 24px",
            textAlign: "center",
          }}
        >
          <div
            style={{
              width: "56px",
              height: "56px",
              borderRadius: "16px",
              background: "var(--surface-tint)",
              color: "var(--shpe-blue)",
              display: "grid",
              placeItems: "center",
              margin: "0 auto 16px",
            }}
          >
            <BoxIcon size={26} strokeWidth={1.7} />
          </div>
          <p style={{ margin: "0 0 4px", fontSize: "18px", fontWeight: 700, color: "var(--ink)" }}>
            {error ? "The shop is unavailable" : "No products yet"}
          </p>
          <p style={{ margin: 0, color: "var(--muted)", fontSize: "14px" }}>
            {error
              ? "Something went wrong loading the catalog — try again in a moment."
              : "The store is being stocked — check back before the next chapter event."}
          </p>
        </div>
      )}

      {/* Product grid */}
      {!loading && visible.length > 0 && (
        <div style={gridStyle}>
          {visible.map((product) => (
            <Link
              key={product.id}
              to={`/shop/${product.id}`}
              className="shopCard"
              style={{
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-xl)",
                background: "#fff",
                overflow: "hidden",
                cursor: "pointer",
                display: "flex",
                flexDirection: "column",
              }}
            >
              <ProductImage product={product} />
              <div style={{ padding: "16px", display: "flex", flexDirection: "column", gap: "6px", flex: 1 }}>
                <span
                  style={{
                    fontSize: "11px",
                    fontWeight: 700,
                    letterSpacing: ".05em",
                    textTransform: "uppercase",
                    color: "var(--muted-soft)",
                  }}
                >
                  {typeLabel(product.product_type)}
                </span>
                <p style={{ margin: 0, fontSize: "16px", fontWeight: 700, color: "var(--ink)", lineHeight: 1.25 }}>
                  {product.name}
                </p>
                {/* Every listed product is orderable — GET /shop/products
                    filters out hidden and retired ones, and the chapter
                    fulfils per order, so nothing is ever "sold out". */}
                <div style={{ marginTop: "auto", paddingTop: "8px" }}>
                  <span style={{ fontSize: "16px", fontWeight: 800, color: "var(--shpe-blue)" }}>
                    {formatCents(product.price_cents)}
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

const gridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
  gap: "24px",
};
