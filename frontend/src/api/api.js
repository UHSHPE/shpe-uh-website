import axios from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
});

// AuthContext registers its own sign-out here so an expired token clears
// React state too, not just localStorage.
let onUnauthorized = null;
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

// On these, a 401 means "wrong credentials", not "your session ended" —
// signing the user out would wipe the error message the sign-in page is
// about to render.
const CREDENTIAL_PATHS = ["/login", "/signup", "/verify-email", "/password-reset"];

// Tokens expire (ACCESS_TOKEN_EXPIRE_MINUTES) and there is no refresh flow,
// so without this an expired session just fails every request in silence.
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const url = err.config?.url ?? "";
    const isCredentialCall = CREDENTIAL_PATHS.some((p) => url.startsWith(p));
    if (err.response?.status === 401 && !isCredentialCall) {
      localStorage.removeItem("token");
      onUnauthorized?.();
    }
    return Promise.reject(err);
  }
);

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

// Public — confirms a signup with the token from the verification email.
// Returns a login token on success (the account is now usable).
export function verifyEmail(token) {
  return api.post("/verify-email", { token });
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

// --- QR attendance & points ---

// Scans a sign-in or sign-out QR code. brought_new_member/new_member_name
// only matter on a sign-in scan (harmless — ignored server-side — on a
// sign-out scan).
export function attendEvent(code, { broughtNewMember, newMemberName } = {}) {
  return api.post(
    "/events/attend",
    {
      code,
      brought_new_member: broughtNewMember ?? false,
      new_member_name: newMemberName ?? null,
    },
    { headers: authHeaders() },
  );
}

// Events the signed-in chair/E-Board member hosts, WITH sign-in/out codes
// (minted on first view). Chair/E-Board only — 403 for a regular member.
export function getMyEvents() {
  return api.get("/events/mine", { headers: authHeaders() });
}

// Every chapter event, read-only — no codes. Same chair/E-Board gate as
// getMyEvents.
export function getAllChairEvents() {
  return api.get("/events/all", { headers: authHeaders() });
}

// Attendance roster for one event — 403 unless the caller hosts it.
export function getEventAttendance(eventId) {
  return api.get(`/events/${eventId}/attendance`, { headers: authHeaders() });
}

// Public, read-only preview of a scanned code — the mobile check-in flow
// shows event name/time/location BEFORE POSTing (POST /events/attend
// records immediately). authHeaders() returns {} when signed out, which
// *is* the optional-auth behavior: a token, when present, additionally
// fills the caller's own signed_in_at/signed_out_at.
export function getAttendPreview(code) {
  return api.get(`/events/code/${code}`, { headers: authHeaders() });
}

// Live scan counter for the QR modal / present view — chair/E-Board only,
// scoped to events they host. Poll this instead of re-fetching getMyEvents,
// which would re-mint codes and ship every hosted event's secrets per poll.
export function getEventScanCount(eventId) {
  return api.get(`/events/${eventId}/scan-count`, { headers: authHeaders() });
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
// The response is cached immutably (see get_product_image), so ?v= carries
// the stored filename: it changes on every upload, which is what makes a
// replaced photo appear immediately instead of being served stale from a
// browser or CDN cache.
export function productImageUrl(product) {
  return product?.image_filename
    ? `${api.defaults.baseURL}/shop/products/${product.id}/image` +
        `?v=${encodeURIComponent(product.image_filename)}`
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

// Soft delete — the product is hidden from the shop but kept in the admin's
// Retired list (nothing is destroyed, so order history stays readable).
export function retireProduct(productId) {
  return api.delete(`/shop/products/${productId}`, { headers: authHeaders() });
}

// Undo a retire. The product comes back hidden until an admin sets it Active.
export function restoreProduct(productId) {
  return api.post(`/shop/products/${productId}/restore`, {}, { headers: authHeaders() });
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

// --- Chapter admin: president only ---

// Member directory. Optional params: { search, paid, role } — the members
// page filters client-side, but the API supports them for direct use.
export function getAdminMembers(params = {}) {
  return api.get("/admin/members", { headers: authHeaders(), params });
}

export function getAdminStats() {
  return api.get("/admin/stats", { headers: authHeaders() });
}

// Every assignable role value (source of truth: the backend Role enum).
export function getAssignableRoles() {
  return api.get("/admin/roles", { headers: authHeaders() });
}

export function updateMemberRole(userId, role) {
  return api.patch(`/admin/members/${userId}/role`, { role }, { headers: authHeaders() });
}

// The chapter reporting tree — organizational only, grants no permissions.
export function getOrgStructure() {
  return api.get("/admin/structure", { headers: authHeaders() });
}

export function setRoleSupervisor(role, supervisorRole) {
  return api.put(
    `/admin/structure/${encodeURIComponent(role)}`,
    { supervisor_role: supervisorRole },
    { headers: authHeaders() },
  );
}
