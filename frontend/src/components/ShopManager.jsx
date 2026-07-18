import { useEffect, useRef, useState } from "react";
import {
  createProduct,
  deleteProduct,
  getAdminProducts,
  getNotifications,
  getShopOrders,
  getShopSettings,
  markNotificationRead,
  productImageUrl,
  updateProduct,
  updateShopOrder,
  updateShopSettings,
  uploadProductImage,
} from "../api/api";
import { useCart } from "../context/CartContext";
import StatusPill from "./StatusPill";
import { formatCents, formatOrderDate, orderItemsSummary, typeLabel } from "../utils/shop";
import { ChevronDownIcon, CheckIcon, CloseIcon, ImageIcon, PencilIcon, PlusIcon, TrashIcon } from "./shopIcons";

const APPAREL_SIZES = ["S", "M", "L", "XL", "2XL"];

const emptyForm = {
  id: null,
  name: "",
  description: "",
  price: "",
  product_type: "apparel",
  sizes: [...APPAREL_SIZES],
  is_active: true,
  imageFile: null,
};

// Manager-only admin card on the profile page: Overview · Products · Orders ·
// Notifications (per spec §4.2 / design handoff screen 7).
export default function ShopManager() {
  const { showToast } = useCart();
  const [tab, setTab] = useState("overview");
  const [products, setProducts] = useState([]);
  const [orders, setOrders] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [orderFilter, setOrderFilter] = useState("all");
  const [expandedId, setExpandedId] = useState(null);
  const [noteDrafts, setNoteDrafts] = useState({});
  const [form, setForm] = useState(null); // null = modal closed
  const [settingsDraft, setSettingsDraft] = useState({ tagline: "", order_item_cap: "" });
  const fileInputRef = useRef(null);

  function refreshProducts() {
    getAdminProducts().then((res) => setProducts(res.data)).catch(() => {});
  }
  function refreshOrders() {
    getShopOrders().then((res) => setOrders(res.data)).catch(() => {});
  }
  function refreshNotifications() {
    getNotifications().then((res) => setNotifications(res.data)).catch(() => {});
  }

  useEffect(() => {
    refreshProducts();
    refreshOrders();
    refreshNotifications();
    getShopSettings()
      .then((res) =>
        setSettingsDraft({
          tagline: res.data.tagline,
          order_item_cap: String(res.data.order_item_cap),
        })
      )
      .catch(() => {});
  }, []);

  const settingsCap = parseInt(settingsDraft.order_item_cap, 10);
  const settingsValid = settingsDraft.tagline.trim() !== "" && settingsCap > 0;

  async function saveSettings() {
    try {
      await updateShopSettings({
        tagline: settingsDraft.tagline.trim(),
        order_item_cap: settingsCap,
      });
      showToast("Settings saved");
    } catch (err) {
      showToast(err.response?.data?.detail || "Couldn't save settings");
    }
  }

  const unread = notifications.filter((n) => !n.is_read);
  const counts = {
    all: orders.length,
    paid: orders.filter((o) => o.status === "paid").length,
    ready: orders.filter((o) => o.status === "ready").length,
    picked_up: orders.filter((o) => o.status === "picked_up").length,
    cancelled: orders.filter((o) => o.status === "cancelled").length,
  };
  const collectedCents = orders
    .filter((o) => o.status !== "cancelled")
    .reduce((sum, o) => sum + o.total_cents, 0);

  // --- product form ---

  function openAdd() {
    setForm({ ...emptyForm });
  }

  function openEdit(product) {
    setForm({
      id: product.id,
      name: product.name,
      description: product.description,
      price: (product.price_cents / 100).toString(),
      product_type: product.product_type,
      sizes: product.sizes ?? [...APPAREL_SIZES],
      is_active: product.is_active,
      imageFile: null,
    });
  }

  const formValid = form && form.name.trim() !== "" && form.price.trim() !== "" && !isNaN(parseFloat(form.price));

  async function saveProduct() {
    const payload = {
      name: form.name.trim(),
      description: form.description.trim(),
      price_cents: Math.round(parseFloat(form.price) * 100),
      product_type: form.product_type,
      sizes: form.product_type === "apparel" ? form.sizes : null,
      is_active: form.is_active,
    };
    try {
      const productId = form.id
        ? (await updateProduct(form.id, payload)).data.id
        : (await createProduct(payload)).data.id;
      if (form.imageFile) await uploadProductImage(productId, form.imageFile);
      setForm(null);
      refreshProducts();
      showToast(form.id ? "Product updated" : "Product added");
    } catch (err) {
      showToast(err.response?.data?.detail || "Couldn't save the product");
    }
  }

  async function toggleActive(product) {
    await updateProduct(product.id, { is_active: !product.is_active }).catch(() => {});
    refreshProducts();
  }

  async function removeProduct(product) {
    if (!window.confirm(`Remove "${product.name}" from the shop?`)) return;
    await deleteProduct(product.id).catch(() => {});
    refreshProducts();
    showToast("Product removed");
  }

  // --- orders ---

  async function setOrderStatus(order, status) {
    try {
      await updateShopOrder(order.id, { status });
      refreshOrders();
      showToast(
        status === "ready"
          ? "Marked ready — buyer emailed"
          : status === "picked_up"
            ? "Order completed"
            : "Order cancelled"
      );
    } catch (err) {
      showToast(err.response?.data?.detail || "Couldn't update the order");
    }
  }

  async function saveNote(order) {
    await updateShopOrder(order.id, { notes: noteDrafts[order.id] ?? "" }).catch(() => {});
    refreshOrders();
    showToast("Note saved");
  }

  async function markAllRead() {
    await Promise.all(unread.map((n) => markNotificationRead(n.id).catch(() => {})));
    refreshNotifications();
  }

  const visibleOrders = orders.filter((o) => orderFilter === "all" || o.status === orderFilter);

  const tabs = [
    { key: "overview", label: "Overview" },
    { key: "products", label: "Products" },
    { key: "orders", label: "Orders" },
    { key: "notifications", label: "Notifications", badge: unread.length },
    { key: "settings", label: "Settings" },
  ];

  return (
    <div
      style={{
        border: "1px solid var(--border)",
        borderRadius: "16px",
        background: "#fff",
        boxShadow: "var(--shadow-card)",
        marginBottom: "24px",
        overflow: "hidden",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", padding: "20px 24px 0", flexWrap: "wrap" }}>
        <h2 style={{ margin: 0, fontSize: "18px", fontWeight: 700, color: "var(--shpe-blue)" }}>Shop Manager</h2>
        <span style={{ fontSize: "12px", color: "var(--muted-soft)" }}>Comms Director · Marketing</span>
      </div>

      {/* Tab bar */}
      <div style={{ display: "flex", gap: "4px", padding: "14px 24px 0", borderBottom: "1px solid var(--border)", flexWrap: "wrap" }}>
        {tabs.map((t) => {
          const active = tab === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              style={{
                position: "relative",
                border: "none",
                background: "transparent",
                padding: "10px 14px 14px",
                fontSize: "14px",
                fontWeight: active ? 700 : 600,
                color: active ? "var(--shpe-blue)" : "var(--muted)",
                cursor: "pointer",
              }}
            >
              {t.label}
              {t.badge > 0 && (
                <span
                  style={{
                    marginLeft: "7px",
                    background: active ? "var(--shpe-red)" : "var(--surface-soft)",
                    color: active ? "#fff" : "var(--muted)",
                    borderRadius: "999px",
                    padding: "1px 7px",
                    fontSize: "11px",
                  }}
                >
                  {t.badge}
                </span>
              )}
              {active && (
                <span style={{ position: "absolute", left: "8px", right: "8px", bottom: 0, height: "2px", background: "var(--shpe-blue)", borderRadius: "999px" }} />
              )}
            </button>
          );
        })}
      </div>

      <div style={{ padding: "24px" }}>
        {/* OVERVIEW */}
        {tab === "overview" && (
          <>
            <p style={{ margin: "0 0 16px", fontSize: "15px", color: "var(--ink-soft)" }}>
              Right now:{" "}
              <strong style={{ color: "var(--ink)" }}>
                {counts.paid} paid · {counts.ready} ready for pickup · {counts.picked_up} picked up
              </strong>
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "14px" }}>
              <StatTile value={counts.paid} label="Paid · need prep" color="var(--status-paid-text)" />
              <StatTile value={counts.ready} label="Ready for pickup" color="var(--status-ready-text)" />
              <StatTile value={counts.picked_up} label="Picked up" color="var(--status-picked-text)" />
              <StatTile value={formatCents(collectedCents)} label="Collected" color="var(--shpe-blue)" />
            </div>
          </>
        )}

        {/* PRODUCTS */}
        {tab === "products" && (
          <>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", marginBottom: "16px", flexWrap: "wrap" }}>
              <p style={{ margin: 0, fontSize: "14px", color: "var(--muted)" }}>
                Manage what's on the shelf. Toggle availability or edit details anytime.
              </p>
              <button
                className="primaryBtn"
                onClick={openAdd}
                style={{ display: "inline-flex", alignItems: "center", gap: "8px", padding: "9px 18px", fontSize: "14px" }}
              >
                <PlusIcon size={16} strokeWidth={2.2} />
                Add product
              </button>
            </div>
            <div style={{ border: "1px solid var(--border)", borderRadius: "12px", overflowX: "auto" }}>
              <div style={{ ...productRow, background: "var(--surface-muted)", borderBottom: "1px solid var(--border)", fontSize: "11px", fontWeight: 700, letterSpacing: ".04em", textTransform: "uppercase", color: "var(--muted-soft)" }}>
                <span />
                <span>Product</span>
                <span>Type</span>
                <span>Price</span>
                <span>Status</span>
                <span style={{ textAlign: "right" }}>Edit</span>
              </div>
              {products.map((p) => (
                <div key={p.id} style={{ ...productRow, borderBottom: "1px solid var(--surface-soft)" }}>
                  <div
                    style={{
                      width: "40px",
                      height: "40px",
                      borderRadius: "8px",
                      border: "1px solid var(--border)",
                      background: productImageUrl(p) ? `center/cover url(${productImageUrl(p)})` : "var(--placeholder-hatch)",
                    }}
                  />
                  <div style={{ minWidth: 0 }}>
                    <p style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "var(--ink)", lineHeight: 1.25 }}>{p.name}</p>
                    <p style={{ margin: "2px 0 0", fontSize: "12px", color: "var(--muted-soft)" }}>
                      {p.product_type === "apparel" ? (p.sizes ?? []).join(" · ") : "No sizes"}
                    </p>
                  </div>
                  <span style={{ fontSize: "13px", color: "var(--ink-soft)" }}>{typeLabel(p.product_type)}</span>
                  <span style={{ fontSize: "14px", fontWeight: 700, color: "var(--shpe-blue)" }}>{formatCents(p.price_cents)}</span>
                  <div>
                    <button
                      onClick={() => toggleActive(p)}
                      style={{
                        borderRadius: "999px",
                        padding: "4px 11px",
                        fontSize: "11px",
                        fontWeight: 700,
                        cursor: "pointer",
                        color: p.is_active ? "var(--status-picked-text)" : "var(--status-cancelled-text)",
                        background: p.is_active ? "var(--status-picked-bg)" : "var(--status-cancelled-bg)",
                        border: p.is_active ? "1px solid var(--status-picked-border)" : "1px solid var(--status-cancelled-border)",
                      }}
                    >
                      {p.is_active ? "Active" : "Sold out"}
                    </button>
                  </div>
                  <div style={{ display: "flex", gap: "6px", justifyContent: "flex-end" }}>
                    <button onClick={() => openEdit(p)} aria-label="Edit" style={iconBtn}>
                      <PencilIcon size={15} />
                    </button>
                    <button onClick={() => removeProduct(p)} aria-label="Remove" style={{ ...iconBtn, border: "1px solid #F3D6CC", color: "var(--shpe-red)" }}>
                      <TrashIcon size={15} />
                    </button>
                  </div>
                </div>
              ))}
              {products.length === 0 && (
                <div style={{ padding: "32px", textAlign: "center", color: "var(--muted)", fontSize: "14px" }}>
                  No products yet — add the first one.
                </div>
              )}
            </div>
          </>
        )}

        {/* ORDERS */}
        {tab === "orders" && (
          <>
            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "18px" }}>
              {[
                { key: "all", label: "All" },
                { key: "paid", label: "Paid" },
                { key: "ready", label: "Ready" },
                { key: "picked_up", label: "Picked up" },
                { key: "cancelled", label: "Cancelled" },
              ].map((f) => {
                const active = orderFilter === f.key;
                return (
                  <button
                    key={f.key}
                    onClick={() => setOrderFilter(f.key)}
                    style={{
                      borderRadius: "999px",
                      padding: "7px 14px",
                      fontSize: "13px",
                      fontWeight: active ? 700 : 600,
                      border: active ? "1px solid var(--shpe-blue)" : "1px solid var(--border)",
                      background: active ? "var(--shpe-blue)" : "#fff",
                      color: active ? "#fff" : "var(--ink-soft)",
                      cursor: "pointer",
                    }}
                  >
                    {f.label}{" "}
                    <span style={{ opacity: active ? 0.7 : 1, color: active ? undefined : "var(--muted-soft)" }}>
                      {counts[f.key]}
                    </span>
                  </button>
                );
              })}
            </div>

            {visibleOrders.length === 0 && (
              <div style={{ textAlign: "center", padding: "40px", color: "var(--muted)", fontSize: "14px" }}>
                No orders in this view.
              </div>
            )}

            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {visibleOrders.map((order) => {
                const expanded = expandedId === order.id;
                return (
                  <div key={order.id} style={{ border: "1px solid var(--border)", borderRadius: "12px", overflow: "hidden" }}>
                    <div
                      onClick={() => {
                        setExpandedId(expanded ? null : order.id);
                        setNoteDrafts((d) => ({ ...d, [order.id]: d[order.id] ?? order.notes ?? "" }));
                      }}
                      style={{ display: "flex", alignItems: "center", gap: "14px", padding: "14px 16px", cursor: "pointer", flexWrap: "wrap" }}
                    >
                      <div style={{ flex: 1, minWidth: "200px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "3px" }}>
                          <span style={{ fontSize: "14px", fontWeight: 800, color: "var(--shpe-blue)", fontFamily: "var(--font-mono)" }}>
                            {order.order_code}
                          </span>
                          <StatusPill status={order.status} />
                        </div>
                        <p style={{ margin: 0, fontSize: "13px", fontWeight: 700, color: "var(--ink)" }}>{order.buyer_name}</p>
                        <p style={{ margin: "2px 0 0", fontSize: "12px", color: "var(--muted)" }}>
                          {orderItemsSummary(order.items)}
                        </p>
                      </div>
                      <div style={{ textAlign: "right" }}>
                        <p style={{ margin: 0, fontSize: "15px", fontWeight: 800, color: "var(--ink)" }}>{formatCents(order.total_cents)}</p>
                        <p style={{ margin: "2px 0 0", fontSize: "12px", color: "var(--muted-soft)" }}>
                          Placed {formatOrderDate(order.created_at)}
                        </p>
                      </div>
                      <ChevronDownIcon size={18} stroke="var(--muted-soft)" style={{ transform: expanded ? "rotate(180deg)" : "none" }} />
                    </div>

                    {expanded && (
                      <div style={{ borderTop: "1px solid var(--border)", background: "var(--surface-muted)", padding: "18px" }}>
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "20px", marginBottom: "16px" }}>
                          <div>
                            <p style={sectionLabel}>Buyer & contact</p>
                            <p style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "var(--ink)" }}>{order.buyer_name}</p>
                            <p style={{ margin: "3px 0 0", fontSize: "13px", color: "var(--muted)" }}>
                              {order.buyer_email}
                              {order.buyer_phone ? ` · ${order.buyer_phone}` : ""}
                            </p>
                          </div>
                          <div>
                            <p style={sectionLabel}>Items</p>
                            {order.items.map((item, i) => (
                              <div key={i} style={{ display: "flex", justifyContent: "space-between", gap: "10px", fontSize: "13px", color: "var(--ink-soft)", marginBottom: "2px" }}>
                                <span>
                                  {item.quantity}× {item.product_name}
                                  {item.size ? ` (${item.size})` : ""}
                                </span>
                                <span style={{ fontWeight: 700, color: "var(--ink)" }}>
                                  {formatCents(item.unit_price_cents * item.quantity)}
                                </span>
                              </div>
                            ))}
                            <div style={{ display: "flex", justifyContent: "space-between", gap: "10px", fontSize: "13px", fontWeight: 800, color: "var(--shpe-blue)", borderTop: "1px solid var(--border)", marginTop: "6px", paddingTop: "6px" }}>
                              <span>Total</span>
                              <span>{formatCents(order.total_cents)}</span>
                            </div>
                          </div>
                        </div>

                        <div style={{ marginBottom: "14px" }}>
                          <p style={{ ...sectionLabel, marginBottom: "6px" }}>Internal note</p>
                          <div style={{ display: "flex", gap: "8px" }}>
                            <input
                              className="shopInput"
                              style={{ flex: 1, padding: "10px 12px", fontSize: "13px" }}
                              value={noteDrafts[order.id] ?? ""}
                              onChange={(e) => setNoteDrafts((d) => ({ ...d, [order.id]: e.target.value }))}
                              placeholder="Add a note (e.g. picked up by roommate)"
                            />
                            <button
                              onClick={() => saveNote(order)}
                              style={{ borderRadius: "10px", padding: "0 16px", fontSize: "13px", fontWeight: 700, border: "1px solid var(--border-strong)", background: "#fff", color: "var(--shpe-blue)", cursor: "pointer" }}
                            >
                              Save
                            </button>
                          </div>
                        </div>

                        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
                          {order.status === "paid" && (
                            <button className="primaryBtn" style={{ padding: "9px 16px", fontSize: "13px" }} onClick={() => setOrderStatus(order, "ready")}>
                              Mark ready for pickup →
                            </button>
                          )}
                          {order.status === "ready" && (
                            <button
                              style={{ borderRadius: "999px", padding: "9px 16px", fontSize: "13px", fontWeight: 700, border: "1px solid var(--success-deep)", background: "var(--success-deep)", color: "#fff", cursor: "pointer" }}
                              onClick={() => setOrderStatus(order, "picked_up")}
                            >
                              Mark picked up →
                            </button>
                          )}
                          {(order.status === "paid" || order.status === "ready") && (
                            <button
                              style={{ borderRadius: "999px", padding: "9px 16px", fontSize: "13px", fontWeight: 700, border: "1px solid #F3D6CC", background: "#fff", color: "var(--shpe-red)", cursor: "pointer" }}
                              onClick={() => setOrderStatus(order, "cancelled")}
                            >
                              Cancel order
                            </button>
                          )}
                          {order.status === "picked_up" && (
                            <span style={{ display: "inline-flex", alignItems: "center", gap: "7px", fontSize: "13px", fontWeight: 700, color: "var(--success-deep)" }}>
                              <CheckIcon size={15} />
                              Completed — picked up
                            </span>
                          )}
                          {order.status === "cancelled" && (
                            <span style={{ fontSize: "13px", fontWeight: 700, color: "var(--muted)" }}>
                              This order was cancelled.
                            </span>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </>
        )}

        {/* NOTIFICATIONS */}
        {tab === "notifications" && (
          <>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", marginBottom: "16px" }}>
              <p style={{ margin: 0, fontSize: "14px", color: "var(--muted)" }}>
                New-order alerts. Click an unread alert to mark it read.
              </p>
              {unread.length > 0 && (
                <button
                  onClick={markAllRead}
                  style={{ borderRadius: "999px", padding: "7px 14px", fontSize: "13px", fontWeight: 700, border: "1px solid var(--border-strong)", background: "#fff", color: "var(--shpe-blue)", cursor: "pointer", whiteSpace: "nowrap" }}
                >
                  Mark all read ({unread.length})
                </button>
              )}
            </div>
            {notifications.length === 0 && (
              <div style={{ textAlign: "center", padding: "32px", color: "var(--muted)", fontSize: "14px" }}>
                No notifications yet.
              </div>
            )}
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {notifications.map((n) =>
                n.is_read ? (
                  <div key={n.id} style={{ border: "1px solid var(--border)", borderLeft: "4px solid var(--border)", borderRadius: "10px", padding: "12px 16px", background: "#fff", display: "flex", justifyContent: "space-between", gap: "12px", alignItems: "flex-start" }}>
                    <p style={{ margin: 0, fontSize: "14px", color: "var(--muted)" }}>{n.body}</p>
                    <span style={notifTime}>{formatOrderDate(n.created_at)}</span>
                  </div>
                ) : (
                  <div
                    key={n.id}
                    onClick={() => markNotificationRead(n.id).then(refreshNotifications).catch(() => {})}
                    style={{ border: "1px solid var(--info-border)", borderLeft: "4px solid var(--shpe-blue-bright)", borderRadius: "10px", padding: "12px 16px", background: "var(--surface-tint)", cursor: "pointer", display: "flex", justifyContent: "space-between", gap: "12px", alignItems: "flex-start" }}
                  >
                    <div style={{ display: "flex", gap: "10px", alignItems: "flex-start" }}>
                      <span style={{ width: "8px", height: "8px", borderRadius: "999px", background: "var(--shpe-blue-bright)", marginTop: "5px", flexShrink: 0 }} />
                      <p style={{ margin: 0, fontSize: "14px", fontWeight: 600, color: "var(--ink)" }}>{n.body}</p>
                    </div>
                    <span style={notifTime}>{formatOrderDate(n.created_at)}</span>
                  </div>
                )
              )}
            </div>
          </>
        )}
        {/* SETTINGS */}
        {tab === "settings" && (
          <div style={{ maxWidth: "560px", display: "flex", flexDirection: "column", gap: "16px" }}>
            <p style={{ margin: 0, fontSize: "14px", color: "var(--muted)" }}>
              Storefront copy and order limits — changes apply immediately.
            </p>
            <label style={formLabel}>
              Storefront tagline
              <textarea
                className="shopInput"
                rows={2}
                value={settingsDraft.tagline}
                onChange={(e) => setSettingsDraft({ ...settingsDraft, tagline: e.target.value })}
                placeholder="Shown under the shop hero heading"
                style={{ resize: "vertical" }}
              />
            </label>
            <label style={{ ...formLabel, maxWidth: "220px" }}>
              Max units per item per order
              <input
                className="shopInput"
                inputMode="numeric"
                value={settingsDraft.order_item_cap}
                onChange={(e) => setSettingsDraft({ ...settingsDraft, order_item_cap: e.target.value })}
                placeholder="5"
              />
            </label>
            <button
              className="primaryBtn"
              disabled={!settingsValid}
              onClick={saveSettings}
              style={{ alignSelf: "flex-start", padding: "10px 22px", fontSize: "14px" }}
            >
              Save settings
            </button>
          </div>
        )}
      </div>

      {/* Add/Edit product modal */}
      {form && (
        <div
          style={{ position: "fixed", inset: 0, background: "rgba(3,10,30,.45)", zIndex: 3200, display: "flex", alignItems: "flex-start", justifyContent: "center", padding: "40px 16px", overflowY: "auto", animation: "shopFadeIn .2s ease" }}
          onClick={() => setForm(null)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{ width: "540px", maxWidth: "100%", background: "#fff", borderRadius: "18px", boxShadow: "var(--shadow-modal)", animation: "shopRiseIn .25s ease" }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "20px 24px", borderBottom: "1px solid var(--border)" }}>
              <h3 style={{ margin: 0, fontSize: "18px", fontWeight: 800, color: "var(--ink)" }}>
                {form.id ? "Edit product" : "Add product"}
              </h3>
              <button
                onClick={() => setForm(null)}
                aria-label="Close"
                style={{ width: "32px", height: "32px", borderRadius: "999px", border: "none", background: "var(--surface-soft)", color: "var(--ink-soft)", cursor: "pointer", display: "grid", placeItems: "center" }}
              >
                <CloseIcon size={16} />
              </button>
            </div>

            <div style={{ padding: "22px 24px", display: "flex", flexDirection: "column", gap: "16px" }}>
              <label style={formLabel}>
                Name
                <input className="shopInput" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. SHPE UH Quarter-Zip" />
              </label>
              <label style={formLabel}>
                Description
                <textarea
                  className="shopInput"
                  rows={3}
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="Short description buyers will see"
                  style={{ resize: "vertical" }}
                />
              </label>
              <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
                <label style={{ ...formLabel, flex: 1, minWidth: "120px" }}>
                  Price (USD)
                  <input className="shopInput" inputMode="decimal" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} placeholder="45" />
                </label>
                <div style={{ ...formLabel, flex: 1, minWidth: "170px" }}>
                  Product type
                  <div style={{ display: "flex", gap: "8px" }}>
                    {[
                      { value: "apparel", label: "Apparel" },
                      { value: "item", label: "Sticker / item" },
                    ].map((t) => {
                      const active = form.product_type === t.value;
                      return (
                        <button
                          key={t.value}
                          onClick={() => setForm({ ...form, product_type: t.value })}
                          style={{
                            flex: 1,
                            borderRadius: "10px",
                            padding: "10px",
                            fontSize: "13px",
                            fontWeight: active ? 700 : 600,
                            border: active ? "1.5px solid var(--shpe-blue)" : "1.5px solid var(--border)",
                            background: active ? "var(--surface-tint)" : "#fff",
                            color: active ? "var(--shpe-blue)" : "var(--ink-soft)",
                            cursor: "pointer",
                          }}
                        >
                          {t.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>

              {form.product_type === "apparel" && (
                <div style={formLabel}>
                  Available sizes
                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    {APPAREL_SIZES.map((sz) => {
                      const active = form.sizes.includes(sz);
                      return (
                        <button
                          key={sz}
                          onClick={() =>
                            setForm({
                              ...form,
                              sizes: active ? form.sizes.filter((s) => s !== sz) : [...form.sizes, sz],
                            })
                          }
                          style={{
                            minWidth: "46px",
                            borderRadius: "9px",
                            padding: "8px 10px",
                            fontSize: "13px",
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

              <div style={formLabel}>
                Product image
                <div
                  onClick={() => fileInputRef.current?.click()}
                  style={{ border: "1.5px dashed #CBD5E4", borderRadius: "12px", padding: "22px", textAlign: "center", background: "var(--surface-muted)", cursor: "pointer" }}
                >
                  <ImageIcon size={24} stroke="var(--muted-soft)" style={{ marginBottom: "6px" }} />
                  <p style={{ margin: 0, fontSize: "13px", color: "var(--muted)", fontWeight: 400 }}>
                    {form.imageFile ? (
                      <strong style={{ color: "var(--shpe-blue)" }}>{form.imageFile.name}</strong>
                    ) : (
                      <>
                        <strong style={{ color: "var(--shpe-blue)" }}>Upload an image</strong> · PNG, JPG, WebP
                      </>
                    )}
                  </p>
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={(e) => setForm({ ...form, imageFile: e.target.files?.[0] ?? null })}
                  style={{ display: "none" }}
                />
              </div>

              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", border: "1px solid var(--border)", borderRadius: "10px", padding: "12px 14px" }}>
                <div>
                  <p style={{ margin: 0, fontSize: "13px", fontWeight: 700, color: "var(--ink)" }}>Availability</p>
                  <p style={{ margin: "2px 0 0", fontSize: "12px", color: "var(--muted)" }}>
                    {form.is_active ? "Visible in the shop" : "Hidden — shows as sold out"}
                  </p>
                </div>
                <button
                  onClick={() => setForm({ ...form, is_active: !form.is_active })}
                  aria-label="Toggle availability"
                  style={{ width: "46px", height: "26px", borderRadius: "999px", border: "none", background: form.is_active ? "var(--shpe-blue)" : "var(--border-strong)", cursor: "pointer", position: "relative", flexShrink: 0 }}
                >
                  <span style={{ position: "absolute", top: "3px", [form.is_active ? "right" : "left"]: "3px", width: "20px", height: "20px", borderRadius: "999px", background: "#fff" }} />
                </button>
              </div>
            </div>

            <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end", padding: "16px 24px", borderTop: "1px solid var(--border)" }}>
              <button
                onClick={() => setForm(null)}
                style={{ borderRadius: "999px", padding: "10px 20px", fontSize: "14px", fontWeight: 700, border: "1px solid var(--border-strong)", background: "#fff", color: "var(--ink)", cursor: "pointer" }}
              >
                Cancel
              </button>
              <button
                className="primaryBtn"
                disabled={!formValid}
                onClick={saveProduct}
                style={{ padding: "10px 22px", fontSize: "14px" }}
              >
                Save product
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StatTile({ value, label, color }) {
  return (
    <div style={{ border: "1px solid var(--border)", borderRadius: "14px", padding: "18px 20px", background: "#fff" }}>
      <p style={{ margin: 0, fontSize: "30px", fontWeight: 800, lineHeight: 1, color }}>{value}</p>
      <p style={{ margin: "8px 0 0", fontSize: "12px", fontWeight: 600, color: "var(--muted)" }}>{label}</p>
    </div>
  );
}

const productRow = {
  display: "grid",
  gridTemplateColumns: "44px minmax(160px, 1fr) 84px 66px 92px 78px",
  gap: "12px",
  alignItems: "center",
  padding: "12px 16px",
  minWidth: "560px",
};

const iconBtn = {
  width: "32px",
  height: "32px",
  borderRadius: "8px",
  border: "1px solid var(--border)",
  background: "#fff",
  color: "var(--ink-soft)",
  cursor: "pointer",
  display: "grid",
  placeItems: "center",
};

const sectionLabel = {
  margin: "0 0 6px",
  fontSize: "11px",
  fontWeight: 700,
  letterSpacing: ".05em",
  textTransform: "uppercase",
  color: "var(--muted-soft)",
};

const notifTime = {
  fontSize: "11px",
  color: "var(--muted-soft)",
  whiteSpace: "nowrap",
};

const formLabel = {
  display: "flex",
  flexDirection: "column",
  gap: "6px",
  fontSize: "12px",
  fontWeight: 700,
  color: "var(--ink-soft)",
};
