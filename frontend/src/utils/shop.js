// Shared shop helpers — money formatting, status pill styling, role checks.

export function formatCents(cents) {
  return `$${(cents / 100).toFixed(2)}`;
}

// Shop admin rides on these roles (matches SHOP_ADMIN_ROLES on the backend) —
// there is no dedicated shop-manager role. The president holds every admin
// privilege on the site, shop included.
export const SHOP_ADMIN_ROLES = ["Communication Director", "Marketing Chair", "President"];

export function isShopManager(user) {
  return SHOP_ADMIN_ROLES.includes(user?.role);
}

// President-only surfaces (the /members directory, role assignment).
export const PRESIDENT_ROLE = "President";

export function isPresident(user) {
  return user?.role === PRESIDENT_ROLE;
}

// Who can reach the members directory and assign roles (matches
// ROLE_ADMIN_ROLES on the backend). VPs can assign every role except
// President, and can't change the sitting president — the backend enforces
// both; the UI just avoids offering picks that would 403.
export const ROLE_ADMIN_ROLES = [
  PRESIDENT_ROLE,
  "Vice President External",
  "Vice President Internal",
];

export function canAssignRoles(user) {
  return ROLE_ADMIN_ROLES.includes(user?.role);
}

// Order-status pill styling — tokens defined in styles.css §Shop.
export const STATUS_META = {
  paid: {
    label: "Paid",
    color: "var(--status-paid-text)",
    bg: "var(--status-paid-bg)",
    border: "var(--status-paid-border)",
  },
  ready: {
    label: "Ready for pickup",
    color: "var(--status-ready-text)",
    bg: "var(--status-ready-bg)",
    border: "var(--status-ready-border)",
  },
  picked_up: {
    label: "Picked up",
    color: "var(--status-picked-text)",
    bg: "var(--status-picked-bg)",
    border: "var(--status-picked-border)",
  },
  cancelled: {
    label: "Cancelled",
    color: "var(--status-cancelled-text)",
    bg: "var(--status-cancelled-bg)",
    border: "var(--status-cancelled-border)",
  },
};

// Product-type eyebrow label ("Apparel" / "Item") — derived from data, never hardcoded pills.
export function typeLabel(productType) {
  return productType === "apparel" ? "Apparel" : "Item";
}

// Backend stores naive UTC; append Z so the browser reads it as UTC.
export function formatOrderDate(isoString) {
  return new Date(isoString + "Z").toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function orderItemsSummary(items) {
  return items
    .map((it) => `${it.quantity}× ${it.product_name}${it.size ? ` (${it.size})` : ""}`)
    .join(" · ");
}
