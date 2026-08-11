import { useEffect, useState } from "react";
import { getEventAttendance } from "../api/api";
import { formatClock, formatDuration, formatEventTime } from "../utils/events";

// Read-only attendance roster that expands under an event card on
// pages/my-events.jsx. No manual add/adjust — that's an explicit follow-up
// per the implementation plan, not part of this feature. Header meta is
// joined client-side from the event the card already has; the endpoint
// (GET /events/{id}/attendance) returns rows only.
export default function EventAttendancePanel({ event }) {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getEventAttendance(event.id)
      .then((res) => {
        if (!cancelled) setRows(res.data);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [event.id]);

  const signedOutCount = rows?.filter((r) => r.signed_out_at).length ?? 0;

  return (
    <div
      style={{
        border: "1px solid var(--border)",
        borderTop: "none",
        borderRadius: "0 0 12px 12px",
        background: "var(--surface-muted)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "12px",
          padding: "16px 20px",
          borderBottom: "1px solid var(--border)",
          flexWrap: "wrap",
        }}
      >
        <div>
          <p style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "var(--ink)" }}>{event.title} — Attendance</p>
          <p style={{ margin: "2px 0 0", fontSize: "12px", color: "var(--muted)" }}>
            {formatEventTime(event.start_time, event.end_time)}
          </p>
        </div>
        {rows && rows.length > 0 && (
          <p style={{ margin: 0, fontSize: "13px", fontWeight: 700, color: "var(--shpe-blue)" }}>
            {rows.length} signed in · {signedOutCount} signed out
          </p>
        )}
      </div>

      {error ? (
        <p style={{ padding: "24px", textAlign: "center", color: "var(--shpe-red)", fontSize: "14px", margin: 0 }}>
          Couldn't load attendance for this event.
        </p>
      ) : rows === null ? (
        <p style={{ padding: "24px", textAlign: "center", color: "var(--muted)", fontSize: "14px", margin: 0 }}>
          Loading…
        </p>
      ) : rows.length === 0 ? (
        <p style={{ padding: "24px", textAlign: "center", color: "var(--muted)", fontSize: "14px", margin: 0 }}>
          No one has checked in yet.
        </p>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", minWidth: "620px" }}>
            <thead>
              <tr style={{ fontSize: "11px", fontWeight: 700, letterSpacing: ".04em", textTransform: "uppercase", color: "var(--muted-soft)" }}>
                <th style={thStyle}>Member</th>
                <th style={thStyle}>Check-in</th>
                <th style={thStyle}>Sign-out</th>
                <th style={thStyle}>Duration</th>
                <th style={thStyle}>Points</th>
                <th style={thStyle}>Guest</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.user_id} style={{ borderTop: "1px solid var(--border)" }}>
                  <td style={tdStyle}>
                    <span style={{ fontWeight: 700, color: "var(--ink)" }}>
                      {r.first_name} {r.last_name}
                    </span>
                    <br />
                    <span style={{ fontSize: "12px", color: "var(--muted)" }}>{r.personal_email}</span>
                  </td>
                  <td style={tdStyle}>{formatClock(r.signed_in_at)}</td>
                  <td style={tdStyle}>{r.signed_out_at ? formatClock(r.signed_out_at) : "—"}</td>
                  <td style={tdStyle}>{formatDuration(r.signed_in_at, r.signed_out_at) ?? "—"}</td>
                  <td style={{ ...tdStyle, fontWeight: 700, color: "var(--shpe-blue)" }}>+{r.points_awarded}</td>
                  <td style={tdStyle}>
                    {r.brought_new_member ? (
                      <span style={{ display: "inline-flex", alignItems: "center", gap: "4px", fontSize: "12px", fontWeight: 700, color: "var(--success-deep)" }}>
                        👤 {r.new_member_name || "Yes"}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const thStyle = { textAlign: "left", padding: "10px 20px" };
const tdStyle = { padding: "12px 20px", fontSize: "13px", color: "var(--ink-soft)", verticalAlign: "top" };
