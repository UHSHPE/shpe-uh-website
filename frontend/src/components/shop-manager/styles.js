export const productRow = {
  display: "grid",
  gridTemplateColumns: "44px minmax(160px, 1fr) 84px 66px 92px 78px",
  gap: "12px",
  alignItems: "center",
  padding: "12px 16px",
  minWidth: "560px",
};

export const iconButton = {
  width: "32px",
  height: "32px",
  borderRadius: "8px",
  border: "1px solid var(--border)",
  background: "#fff",
  color: "var(--ink-soft)",
  cursor: "pointer",
  display: "grid",
  placeItems: "center",
};

export const sectionLabel = {
  margin: "0 0 6px",
  fontSize: "11px",
  fontWeight: 700,
  letterSpacing: ".05em",
  textTransform: "uppercase",
  color: "var(--muted-soft)",
};

export const formLabel = {
  display: "flex",
  flexDirection: "column",
  gap: "6px",
  fontSize: "12px",
  fontWeight: 700,
  color: "var(--ink-soft)",
};
