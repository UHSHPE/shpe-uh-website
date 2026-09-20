import { productImageUrl } from "../../api/api";
import { formatCents, typeLabel } from "../../utils/shop";
import Pagination from "../Pagination";
import { ChevronDownIcon, PencilIcon, PlusIcon, TrashIcon } from "../shopIcons";
import { iconButton, productRow } from "./styles";

function ProductImage({ product }) {
  const image = productImageUrl(product);
  return (
    <div
      style={{
        width: "40px",
        height: "40px",
        borderRadius: "8px",
        border: "1px solid var(--border)",
        background: image
          ? `center/cover url(${image})`
          : "var(--placeholder-hatch)",
      }}
    />
  );
}

function ProductDetails({ product, muted = false }) {
  return (
    <div style={{ minWidth: 0 }}>
      <p
        style={{
          margin: 0,
          fontSize: "14px",
          fontWeight: 700,
          color: muted ? "var(--muted)" : "var(--ink)",
          lineHeight: 1.25,
        }}
      >
        {product.name}
      </p>
      <p
        style={{
          margin: "2px 0 0",
          fontSize: "12px",
          color: "var(--muted-soft)",
        }}
      >
        {product.product_type === "apparel"
          ? (product.sizes ?? []).join(" · ")
          : "No sizes"}
      </p>
    </div>
  );
}

export default function ProductsTab({
  liveProducts,
  retiredProducts,
  livePager,
  retiredPager,
  retiredOpen,
  onToggleRetired,
  onAdd,
  onEdit,
  onToggleActive,
  onRequestRetire,
  onRestore,
}) {
  return (
    <>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "12px",
          marginBottom: "16px",
          flexWrap: "wrap",
        }}
      >
        <p style={{ margin: 0, fontSize: "14px", color: "var(--muted)" }}>
          Manage what's on the shelf. Toggle availability or edit details
          anytime.
        </p>
        <button
          className="primaryBtn"
          onClick={onAdd}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            padding: "9px 18px",
            fontSize: "14px",
          }}
        >
          <PlusIcon size={16} strokeWidth={2.2} />
          Add product
        </button>
      </div>
      <div
        style={{
          border: "1px solid var(--border)",
          borderRadius: "12px",
          overflowX: "auto",
        }}
      >
        <div
          style={{
            ...productRow,
            background: "var(--surface-muted)",
            borderBottom: "1px solid var(--border)",
            fontSize: "11px",
            fontWeight: 700,
            letterSpacing: ".04em",
            textTransform: "uppercase",
            color: "var(--muted-soft)",
          }}
        >
          <span />
          <span>Product</span>
          <span>Type</span>
          <span>Price</span>
          <span>Status</span>
          <span style={{ textAlign: "right" }}>Edit</span>
        </div>
        {livePager.pageItems.map((product) => (
          <div
            key={product.id}
            style={{
              ...productRow,
              borderBottom: "1px solid var(--surface-soft)",
            }}
          >
            <ProductImage product={product} />
            <ProductDetails product={product} />
            <span style={{ fontSize: "13px", color: "var(--ink-soft)" }}>
              {typeLabel(product.product_type)}
            </span>
            <span
              style={{
                fontSize: "14px",
                fontWeight: 700,
                color: "var(--shpe-blue)",
              }}
            >
              {formatCents(product.price_cents)}
            </span>
            <div>
              <button
                onClick={() => onToggleActive(product)}
                style={{
                  borderRadius: "999px",
                  padding: "4px 11px",
                  fontSize: "11px",
                  fontWeight: 700,
                  cursor: "pointer",
                  color: product.is_active
                    ? "var(--status-picked-text)"
                    : "var(--status-cancelled-text)",
                  background: product.is_active
                    ? "var(--status-picked-bg)"
                    : "var(--status-cancelled-bg)",
                  border: product.is_active
                    ? "1px solid var(--status-picked-border)"
                    : "1px solid var(--status-cancelled-border)",
                }}
              >
                {product.is_active ? "Active" : "Hidden"}
              </button>
            </div>
            <div
              style={{
                display: "flex",
                gap: "6px",
                justifyContent: "flex-end",
              }}
            >
              <button
                onClick={() => onEdit(product)}
                aria-label="Edit"
                style={iconButton}
              >
                <PencilIcon size={15} />
              </button>
              <button
                onClick={() => onRequestRetire(product)}
                aria-label="Retire"
                style={{
                  ...iconButton,
                  border: "1px solid #F3D6CC",
                  color: "var(--shpe-red)",
                }}
              >
                <TrashIcon size={15} />
              </button>
            </div>
          </div>
        ))}
        {liveProducts.length === 0 && (
          <div
            style={{
              padding: "32px",
              textAlign: "center",
              color: "var(--muted)",
              fontSize: "14px",
            }}
          >
            No products yet — add the first one.
          </div>
        )}
      </div>
      <Pagination {...livePager} label="products" />

      <div
        style={{
          marginTop: "18px",
          border: "1px solid var(--border)",
          borderRadius: "12px",
          overflow: "hidden",
        }}
      >
        <button
          onClick={onToggleRetired}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "10px",
            padding: "12px 16px",
            border: "none",
            background: "var(--surface-muted)",
            color: "var(--muted)",
            fontSize: "13px",
            fontWeight: 700,
            cursor: "pointer",
            textAlign: "left",
          }}
        >
          Retired ({retiredProducts.length})
          <ChevronDownIcon
            size={16}
            stroke="var(--muted-soft)"
            style={{ transform: retiredOpen ? "rotate(180deg)" : "none" }}
          />
        </button>
        {retiredOpen && (
          <>
            <div
              style={{
                borderTop: "1px solid var(--border)",
                overflowX: "auto",
              }}
            >
              {retiredProducts.length === 0 ? (
                <div
                  style={{
                    padding: "20px 16px",
                    textAlign: "center",
                    color: "var(--muted)",
                    fontSize: "13px",
                  }}
                >
                  Nothing retired yet — retired products land here and can be
                  restored.
                </div>
              ) : (
                retiredPager.pageItems.map((product) => (
                  <div
                    key={product.id}
                    style={{
                      ...productRow,
                      borderBottom: "1px solid var(--surface-soft)",
                      opacity: 0.7,
                    }}
                  >
                    <ProductImage product={product} />
                    <ProductDetails product={product} muted />
                    <span style={{ fontSize: "13px", color: "var(--muted)" }}>
                      {typeLabel(product.product_type)}
                    </span>
                    <span
                      style={{
                        fontSize: "14px",
                        fontWeight: 700,
                        color: "var(--muted)",
                      }}
                    >
                      {formatCents(product.price_cents)}
                    </span>
                    <div>
                      <span
                        style={{
                          display: "inline-block",
                          borderRadius: "999px",
                          padding: "4px 11px",
                          fontSize: "11px",
                          fontWeight: 700,
                          color: "var(--status-cancelled-text)",
                          background: "var(--status-cancelled-bg)",
                          border: "1px solid var(--status-cancelled-border)",
                        }}
                      >
                        Retired
                      </span>
                    </div>
                    <div
                      style={{ display: "flex", justifyContent: "flex-end" }}
                    >
                      <button
                        onClick={() => onRestore(product)}
                        style={{
                          borderRadius: "999px",
                          padding: "6px 13px",
                          fontSize: "12px",
                          fontWeight: 700,
                          border: "1px solid var(--border-strong)",
                          background: "#fff",
                          color: "var(--shpe-blue)",
                          cursor: "pointer",
                          whiteSpace: "nowrap",
                        }}
                      >
                        Restore
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
            <div style={{ padding: "0 16px 14px" }}>
              <Pagination {...retiredPager} label="retired products" />
            </div>
          </>
        )}
      </div>
    </>
  );
}
