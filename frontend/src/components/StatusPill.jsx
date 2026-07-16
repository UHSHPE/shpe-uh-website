import { STATUS_META } from "../utils/shop";

// Order-status pill (Paid / Ready for pickup / Picked up / Cancelled).
export default function StatusPill({ status }) {
  const meta = STATUS_META[status] ?? STATUS_META.paid;
  return (
    <span
      style={{
        borderRadius: "999px",
        padding: "3px 10px",
        fontSize: "11px",
        fontWeight: 700,
        whiteSpace: "nowrap",
        color: meta.color,
        background: meta.bg,
        border: `1px solid ${meta.border}`,
      }}
    >
      {meta.label}
    </span>
  );
}
