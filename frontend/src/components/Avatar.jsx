// Initials avatar — a brand-colored circle showing the member's initials,
// or an image when `src` is provided. Styling lives in styles.css (.avatar).
function initialsFrom(name = "") {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0][0].toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export default function Avatar({ name = "", src, size = 32, ring = false }) {
  return (
    <span
      className="avatar"
      aria-hidden="true"
      style={{
        width: size,
        height: size,
        fontSize: Math.round(size * 0.42),
        boxShadow: ring
          ? "0 0 0 2px #fff, 0 0 0 4px var(--shpe-orange-deep)"
          : "none",
      }}
    >
      {src ? <img src={src} alt="" /> : initialsFrom(name)}
    </span>
  );
}
