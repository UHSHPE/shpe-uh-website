import { useEffect, useState } from "react";
import { getEventStats } from "../api/api";

// Aggregate statistics that expand under an event card on
// pages/my-events.jsx. Companion to EventAttendancePanel: that one is the
// named roster (host-scoped), this one is counts only, which is why it
// renders on All Events for every event including other committees'.
//
// Everything is drawn with plain divs rather than a chart library — the
// breakdowns are short, fixed-category bar rows, and the project has no
// charting dependency to justify adding for four of them.

const BAR_COLORS = {
  classifications: "var(--shpe-blue-mid)",
  colleges: "var(--event-professional)",
  majors: "var(--event-social)",
  membership: "var(--event-srt)",
};

export default function EventStatsPanel({ event }) {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    // No setState reset here — the lint config's react-hooks/set-state-in-effect
    // rule fails the build on it, and the panel is mounted fresh per event
    // anyway (my-events.jsx renders it only for the expanded card).
    let cancelled = false;
    getEventStats(event.id)
      .then((res) => {
        if (!cancelled) setStats(res.data);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [event.id]);

  return (
    <div
      style={{
        border: "1px solid var(--border)",
        borderTop: "none",
        borderRadius: "0 0 12px 12px",
        background: "var(--surface-muted)",
      }}
    >
      <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border)" }}>
        <p style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "var(--ink)" }}>
          {event.title} — Statistics
        </p>
        <p style={{ margin: "2px 0 0", fontSize: "12px", color: "var(--muted)" }}>
          Attendance breakdown. Demographics reflect each member's profile today.
        </p>
      </div>

      {error ? (
        <p style={{ padding: "24px", textAlign: "center", color: "var(--shpe-red)", fontSize: "14px", margin: 0 }}>
          Couldn't load statistics for this event.
        </p>
      ) : stats === null ? (
        <p style={{ padding: "24px", textAlign: "center", color: "var(--muted)", fontSize: "14px", margin: 0 }}>
          Loading…
        </p>
      ) : stats.signed_in === 0 ? (
        <p style={{ padding: "24px", textAlign: "center", color: "var(--muted)", fontSize: "14px", margin: 0 }}>
          No one has checked in yet — nothing to summarize.
        </p>
      ) : (
        <div style={{ padding: "20px" }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
              gap: "12px",
              marginBottom: "24px",
            }}
          >
            <StatTile label="Attended" value={stats.signed_in} accent />
            <StatTile label="Signed out" value={stats.signed_out} hint={`${stats.still_signed_in} never scanned out`} />
            <StatTile label="Avg. time at event" value={stats.average_minutes === null ? "—" : formatMinutes(stats.average_minutes)} />
            <StatTile label="First-timers" value={stats.first_time_attendees} hint={`${stats.returning_attendees} had come before`} />
            <StatTile label="Guests brought" value={stats.guests_brought} />
            <StatTile label="National members" value={stats.national_members} />
            <StatTile label="Points awarded" value={stats.total_points_awarded} />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "24px" }}>
            <Breakdown
              title="Classification"
              rows={stats.classifications}
              total={stats.signed_in}
              color={BAR_COLORS.classifications}
            />
            <Breakdown
              title={`Top majors${stats.distinct_majors > stats.top_majors.length ? ` (of ${stats.distinct_majors})` : ""}`}
              rows={
                stats.other_majors > 0
                  ? [...stats.top_majors, { label: "All other majors", count: stats.other_majors }]
                  : stats.top_majors
              }
              total={stats.signed_in}
              color={BAR_COLORS.majors}
            />
            <Breakdown
              title="College"
              rows={stats.colleges}
              total={stats.signed_in}
              color={BAR_COLORS.colleges}
            />
            <Breakdown
              title="Membership"
              rows={stats.membership}
              total={stats.signed_in}
              color={BAR_COLORS.membership}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function StatTile({ label, value, hint, accent }) {
  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid var(--border)",
        borderRadius: "10px",
        padding: "14px 16px",
      }}
    >
      <p style={{ margin: 0, fontSize: "11px", fontWeight: 700, letterSpacing: ".04em", textTransform: "uppercase", color: "var(--muted-soft)" }}>
        {label}
      </p>
      <p style={{ margin: "6px 0 0", fontSize: "24px", fontWeight: 800, color: accent ? "var(--shpe-red)" : "var(--shpe-navy)", lineHeight: 1.1 }}>
        {value}
      </p>
      {hint && <p style={{ margin: "4px 0 0", fontSize: "11px", color: "var(--muted)" }}>{hint}</p>}
    </div>
  );
}

// One fixed-category bar row. Bars are scaled against the largest bucket
// (not the total) so a lopsided breakdown still reads, while the percentage
// beside each count stays relative to everyone who attended.
function Breakdown({ title, rows, total, color }) {
  const peak = Math.max(1, ...rows.map((r) => r.count));

  return (
    <div>
      <p style={{ margin: "0 0 10px", fontSize: "12px", fontWeight: 700, letterSpacing: ".03em", textTransform: "uppercase", color: "var(--muted)" }}>
        {title}
      </p>
      {rows.length === 0 ? (
        <p style={{ margin: 0, fontSize: "13px", color: "var(--muted-soft)" }}>No data.</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {rows.map((row) => (
            <div key={row.label}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: "10px", fontSize: "12px", marginBottom: "3px" }}>
                <span style={{ color: "var(--ink-soft)", fontWeight: row.count > 0 ? 600 : 400 }}>{row.label}</span>
                <span style={{ color: "var(--muted)", whiteSpace: "nowrap" }}>
                  {row.count}
                  {total > 0 && row.count > 0 && ` · ${Math.round((row.count / total) * 100)}%`}
                </span>
              </div>
              <div style={{ height: "6px", borderRadius: "999px", background: "var(--surface-soft)", overflow: "hidden" }}>
                <div
                  style={{
                    width: `${(row.count / peak) * 100}%`,
                    height: "100%",
                    borderRadius: "999px",
                    background: color,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function formatMinutes(minutes) {
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours}h` : `${hours}h ${rest}m`;
}
