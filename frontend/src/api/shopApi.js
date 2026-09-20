import { api, authHeaders } from "./client";

export function getShopSettings() {
  return api.get("/shop/settings");
}

export function getShopProducts() {
  return api.get("/shop/products");
}

export function getShopProduct(productId) {
  return api.get(`/shop/products/${productId}`);
}

export function productImageUrl(product) {
  return product?.image_filename
    ? `${api.defaults.baseURL}/shop/products/${product.id}/image` +
        `?v=${encodeURIComponent(product.image_filename)}`
    : null;
}

// Public endpoint with optional auth so signed-in orders link to the buyer.
export function createShopOrder(payload) {
  return api.post("/shop/orders", payload, { headers: authHeaders() });
}

export function getShopOrder(code, email) {
  return api.get(`/shop/orders/${code}`, { params: { email } });
}

export function getMyShopOrders() {
  return api.get("/shop/orders/me", { headers: authHeaders() });
}

export function updateShopSettings(data) {
  return api.patch("/shop/settings", data, { headers: authHeaders() });
}

export function getAdminProducts() {
  return api.get("/shop/admin/products", { headers: authHeaders() });
}

export function createProduct(data) {
  return api.post("/shop/products", data, { headers: authHeaders() });
}

export function updateProduct(productId, data) {
  return api.patch(`/shop/products/${productId}`, data, {
    headers: authHeaders(),
  });
}

export function retireProduct(productId) {
  return api.delete(`/shop/products/${productId}`, { headers: authHeaders() });
}

export function restoreProduct(productId) {
  return api.post(
    `/shop/products/${productId}/restore`,
    {},
    { headers: authHeaders() },
  );
}

export function uploadProductImage(productId, file) {
  const formData = new FormData();
  formData.append("file", file);
  return api.post(`/shop/products/${productId}/image`, formData, {
    headers: authHeaders(),
  });
}

export function getShopOrders(status) {
  return api.get("/shop/orders", {
    headers: authHeaders(),
    params: status ? { status } : {},
  });
}

export function updateShopOrder(orderId, data) {
  return api.patch(`/shop/orders/${orderId}`, data, { headers: authHeaders() });
}
