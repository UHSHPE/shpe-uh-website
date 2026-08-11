import { getShopProducts } from "../api/api";

// Must match the backend (shop_services.DUES_PRODUCT_NAME) and seed.py —
// the dues product is found by name everywhere it's special-cased.
export const DUES_PRODUCT_NAME = "T-Shirt Dues";

// Put the dues product in the cart (pre-sized when the member's shirt size
// matches) and return the path to send them to: /shop/checkout when the item
// was added, the dues product page when they still need to pick a size, or
// null when the shop/product is unavailable (caller picks the fallback).
export async function startDuesCheckout({ shirtSize, addItem }) {
  let products;
  try {
    products = (await getShopProducts()).data;
  } catch {
    return null;
  }
  const dues = products.find((p) => p.name === DUES_PRODUCT_NAME);
  if (!dues) return null;
  if (shirtSize && dues.sizes?.includes(shirtSize)) {
    addItem(dues, shirtSize, 1, { openDrawer: false });
    return "/shop/checkout";
  }
  return `/shop/${dues.id}`;
}
