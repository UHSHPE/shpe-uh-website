import axios from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
});

export function loginUser(email, password) {
  const params = new URLSearchParams();
  params.append("username", email);
  params.append("password", password);
  return api.post("/login", params, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
}

export function signupUser(data) {
  return api.post("/signup", data);
}

// Public — no auth headers on either password-reset call
export function requestPasswordReset(email) {
  return api.post("/password-reset/request", { email });
}

export function confirmPasswordReset(token, newPassword) {
  return api.post("/password-reset/confirm", { token, new_password: newPassword });
}

export function getMe(token) {
  return api.get("/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

function authHeaders() {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function getUpcomingEvents(days = 7) {
  return api.get(`/events/upcoming?days=${days}`, { headers: authHeaders() });
}

export function getAllEvents() {
  return api.get("/events");
}

export function getCommittees() {
  return api.get("/committees", { headers: authHeaders() });
}

export function joinCommittee(committeeId) {
  return api.post(`/committees/${committeeId}/join`, {}, { headers: authHeaders() });
}

export function leaveCommittee(committeeId) {
  return api.delete(`/committees/${committeeId}/leave`, { headers: authHeaders() });
}

export function getCommitteeMembers(committeeId) {
  return api.get(`/committees/${committeeId}/members`, { headers: authHeaders() });
}

export function getCommitteeMessages(committeeId) {
  return api.get(`/committees/${committeeId}/messages`, { headers: authHeaders() });
}

export function sendCommitteeMessage(committeeId, body) {
  return api.post(`/committees/${committeeId}/messages`, { body }, { headers: authHeaders() });
}

export function setEventReminder(eventId) {
  return api.post(`/events/${eventId}/remind`, {}, { headers: authHeaders() });
}

export function cancelEventReminder(eventId) {
  return api.delete(`/events/${eventId}/remind`, { headers: authHeaders() });
}

export function getMyReminders() {
  return api.get("/events/reminders/me", { headers: authHeaders() });
}

export function getNotifications() {
  return api.get("/notifications", { headers: authHeaders() });
}

// Resume — let axios set the multipart boundary; don't set Content-Type by hand.
export function uploadResume(file) {
  const formData = new FormData();
  formData.append("file", file);
  return api.post("/me/resume", formData, { headers: authHeaders() });
}

// The bearer token can't ride on an <iframe>/<a href>, so fetch the PDF as a
// blob and open it via URL.createObjectURL on the page.
export function getResumeBlob() {
  return api.get("/me/resume", { headers: authHeaders(), responseType: "blob" });
}

export function deleteResume() {
  return api.delete("/me/resume", { headers: authHeaders() });
}

export function markNotificationRead(notificationId) {
  return api.post(`/notifications/${notificationId}/read`, {}, { headers: authHeaders() });
}

// --- Shop: public storefront (no auth headers) ---

// Tagline + per-order item cap, editable by shop admins.
export function getShopSettings() {
  return api.get("/shop/settings");
}

export function getShopProducts() {
  return api.get("/shop/products");
}

export function getShopProduct(productId) {
  return api.get(`/shop/products/${productId}`);
}

// Public image URL — safe to use directly in an <img src>.
export function productImageUrl(product) {
  return product?.image_filename
    ? `${api.defaults.baseURL}/shop/products/${product.id}/image`
    : null;
}

// Public endpoint, but the token rides along when present so a signed-in
// buyer's order links to their account (guests send no auth header).
export function createShopOrder(payload) {
  return api.post("/shop/orders", payload, { headers: authHeaders() });
}

// Buyer status lookup — requires the order code AND the buyer email.
export function getShopOrder(code, email) {
  return api.get(`/shop/orders/${code}`, { params: { email } });
}

export function getMyShopOrders() {
  return api.get("/shop/orders/me", { headers: authHeaders() });
}

// --- Shop: manager only ---

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
  return api.patch(`/shop/products/${productId}`, data, { headers: authHeaders() });
}

export function deleteProduct(productId) {
  return api.delete(`/shop/products/${productId}`, { headers: authHeaders() });
}

export function uploadProductImage(productId, file) {
  const formData = new FormData();
  formData.append("file", file);
  return api.post(`/shop/products/${productId}/image`, formData, { headers: authHeaders() });
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
