import { formatCents } from "../utils/shop";

// Amber callout listing lines whose catalog price moved while they sat in the
// cart. Shown wherever a total is displayed, because the cart is re-priced on
// the way in and the buyer must not discover the new figure on the receipt.
//
// `onAcknowledge` is passed only on checkout, where the Pay button stays
// disabled until it fires — the drawer's copy is informational, since its
// button navigates rather than charges.
export default function PriceChangeNotice({ changes, onAcknowledge }) {
  if (changes.length === 0) return null;

  return (
    <div
      role="status"
      style={{
        background: "var(--status-ready-bg)",
        border: "1px solid var(--status-ready-border)",
        borderRadius: "12px",
        padding: "12px 16px",
        marginTop: "14px",
      }}
    >
      <p
        style={{
          margin: 0,
          fontSize: "13px",
          fontWeight: 700,
          color: "var(--status-ready-text)",
        }}
      >
        {changes.length === 1
          ? "A price changed since you added it"
          : "Some prices changed since you added them"}
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: "4px", margin: "8px 0 0" }}>
        {changes.map((c) => (
          <div
            key={`${c.productId}|${c.size ?? ""}`}
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: "12px",
              fontSize: "12.5px",
              color: "var(--status-ready-text)",
            }}
          >
            <span>
              {c.name}
              {c.size ? ` (${c.size})` : ""}
            </span>
            <span style={{ whiteSpace: "nowrap", fontWeight: 700 }}>
              <s style={{ opacity: 0.65, fontWeight: 500 }}>{formatCents(c.fromCents)}</s>
              {" → "}
              {formatCents(c.toCents)}
            </span>
          </div>
        ))}
      </div>
      {onAcknowledge && (
        <button
          className="ghostBtn"
          onClick={onAcknowledge}
          style={{ marginTop: "12px", padding: "7px 14px", fontSize: "13px" }}
        >
          OK, got it
        </button>
      )}
    </div>
  );
}
