import {
  formatCents,
  formatOrderDate,
  orderItemsSummary,
} from "../../utils/shop";
import Pagination from "../Pagination";
import StatusPill from "../StatusPill";
import { CheckIcon, ChevronDownIcon } from "../shopIcons";
import { sectionLabel } from "./styles";

const FILTERS = [
  { key: "all", label: "All" },
  { key: "paid", label: "Paid" },
  { key: "ready", label: "Ready" },
  { key: "picked_up", label: "Picked up" },
  { key: "cancelled", label: "Cancelled" },
];

function OrderActions({ order, onStatusChange }) {
  return (
    <div
      style={{
        display: "flex",
        gap: "8px",
        flexWrap: "wrap",
        alignItems: "center",
      }}
    >
      {order.status === "paid" && (
        <button
          className="primaryBtn"
          style={{ padding: "9px 16px", fontSize: "13px" }}
          onClick={() => onStatusChange(order, "ready")}
        >
          Mark ready for pickup →
        </button>
      )}
      {order.status === "ready" && (
        <button
          style={{
            borderRadius: "999px",
            padding: "9px 16px",
            fontSize: "13px",
            fontWeight: 700,
            border: "1px solid var(--success-deep)",
            background: "var(--success-deep)",
            color: "#fff",
            cursor: "pointer",
          }}
          onClick={() => onStatusChange(order, "picked_up")}
        >
          Mark picked up →
        </button>
      )}
      {(order.status === "paid" || order.status === "ready") && (
        <button
          style={{
            borderRadius: "999px",
            padding: "9px 16px",
            fontSize: "13px",
            fontWeight: 700,
            border: "1px solid #F3D6CC",
            background: "#fff",
            color: "var(--shpe-red)",
            cursor: "pointer",
          }}
          onClick={() => onStatusChange(order, "cancelled")}
        >
          Cancel order
        </button>
      )}
      {order.status === "picked_up" && (
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "7px",
            fontSize: "13px",
            fontWeight: 700,
            color: "var(--success-deep)",
          }}
        >
          <CheckIcon size={15} />
          Completed — picked up
        </span>
      )}
      {order.status === "cancelled" && (
        <span
          style={{ fontSize: "13px", fontWeight: 700, color: "var(--muted)" }}
        >
          This order was cancelled.
        </span>
      )}
    </div>
  );
}

export default function OrdersTab({
  counts,
  filter,
  onFilterChange,
  orders,
  pager,
  expandedId,
  onExpandedChange,
  noteDrafts,
  setNoteDrafts,
  onSaveNote,
  onStatusChange,
}) {
  function toggleOrder(order) {
    onExpandedChange(expandedId === order.id ? null : order.id);
    setNoteDrafts((drafts) => ({
      ...drafts,
      [order.id]: drafts[order.id] ?? order.notes ?? "",
    }));
  }

  return (
    <>
      <div
        style={{
          display: "flex",
          gap: "8px",
          flexWrap: "wrap",
          marginBottom: "18px",
        }}
      >
        {FILTERS.map((item) => {
          const active = filter === item.key;
          return (
            <button
              key={item.key}
              onClick={() => onFilterChange(item.key)}
              style={{
                borderRadius: "999px",
                padding: "7px 14px",
                fontSize: "13px",
                fontWeight: active ? 700 : 600,
                border: active
                  ? "1px solid var(--shpe-blue)"
                  : "1px solid var(--border)",
                background: active ? "var(--shpe-blue)" : "#fff",
                color: active ? "#fff" : "var(--ink-soft)",
                cursor: "pointer",
              }}
            >
              {item.label}{" "}
              <span
                style={{
                  opacity: active ? 0.7 : 1,
                  color: active ? undefined : "var(--muted-soft)",
                }}
              >
                {counts[item.key]}
              </span>
            </button>
          );
        })}
      </div>
      {orders.length === 0 && (
        <div
          style={{
            textAlign: "center",
            padding: "40px",
            color: "var(--muted)",
            fontSize: "14px",
          }}
        >
          No orders in this view.
        </div>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        {pager.pageItems.map((order) => {
          const expanded = expandedId === order.id;
          return (
            <div
              key={order.id}
              style={{
                border: "1px solid var(--border)",
                borderRadius: "12px",
                overflow: "hidden",
              }}
            >
              <div
                onClick={() => toggleOrder(order)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "14px",
                  padding: "14px 16px",
                  cursor: "pointer",
                  flexWrap: "wrap",
                }}
              >
                <div style={{ flex: 1, minWidth: "200px" }}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "10px",
                      marginBottom: "3px",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "14px",
                        fontWeight: 800,
                        color: "var(--shpe-blue)",
                        fontFamily: "var(--font-mono)",
                      }}
                    >
                      {order.order_code}
                    </span>
                    <StatusPill status={order.status} />
                  </div>
                  <p
                    style={{
                      margin: 0,
                      fontSize: "13px",
                      fontWeight: 700,
                      color: "var(--ink)",
                    }}
                  >
                    {order.buyer_name}
                  </p>
                  <p
                    style={{
                      margin: "2px 0 0",
                      fontSize: "12px",
                      color: "var(--muted)",
                    }}
                  >
                    {orderItemsSummary(order.items)}
                  </p>
                </div>
                <div style={{ textAlign: "right" }}>
                  <p
                    style={{
                      margin: 0,
                      fontSize: "15px",
                      fontWeight: 800,
                      color: "var(--ink)",
                    }}
                  >
                    {formatCents(order.total_cents)}
                  </p>
                  <p
                    style={{
                      margin: "2px 0 0",
                      fontSize: "12px",
                      color: "var(--muted-soft)",
                    }}
                  >
                    Placed {formatOrderDate(order.created_at)}
                  </p>
                </div>
                <ChevronDownIcon
                  size={18}
                  stroke="var(--muted-soft)"
                  style={{ transform: expanded ? "rotate(180deg)" : "none" }}
                />
              </div>
              {expanded && (
                <div
                  style={{
                    borderTop: "1px solid var(--border)",
                    background: "var(--surface-muted)",
                    padding: "18px",
                  }}
                >
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns:
                        "repeat(auto-fit, minmax(240px, 1fr))",
                      gap: "20px",
                      marginBottom: "16px",
                    }}
                  >
                    <div>
                      <p style={sectionLabel}>Buyer & contact</p>
                      <p
                        style={{
                          margin: 0,
                          fontSize: "14px",
                          fontWeight: 700,
                          color: "var(--ink)",
                        }}
                      >
                        {order.buyer_name}
                      </p>
                      <p
                        style={{
                          margin: "3px 0 0",
                          fontSize: "13px",
                          color: "var(--muted)",
                        }}
                      >
                        {order.buyer_email}
                        {order.buyer_phone ? ` · ${order.buyer_phone}` : ""}
                      </p>
                    </div>
                    <div>
                      <p style={sectionLabel}>Items</p>
                      {order.items.map((item, index) => (
                        <div
                          key={index}
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            gap: "10px",
                            fontSize: "13px",
                            color: "var(--ink-soft)",
                            marginBottom: "2px",
                          }}
                        >
                          <span>
                            {item.quantity}× {item.product_name}
                            {item.size ? ` (${item.size})` : ""}
                          </span>
                          <span
                            style={{ fontWeight: 700, color: "var(--ink)" }}
                          >
                            {formatCents(item.unit_price_cents * item.quantity)}
                          </span>
                        </div>
                      ))}
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          gap: "10px",
                          fontSize: "13px",
                          fontWeight: 800,
                          color: "var(--shpe-blue)",
                          borderTop: "1px solid var(--border)",
                          marginTop: "6px",
                          paddingTop: "6px",
                        }}
                      >
                        <span>Total</span>
                        <span>{formatCents(order.total_cents)}</span>
                      </div>
                    </div>
                  </div>
                  <div style={{ marginBottom: "14px" }}>
                    <p style={{ ...sectionLabel, marginBottom: "6px" }}>
                      Internal note
                    </p>
                    <div style={{ display: "flex", gap: "8px" }}>
                      <input
                        className="shopInput"
                        style={{
                          flex: 1,
                          padding: "10px 12px",
                          fontSize: "13px",
                        }}
                        value={noteDrafts[order.id] ?? ""}
                        onChange={(event) =>
                          setNoteDrafts((drafts) => ({
                            ...drafts,
                            [order.id]: event.target.value,
                          }))
                        }
                        placeholder="Add a note (e.g. picked up by roommate)"
                      />
                      <button
                        onClick={() => onSaveNote(order)}
                        style={{
                          borderRadius: "10px",
                          padding: "0 16px",
                          fontSize: "13px",
                          fontWeight: 700,
                          border: "1px solid var(--border-strong)",
                          background: "#fff",
                          color: "var(--shpe-blue)",
                          cursor: "pointer",
                        }}
                      >
                        Save
                      </button>
                    </div>
                  </div>
                  <OrderActions order={order} onStatusChange={onStatusChange} />
                </div>
              )}
            </div>
          );
        })}
      </div>
      <Pagination {...pager} label="orders" />
    </>
  );
}
