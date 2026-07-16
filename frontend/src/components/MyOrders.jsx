import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getMyShopOrders, getShopProducts } from "../api/api";
import { useCart } from "../context/CartContext";
import StatusPill from "./StatusPill";
import { formatCents, formatOrderDate, orderItemsSummary } from "../utils/shop";

// "My orders" card on the profile page — every signed-in member sees their
// order history with live status and a re-order shortcut.
export default function MyOrders() {
  const [orders, setOrders] = useState(null);
  const { addItem, showToast } = useCart();

  useEffect(() => {
    getMyShopOrders()
      .then((res) => setOrders(res.data))
      .catch(() => setOrders([]));
  }, []);

  // Re-adds the order's items to the cart from the live catalog (skipping
  // anything that's gone or sold out since) and opens the drawer.
  async function handleReorder(order) {
    let products = [];
    try {
      products = (await getShopProducts()).data;
    } catch {
      showToast("Couldn't load the catalog");
      return;
    }
    let added = 0;
    for (const item of order.items) {
      const product = products.find((p) => p.id === item.product_id);
      if (!product) continue;
      const size =
        product.product_type === "apparel" && product.sizes?.includes(item.size)
          ? item.size
          : product.product_type === "apparel"
            ? null
            : undefined;
      if (product.product_type === "apparel" && !size) continue;
      addItem(product, size ?? null, item.quantity, { openDrawer: added === 0 });
      added += 1;
    }
    if (added === 0) showToast("Those items are no longer available");
    else if (added < order.items.length) showToast("Some items are no longer available");
  }

  return (
    <div
      style={{
        border: "1px solid var(--border)",
        borderRadius: "16px",
        padding: "24px 26px",
        background: "#fff",
        boxShadow: "var(--shadow-card)",
        marginBottom: "24px",
      }}
    >
      <h2 style={{ margin: "0 0 4px", fontSize: "18px", fontWeight: 700, color: "var(--shpe-blue)" }}>
        My orders
      </h2>
      <p style={{ margin: "0 0 18px", fontSize: "13px", color: "var(--muted)" }}>
        Track pickup status and re-order your favorites.
      </p>

      {orders === null && (
        <p style={{ margin: 0, color: "var(--muted)", fontSize: "14px" }}>Loading orders…</p>
      )}

      {orders?.length === 0 && (
        <div style={{ textAlign: "center", padding: "32px 16px", color: "var(--muted)", fontSize: "14px" }}>
          You haven't placed any orders yet.{" "}
          <Link to="/shop" style={{ color: "var(--shpe-blue-bright)", fontWeight: 700 }}>
            Browse the shop →
          </Link>
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        {(orders ?? []).map((order) => (
          <div
            key={order.id}
            style={{
              border: "1px solid var(--border)",
              borderRadius: "12px",
              padding: "16px 18px",
              display: "flex",
              alignItems: "center",
              gap: "16px",
              flexWrap: "wrap",
            }}
          >
            <div style={{ flex: 1, minWidth: "180px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "4px" }}>
                <span style={{ fontSize: "15px", fontWeight: 800, color: "var(--shpe-blue)", fontFamily: "var(--font-mono)" }}>
                  {order.order_code}
                </span>
                <StatusPill status={order.status} />
              </div>
              <p style={{ margin: 0, fontSize: "13px", color: "var(--ink-soft)" }}>
                {orderItemsSummary(order.items)}
              </p>
              <p style={{ margin: "3px 0 0", fontSize: "12px", color: "var(--muted-soft)" }}>
                {formatOrderDate(order.created_at)} · {formatCents(order.total_cents)}
              </p>
            </div>
            <button
              onClick={() => handleReorder(order)}
              style={{
                borderRadius: "999px",
                padding: "8px 16px",
                fontSize: "13px",
                fontWeight: 700,
                border: "1px solid var(--border-strong)",
                background: "#fff",
                color: "var(--shpe-blue)",
                cursor: "pointer",
              }}
            >
              Re-order
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
