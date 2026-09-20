import { useCallback, useEffect, useState } from "react";
import {
  createProduct,
  getAdminProducts,
  getNotifications,
  getShopOrders,
  getShopSettings,
  markNotificationRead,
  restoreProduct,
  retireProduct,
  updateProduct,
  updateShopOrder,
  updateShopSettings,
  uploadProductImage,
} from "../api/api";
import { useCart } from "../context/CartContext";
import usePagination from "../hooks/usePagination";
import ConfirmDialog from "./ConfirmDialog";
import NotificationsTab from "./shop-manager/NotificationsTab";
import OrdersTab from "./shop-manager/OrdersTab";
import OverviewTab from "./shop-manager/OverviewTab";
import ProductFormModal from "./shop-manager/ProductFormModal";
import ProductsTab from "./shop-manager/ProductsTab";
import SettingsTab from "./shop-manager/SettingsTab";
import { emptyProductForm } from "./shop-manager/productFormConstants";

const TABS = ["overview", "products", "orders", "notifications", "settings"];

export default function ShopManager() {
  const { showToast } = useCart();
  const [tab, setTab] = useState("overview");
  const [products, setProducts] = useState([]);
  const [orders, setOrders] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [orderFilter, setOrderFilter] = useState("all");
  const [expandedId, setExpandedId] = useState(null);
  const [noteDrafts, setNoteDrafts] = useState({});
  const [form, setForm] = useState(null);
  const [pendingRetire, setPendingRetire] = useState(null);
  const [retiredOpen, setRetiredOpen] = useState(false);
  const [settingsDraft, setSettingsDraft] = useState({
    tagline: "",
    order_item_cap: "",
  });

  const refreshProducts = useCallback(function refreshProducts() {
    return getAdminProducts()
      .then((res) => setProducts(res.data))
      .catch(() => {});
  }, []);
  const refreshOrders = useCallback(function refreshOrders() {
    return getShopOrders()
      .then((res) => setOrders(res.data))
      .catch(() => {});
  }, []);
  const refreshNotifications = useCallback(function refreshNotifications() {
    return getNotifications()
      .then((res) => setNotifications(res.data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    refreshProducts();
    refreshOrders();
    refreshNotifications();
    getShopSettings()
      .then((res) =>
        setSettingsDraft({
          tagline: res.data.tagline,
          order_item_cap: String(res.data.order_item_cap),
        }),
      )
      .catch(() => {});
  }, [refreshNotifications, refreshOrders, refreshProducts]);

  const unread = notifications.filter((item) => !item.is_read);
  const counts = {
    all: orders.length,
    paid: orders.filter((item) => item.status === "paid").length,
    ready: orders.filter((item) => item.status === "ready").length,
    picked_up: orders.filter((item) => item.status === "picked_up").length,
    cancelled: orders.filter((item) => item.status === "cancelled").length,
  };
  const collectedCents = orders
    .filter((item) => item.status !== "cancelled")
    .reduce((sum, item) => sum + item.total_cents, 0);
  const liveProducts = products.filter((item) => item.retired_at == null);
  const retiredProducts = products.filter((item) => item.retired_at != null);
  const visibleOrders = orders.filter(
    (item) => orderFilter === "all" || item.status === orderFilter,
  );

  // Pagination hooks must remain unconditional even though their views are tabbed.
  const liveProductsPager = usePagination(liveProducts);
  const retiredPager = usePagination(retiredProducts);
  const ordersPager = usePagination(visibleOrders, { resetKey: orderFilter });
  const notificationsPager = usePagination(notifications);

  function openEdit(product) {
    setForm({
      id: product.id,
      name: product.name,
      description: product.description,
      price: (product.price_cents / 100).toString(),
      product_type: product.product_type,
      sizes: product.sizes ?? [...emptyProductForm.sizes],
      is_active: product.is_active,
      imageFile: null,
    });
  }

  async function saveProduct() {
    const editing = Boolean(form.id);
    const payload = {
      name: form.name.trim(),
      description: form.description.trim(),
      price_cents: Math.round(parseFloat(form.price) * 100),
      product_type: form.product_type,
      sizes: form.product_type === "apparel" ? form.sizes : null,
      is_active: form.is_active,
    };
    try {
      const productId = editing
        ? (await updateProduct(form.id, payload)).data.id
        : (await createProduct(payload)).data.id;
      if (form.imageFile) await uploadProductImage(productId, form.imageFile);
      setForm(null);
      await refreshProducts();
      showToast(editing ? "Product updated" : "Product added");
    } catch (err) {
      showToast(err.response?.data?.detail || "Couldn't save the product");
    }
  }

  async function toggleActive(product) {
    await updateProduct(product.id, { is_active: !product.is_active }).catch(
      () => {},
    );
    refreshProducts();
  }

  async function retireSelectedProduct() {
    try {
      await retireProduct(pendingRetire.id);
      await refreshProducts();
      showToast("Product retired");
    } catch (err) {
      showToast(err.response?.data?.detail || "Couldn't retire the product");
    } finally {
      setPendingRetire(null);
    }
  }

  async function restoreSelectedProduct(product) {
    try {
      await restoreProduct(product.id);
      await refreshProducts();
      showToast("Product restored — it's hidden until you set it Active");
    } catch (err) {
      showToast(err.response?.data?.detail || "Couldn't restore the product");
    }
  }

  async function setOrderStatus(order, status) {
    try {
      await updateShopOrder(order.id, { status });
      await refreshOrders();
      showToast(
        status === "ready"
          ? "Marked ready — buyer emailed"
          : status === "picked_up"
            ? "Order completed"
            : "Order cancelled",
      );
    } catch (err) {
      showToast(err.response?.data?.detail || "Couldn't update the order");
    }
  }

  async function saveNote(order) {
    await updateShopOrder(order.id, {
      notes: noteDrafts[order.id] ?? "",
    }).catch(() => {});
    refreshOrders();
    showToast("Note saved");
  }

  async function markOneRead(id) {
    await markNotificationRead(id)
      .then(refreshNotifications)
      .catch(() => {});
  }
  async function markAllRead() {
    await Promise.all(
      unread.map((item) => markNotificationRead(item.id).catch(() => {})),
    );
    refreshNotifications();
  }
  async function saveSettings() {
    try {
      await updateShopSettings({
        tagline: settingsDraft.tagline.trim(),
        order_item_cap: parseInt(settingsDraft.order_item_cap, 10),
      });
      showToast("Settings saved");
    } catch (err) {
      showToast(err.response?.data?.detail || "Couldn't save settings");
    }
  }

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
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "12px",
          padding: "20px 24px 0",
          flexWrap: "wrap",
        }}
      >
        <h2
          style={{
            margin: 0,
            fontSize: "18px",
            fontWeight: 700,
            color: "var(--shpe-blue)",
          }}
        >
          Shop Manager
        </h2>
        <span style={{ fontSize: "12px", color: "var(--muted-soft)" }}>
          Comms Director · Marketing
        </span>
      </div>
      <div
        style={{
          display: "flex",
          gap: "4px",
          padding: "14px 24px 0",
          borderBottom: "1px solid var(--border)",
          flexWrap: "wrap",
        }}
      >
        {TABS.map((key) => {
          const active = tab === key;
          const badge = key === "notifications" ? unread.length : 0;
          return (
            <button
              key={key}
              onClick={() => setTab(key)}
              style={{
                position: "relative",
                border: "none",
                background: "transparent",
                padding: "10px 14px 14px",
                fontSize: "14px",
                fontWeight: active ? 700 : 600,
                color: active ? "var(--shpe-blue)" : "var(--muted)",
                cursor: "pointer",
                textTransform: "capitalize",
              }}
            >
              {key}
              {badge > 0 && (
                <span
                  style={{
                    marginLeft: "7px",
                    background: active
                      ? "var(--shpe-red)"
                      : "var(--surface-soft)",
                    color: active ? "#fff" : "var(--muted)",
                    borderRadius: "999px",
                    padding: "1px 7px",
                    fontSize: "11px",
                  }}
                >
                  {badge}
                </span>
              )}
              {active && (
                <span
                  style={{
                    position: "absolute",
                    left: "8px",
                    right: "8px",
                    bottom: 0,
                    height: "2px",
                    background: "var(--shpe-blue)",
                    borderRadius: "999px",
                  }}
                />
              )}
            </button>
          );
        })}
      </div>
      <div style={{ padding: "24px" }}>
        {tab === "overview" && (
          <OverviewTab counts={counts} collectedCents={collectedCents} />
        )}
        {tab === "products" && (
          <ProductsTab
            liveProducts={liveProducts}
            retiredProducts={retiredProducts}
            livePager={liveProductsPager}
            retiredPager={retiredPager}
            retiredOpen={retiredOpen}
            onToggleRetired={() => setRetiredOpen((open) => !open)}
            onAdd={() =>
              setForm({
                ...emptyProductForm,
                sizes: [...emptyProductForm.sizes],
              })
            }
            onEdit={openEdit}
            onToggleActive={toggleActive}
            onRequestRetire={setPendingRetire}
            onRestore={restoreSelectedProduct}
          />
        )}
        {tab === "orders" && (
          <OrdersTab
            counts={counts}
            filter={orderFilter}
            onFilterChange={setOrderFilter}
            orders={visibleOrders}
            pager={ordersPager}
            expandedId={expandedId}
            onExpandedChange={setExpandedId}
            noteDrafts={noteDrafts}
            setNoteDrafts={setNoteDrafts}
            onSaveNote={saveNote}
            onStatusChange={setOrderStatus}
          />
        )}
        {tab === "notifications" && (
          <NotificationsTab
            notifications={notifications}
            unreadCount={unread.length}
            pager={notificationsPager}
            onMarkRead={markOneRead}
            onMarkAllRead={markAllRead}
          />
        )}
        {tab === "settings" && (
          <SettingsTab
            draft={settingsDraft}
            setDraft={setSettingsDraft}
            onSave={saveSettings}
          />
        )}
      </div>
      {pendingRetire && (
        <ConfirmDialog
          title="Retire product?"
          confirmLabel="Retire"
          tone="danger"
          onCancel={() => setPendingRetire(null)}
          onConfirm={retireSelectedProduct}
          body={
            <p style={{ margin: 0 }}>
              Retire <strong>{pendingRetire.name}</strong>? It'll be hidden from
              the shop but stays in your Retired list, and past orders keep
              showing it.
            </p>
          }
        />
      )}
      {form && (
        <ProductFormModal form={form} setForm={setForm} onSave={saveProduct} />
      )}
    </div>
  );
}
