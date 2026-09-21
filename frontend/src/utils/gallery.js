export const GALLERY_ADMIN_ROLES = [
  "President",
  "Vice President External",
  "Vice President Internal",
  "Communication Director",
  "Marketing Chair",
];

export function isGalleryAdmin(user) {
  return GALLERY_ADMIN_ROLES.includes(user?.role);
}

export function gallerySectionTitle(semester, year) {
  const label = semester === "fall" ? "Fall" : "Spring";
  return `${label} ${year}`;
}

export function formatGalleryDate(isoString) {
  return new Date(`${isoString}Z`).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
