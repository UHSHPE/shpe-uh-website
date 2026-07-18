import { createContext, useContext, useEffect, useState } from "react";
import { getShopSettings } from "../api/api";
import { DUES_PRODUCT_NAME } from "../utils/dues";

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
  const [lines, setLines] = useState(loadCart);
  const [isOpen, setIsOpen] = useState(false);
  const [toast, setToast] = useState(null);
  const [itemCap, setItemCap] = useState(DEFAULT_ITEM_CAP);

  useEffect(() => {
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
    setLines((prev) =>
      prev.filter((l) => lineKey(l.productId, l.size) !== lineKey(productId, size))
    );
  }

  function clearCart() {
    setLines([]);
  }

  const count = lines.reduce((n, l) => n + l.qty, 0);
  const subtotalCents = lines.reduce((n, l) => n + l.priceCents * l.qty, 0);

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
