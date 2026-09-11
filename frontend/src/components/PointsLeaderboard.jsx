import { useEffect, useState } from "react";
import { getLeaderboard } from "../api/api";

// Rows visible before the body scrolls. The header is sticky inside the
// scroller, so the column labels stay put while the reader moves down the
// list — a plain max-height would scroll them out of view and leave five
// unlabelled number columns.
const VISIBLE_ROWS = 10;
const ROW_HEIGHT = 52;

// Medal tints for the top three. Deliberately not from the --event-* tokens:
// those carry event-type meaning elsewhere in the app and reusing them here
// would imply a relationship that doesn't exist.
const RANK_STYLES = {
  1: { background: "#FDF3D0", color: "#8A6A0B" },
  2: { background: "#EFF1F4", color: "#5B6472" },
  3: { background: "#FAE8DC", color: "#8A4B22" },
};

function RankBadge({ rank }) {
  const tint = RANK_STYLES[rank];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        minWidth: "28px",
        height: "28px",
        padding: "0 8px",
        borderRadius: "999px",
        fontWeight: 700,
        fontSize: "14px",
        background: tint ? tint.background : "transparent",
        color: tint ? tint.color : "var(--navText, #001F5B)",
      }}
    >
      {rank}
    </span>
  );
}

export default function PointsLeaderboard() {
  const [data, setData] = useState(null); // null = loading
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    getLeaderboard()
      .then((res) => {
        if (!active) return;
        // A misrouted call can come back as index.html with a 200 (the SPA
        // catch-all rewrite), so shape-check before rendering rather than
        // letting .map throw and blank the page.
        const payload = res.data;
        if (!payload || !Array.isArray(payload.entries) || !Array.isArray(payload.pillars)) {
          setError(true);
          return;
        }
        setData(payload);
      })
      .catch(() => {
        if (active) setError(true);
      });
    return () => { active = false; };
  }, []);

  // Points from an event type with no pillar (a new tracker-sheet dropdown
  // option, a hand-added event). Normally zero everywhere, so the column is
  // hidden — but when it isn't, showing it is what keeps every row visibly
  // adding up to its own total instead of looking like an arithmetic bug.
  const showOther = !!data && data.entries.some((e) => e.uncategorized_points > 0);

  const cellBase = {
    padding: "0 12px",
    fontSize: "14px",
    whiteSpace: "nowrap",
  };
  const headBase = {
    ...cellBase,
    position: "sticky",
    top: 0,
    zIndex: 1,
    background: "var(--gradient-navy, #001F5B)",
    color: "#fff",
    fontWeight: 600,
    fontSize: "12px",
    letterSpacing: ".04em",
    textTransform: "uppercase",
    height: "44px",
    textAlign: "center",
  };

  return (
    <div style={{ width: "100%", maxWidth: "1000px", marginTop: "48px" }}>
      <h2
        className="text-[clamp(1.4rem,3.5vw,2.25rem)]"
        style={{
          fontWeight: 800,
          color: "var(--navText, #001F5B)",
          textAlign: "center",
          margin: "0 0 6px",
        }}
      >
        Points Leaderboard
      </h2>
      <p
        style={{
          textAlign: "center",
          color: "#6b7280",
          fontSize: "14px",
          margin: "0 0 20px",
          lineHeight: 1.5,
        }}
      >
        Points earned by checking in at chapter events, broken down by pillar.
      </p>

      {error && (
        <p style={{ textAlign: "center", color: "#6b7280", fontSize: "15px" }}>
          The leaderboard couldn&rsquo;t be loaded right now. Please try again later.
        </p>
      )}

      {!error && data === null && (
        <p style={{ textAlign: "center", color: "#6b7280", fontSize: "15px" }}>
          Loading the leaderboard&hellip;
        </p>
      )}

      {!error && data && data.entries.length === 0 && (
        <p style={{ textAlign: "center", color: "#6b7280", fontSize: "15px" }}>
          No points have been recorded yet. Check in at an event to get on the board!
        </p>
      )}

      {!error && data && data.entries.length > 0 && (
        <>
          {/* Horizontal scroll lives on this wrapper, not the page — seven
              columns cannot fit a phone, and the page body must never scroll
              sideways. The vertical cap is on the same element so the sticky
              header has a scroll container to stick to. */}
          <div
            style={{
              overflowX: "auto",
              overflowY: "auto",
              maxHeight: `${44 + VISIBLE_ROWS * ROW_HEIGHT}px`,
              border: "1px solid #e5e7eb",
              borderRadius: "var(--radius-lg, 12px)",
              background: "#fff",
              boxShadow: "var(--shadow-card, 0 1px 3px rgba(0,0,0,.08))",
            }}
          >
            <table style={{ borderCollapse: "collapse", width: "100%", minWidth: "640px" }}>
              <thead>
                <tr>
                  <th style={{ ...headBase, textAlign: "center", width: "64px" }}>#</th>
                  <th style={{ ...headBase, textAlign: "left" }}>Member</th>
                  <th style={{ ...headBase }}>Total</th>
                  {data.pillars.map((pillar) => (
                    <th key={pillar.key} style={headBase} title={pillar.label}>
                      {pillar.short}
                    </th>
                  ))}
                  {showOther && (
                    <th style={headBase} title="Events with no pillar assigned">
                      Other
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {data.entries.map((entry) => (
                  <tr
                    key={`${entry.rank}-${entry.name}`}
                    style={{ height: `${ROW_HEIGHT}px`, borderTop: "1px solid #f1f3f5" }}
                  >
                    <td style={{ ...cellBase, textAlign: "center" }}>
                      <RankBadge rank={entry.rank} />
                    </td>
                    <td style={{ ...cellBase, fontWeight: 600, color: "var(--navText, #001F5B)" }}>
                      {entry.name}
                    </td>
                    <td
                      style={{
                        ...cellBase,
                        textAlign: "center",
                        fontWeight: 800,
                        color: "var(--shpe-red, #D33A02)",
                        fontSize: "15px",
                      }}
                    >
                      {entry.total_points}
                    </td>
                    {data.pillars.map((pillar) => {
                      const value = entry.points_by_pillar[pillar.key] ?? 0;
                      return (
                        <td
                          key={pillar.key}
                          style={{
                            ...cellBase,
                            textAlign: "center",
                            color: value === 0 ? "#c2c8d0" : "var(--navText, #001F5B)",
                          }}
                        >
                          {value}
                        </td>
                      );
                    })}
                    {showOther && (
                      <td
                        style={{
                          ...cellBase,
                          textAlign: "center",
                          color: entry.uncategorized_points === 0 ? "#c2c8d0" : "var(--navText, #001F5B)",
                        }}
                      >
                        {entry.uncategorized_points}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p style={{ textAlign: "center", color: "#9ca3af", fontSize: "13px", marginTop: "10px" }}>
            {data.entries.length > VISIBLE_ROWS
              ? `Showing the top ${VISIBLE_ROWS} — scroll for all ${data.entries.length} members.`
              : `${data.entries.length} member${data.entries.length === 1 ? "" : "s"}.`}
          </p>
        </>
      )}
    </div>
  );
}
