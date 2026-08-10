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

// Org tiers, mirroring user_enums.py. Display values, because that's what the
// API returns — SQLite stores the enum *name* ("academic_chair"), so these
// strings only ever match API payloads, never raw database rows.
export const VP_ROLE_NAMES = ["Vice President External", "Vice President Internal"];

// Only the president may assign or modify these.
export const TOP_TIER_ROLES = [PRESIDENT_ROLE, ...VP_ROLE_NAMES];

export const OFFICER_ROLES = [
  "Treasurer",
  "Secretary",
  "Communication Director",
  "Regional Representative",
  "New Member Representative",
  "Director Of Internal Affairs",
];

// The 9 the About page calls the E-Board.
export const EBOARD_ROLES = [...TOP_TIER_ROLES, ...OFFICER_ROLES];

export function isEboardRole(role) {
  return EBOARD_ROLES.includes(role);
}

// The 14 chairs. Listed rather than sniffed by suffix so a future
// role like "Vice Chair" can't silently join the set.
export const CHAIR_ROLES = [
  "Marketing Chair",
  "MentorSHPE Chair",
  "Academic Chair",
  "Professional Chair",
  "Career Fair Chair",
  "Web Development Chair",
  "Social Chair",
  "SHPE Jr Chair",
  "Outreach Chair",
  "Engineering Events Coordinator Chair",
  "SHPEtina Chair",
  "Athletic Chair",
  "Projects Chair",
  "Member Relations Chair",
];

export function isChairRole(role) {
  return CHAIR_ROLES.includes(role);
}

// Whole-user versions of isChairRole/isEboardRole, mirroring
// isPresident(user)/isShopManager(user) — gates the My Events page (QR
// attendance & points) the way shop-manager.jsx gates on isShopManager.
export function isChair(user) {
  return isChairRole(user?.role);
}

export function isEboard(user) {
  return isEboardRole(user?.role);
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

// --- Cart re-pricing -------------------------------------------------------
// Cart lines snapshot priceCents at add-to-cart time and persist to
// localStorage, but the backend recomputes the total from live catalog rows and
// charges THAT. Without a reconcile, a buyer can approve one amount (including
// in the Apple/Google Pay sheet) and be charged another. These are pure so the
// context can stay a component file — see the react-refresh lint rule.

export function changeKey(productId, size) {
  return `${productId}|${size ?? ""}`;
}

// Match cart lines against the live catalog. Returns refreshed lines plus what
// moved, so the caller can tell the buyer before they pay.
export function reconcileCartLines(lines, products) {
  const byId = new Map(products.map((p) => [p.id, p]));
  const changes = [];
  const unavailable = [];
  let dirty = false;

  const next = lines.map((line) => {
    const product = byId.get(line.productId);

    // GET /shop/products returns only is_active && !retired products, so a
    // line missing from the response is exactly the condition the backend
    // 400s on with "One of the products is unavailable."
    if (!product) {
      unavailable.push({
        productId: line.productId,
        size: line.size,
        name: line.name,
        reason: "gone",
      });
      return line;
    }

    // A size can disappear from product.sizes while it sits in a cart; the
    // backend rejects that too, so catch it here rather than after the POST.
    if (
      product.product_type === "apparel" &&
      (!line.size || !(product.sizes || []).includes(line.size))
    ) {
      unavailable.push({
        productId: line.productId,
        size: line.size,
        name: product.name,
        reason: "size",
      });
      return line;
    }

    if (product.price_cents === line.priceCents && product.name === line.name) {
      return line;
    }
    if (product.price_cents !== line.priceCents) {
      changes.push({
        productId: line.productId,
        size: line.size,
        name: product.name,
        fromCents: line.priceCents,
        toCents: product.price_cents,
      });
    }
    dirty = true;
    // name is refreshed alongside the price: lineCap() and the dues guard both
    // key off it by string.
    return { ...line, priceCents: product.price_cents, name: product.name };
  });

  // Same array reference when nothing moved. Load-bearing: shop-checkout's
  // Square effect depends on subtotalCents, and a needless identity change
  // would remount the card iframe under a buyer mid-typing.
  return { lines: dirty ? next : lines, changes, unavailable };
}

// Fold a fresh reconcile into changes already shown. An existing entry keeps
// its ORIGINAL fromCents so a second re-price still reads "$15 → $45" rather
// than "$40 → $45", and an entry that lands back on its starting price drops
// out entirely.
export function mergeChanges(prev, next) {
  const merged = new Map(prev.map((c) => [changeKey(c.productId, c.size), c]));
  for (const change of next) {
    const key = changeKey(change.productId, change.size);
    const existing = merged.get(key);
    merged.set(key, existing ? { ...change, fromCents: existing.fromCents } : change);
  }
  return [...merged.values()].filter((c) => c.fromCents !== c.toCents);
}
