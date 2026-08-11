import { createContext, useContext, useEffect, useRef, useState } from "react";
import { getShopProducts, getShopSettings } from "../api/api";
import { useAuth } from "./AuthContext";
import { DUES_PRODUCT_NAME } from "../utils/dues";
import { changeKey, mergeChanges, reconcileCartLines } from "../utils/shop";

// Cart state shared across the app: line items (persisted to localStorage so
// guests keep their cart across navigation), the drawer open state, the shop
// toast, and the per-order item cap from shop settings. Lines merge by
// product + size.
const CartContext = createContext(null);

const STORAGE_KEY = "shpe_cart";
const DEFAULT_ITEM_CAP = 5;

function loadCart() {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY));
    return Array.isArray(stored) ? stored : [];
  } catch {
    return [];
  }
}

function lineKey(productId, size) {
  return `${productId}|${size ?? ""}`;
}

export function CartProvider({ children }) {
  // Safe because main.jsx nests CartProvider inside AuthProvider. Used only
  // for the dues one-per-member guard in addItem.
  const { user } = useAuth();
  const [lines, setLines] = useState(loadCart);
  const [isOpen, setIsOpen] = useState(false);
  const [toast, setToast] = useState(null);
  const [itemCap, setItemCap] = useState(DEFAULT_ITEM_CAP);

  // Re-pricing state. Deliberately NOT persisted alongside the cart: a stale
  // "unavailable" flag would survive a restock, and localStorage lines get no
  // shape validation in loadCart, so carts already in members' browsers keep
  // working untouched.
  const [priceChanges, setPriceChanges] = useState([]);
  const [unavailableLines, setUnavailableLines] = useState([]);
  const [repriceState, setRepriceState] = useState("idle"); // idle|loading|done|failed
  const [priceChangesAcked, setPriceChangesAcked] = useState(false);

  // repriceCart reads lines through a ref so it never closes over a stale copy
  // (it's called from effects that shouldn't re-run when the cart changes).
  // Seeded from the first render and kept current by the effect below — writing
  // it during render trips react-hooks/refs.
  const linesRef = useRef(lines);

  useEffect(() => {
    linesRef.current = lines;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(lines));
  }, [lines]);

  // Per-order cap on each line item, editable by shop admins.
  useEffect(() => {
    getShopSettings()
      .then((res) => setItemCap(res.data.order_item_cap))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 2000);
    return () => clearTimeout(timer);
  }, [toast]);

  // T-Shirt Dues are one-per-member — never more than 1 in the cart,
  // regardless of the shop-wide item cap.
  function lineCap(name) {
    return name === DUES_PRODUCT_NAME ? 1 : itemCap;
  }

  function addItem(product, size, qty = 1, { openDrawer = true } = {}) {
    const cap = lineCap(product.name);
    const isDues = product.name === DUES_PRODUCT_NAME;

    // Dues are one per member per membership year, enforced server-side by
    // shop_services.enforce_dues_rules. Guard here too — and centrally rather
    // than per page, because every entry point into the cart needs it: the
    // product page, the storefront, and MyOrders' re-order shortcut, which
    // otherwise happily re-adds a previous dues order.
    if (isDues && user?.has_paid_dues) {
      setToast("You've already paid your dues this year");
      return;
    }

    let capped = false;
    setLines((prev) => {
      const key = lineKey(product.id, size);
      const existing = prev.find((l) => lineKey(l.productId, l.size) === key);
      if (existing) {
        const next = Math.min(existing.qty + qty, cap);
        capped = next < existing.qty + qty;
        return prev.map((l) =>
          lineKey(l.productId, l.size) === key ? { ...l, qty: next } : l
        );
      }
      const next = Math.min(qty, cap);
      capped = next < qty;
      return [
        ...prev,
        {
          productId: product.id,
          name: product.name,
          priceCents: product.price_cents,
          productType: product.product_type,
          size: size ?? null,
          qty: next,
        },
      ];
    });
    if (openDrawer) setIsOpen(true);
    setToast(
      capped
        ? isDues
          ? "You can only buy dues once"
          : `Limit ${itemCap} per item`
        : "Added to cart"
    );
  }

  // delta of -1/+1 from the steppers; a line hitting 0 is removed, and
  // quantity never exceeds the line's cap (1 for dues, else the item cap).
  function changeQty(productId, size, delta) {
    setLines((prev) =>
      prev
        .map((l) =>
          lineKey(l.productId, l.size) === lineKey(productId, size)
            ? { ...l, qty: Math.min(l.qty + delta, lineCap(l.name)) }
            : l
        )
        .filter((l) => l.qty > 0)
    );
  }

  function removeLine(productId, size) {
    const key = lineKey(productId, size);
    setLines((prev) => prev.filter((l) => lineKey(l.productId, l.size) !== key));
    // Drop any notice attached to the line that just left the cart.
    setPriceChanges((prev) => prev.filter((c) => changeKey(c.productId, c.size) !== key));
    setUnavailableLines((prev) => prev.filter((u) => changeKey(u.productId, u.size) !== key));
  }

  function clearCart() {
    setLines([]);
    setPriceChanges([]);
    setUnavailableLines([]);
    setPriceChangesAcked(false);
    setRepriceState("idle");
  }

  // Re-match the cart against the live catalog. Called from the surfaces that
  // show money (checkout on mount, the drawer on open) rather than on every
  // CartProvider mount, which would put a request on every page load for every
  // anonymous visitor.
  async function repriceCart() {
    if (linesRef.current.length === 0) return;
    setRepriceState("loading");
    try {
      const { data } = await getShopProducts();
      const result = reconcileCartLines(linesRef.current, data);
      setLines(result.lines); // same reference when nothing moved → no-op
      if (result.changes.length > 0) {
        setPriceChanges((prev) => mergeChanges(prev, result.changes));
        setPriceChangesAcked(false);
      }
      setUnavailableLines(result.unavailable);
      setRepriceState("done");
    } catch {
      // Fail open. The backend recomputes and charges correctly regardless, so
      // a network blip must not take checkout down; "failed" exists only so the
      // Continue button doesn't stay disabled.
      setRepriceState("failed");
    }
  }

  function acknowledgePriceChanges() {
    setPriceChangesAcked(true);
  }

  const count = lines.reduce((n, l) => n + l.qty, 0);

  // Unavailable lines are excluded from the total: they cannot be purchased
  // (checkout blocks Pay until they're removed, and the backend 400s them), so
  // counting them would show a figure that can never be charged — the same
  // display/charge divergence this re-pricing exists to close. Their per-line
  // price is hidden alongside, so the arithmetic still reads correctly.
  const unavailableKeys = new Set(
    unavailableLines.map((u) => changeKey(u.productId, u.size))
  );
  const subtotalCents = lines.reduce(
    (n, l) => (unavailableKeys.has(lineKey(l.productId, l.size)) ? n : n + l.priceCents * l.qty),
    0
  );

  return (
    <CartContext.Provider
      value={{
        lines,
        count,
        subtotalCents,
        itemCap,
        addItem,
        changeQty,
        removeLine,
        clearCart,
        repriceCart,
        priceChanges,
        unavailableLines,
        repriceState,
        priceChangesAcked,
        acknowledgePriceChanges,
        isOpen,
        openCart: () => setIsOpen(true),
        closeCart: () => setIsOpen(false),
        toast,
        showToast: setToast,
      }}
    >
      {children}
    </CartContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useCart() {
  return useContext(CartContext);
}
