/* eslint-disable no-unused-vars */
import { motion } from "framer-motion";

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

function BreakdownCard({ title, counts }) {
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([, count]) => count));
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
          margin: "0 0 12px",
          fontSize: "13px",
          fontWeight: 700,
          color: "var(--ink)",
        }}
      >
        {title}
      </p>
      {entries.length === 0 && (
        <p style={{ margin: 0, fontSize: "13px", color: "var(--muted)" }}>
          No data yet.
        </p>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        {entries.map(([label, count]) => (
          <div
            key={label}
            style={{
              display: "grid",
              gridTemplateColumns: "minmax(90px, 1fr) 2fr 32px",
              gap: "10px",
              alignItems: "center",
            }}
          >
            <span
              style={{
                fontSize: "12px",
                fontWeight: 600,
                color: "var(--ink-soft)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {label}
            </span>
            <span
              style={{
                height: "8px",
                borderRadius: "999px",
                background: "var(--surface-soft)",
                overflow: "hidden",
              }}
            >
              <span
                style={{
                  display: "block",
                  height: "100%",
                  width: `${(count / max) * 100}%`,
                  borderRadius: "999px",
                  background: "var(--shpe-blue)",
                }}
              />
            </span>
            <span
              style={{
                fontSize: "12px",
                fontWeight: 700,
                color: "var(--ink)",
                textAlign: "right",
              }}
            >
              {count}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function MemberStats({ stats }) {
  if (!stats) return null;
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: 0.05 }}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
          gap: "14px",
          marginBottom: "14px",
        }}
      >
        <StatTile
          value={stats.total_accounts}
          label="Total accounts"
          color="var(--shpe-blue)"
        />
        <StatTile
          value={stats.dues_paid}
          label="Dues paid"
          color="var(--status-picked-text)"
        />
        <StatTile
          value={stats.dues_unpaid}
          label="Not paid"
          color="var(--status-ready-text)"
        />
        <StatTile
          value={stats.national_members}
          label="SHPE national members"
          color="var(--shpe-navy)"
        />
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: "14px",
          marginBottom: "28px",
        }}
      >
        <BreakdownCard
          title="By classification"
          counts={stats.classification_counts}
        />
        <BreakdownCard
          title="Shirt sizes (for dues t-shirt orders)"
          counts={stats.shirt_size_counts}
        />
      </div>
    </motion.div>
  );
}
