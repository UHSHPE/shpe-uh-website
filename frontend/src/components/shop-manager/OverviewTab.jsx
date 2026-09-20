import { formatCents } from "../../utils/shop";

function StatTile({ value, label, color }) {
  return (
    <div
      style={{
        border: "1px solid var(--border)",
        borderRadius: "14px",
        padding: "18px 20px",
        background: "#fff",
      }}
    >
      <p
        style={{
          margin: 0,
          fontSize: "30px",
          fontWeight: 800,
          lineHeight: 1,
          color,
        }}
      >
        {value}
      </p>
      <p
        style={{
          margin: "8px 0 0",
          fontSize: "12px",
          fontWeight: 600,
          color: "var(--muted)",
        }}
      >
        {label}
      </p>
    </div>
  );
}

export default function OverviewTab({ counts, collectedCents }) {
  return (
    <>
      <p
        style={{
          margin: "0 0 16px",
          fontSize: "15px",
          color: "var(--ink-soft)",
        }}
      >
        Right now:{" "}
        <strong style={{ color: "var(--ink)" }}>
          {counts.paid} paid · {counts.ready} ready for pickup ·{" "}
          {counts.picked_up} picked up
        </strong>
      </p>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
          gap: "14px",
        }}
      >
        <StatTile
          value={counts.paid}
          label="Paid · need prep"
          color="var(--status-paid-text)"
        />
        <StatTile
          value={counts.ready}
          label="Ready for pickup"
          color="var(--status-ready-text)"
        />
        <StatTile
          value={counts.picked_up}
          label="Picked up"
          color="var(--status-picked-text)"
        />
        <StatTile
          value={formatCents(collectedCents)}
          label="Collected"
          color="var(--shpe-blue)"
        />
      </div>
    </>
  );
}
