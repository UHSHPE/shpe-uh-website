/* eslint-disable no-unused-vars */
import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useAuth } from "../context/AuthContext";
import { getAllChairEvents, getMyEvents } from "../api/api";
import { isChair, isEboard } from "../utils/shop";
import { eventColor, eventTypeLabel, formatEventDay, formatEventTime } from "../utils/events";
import EventQrModal from "../components/EventQrModal";
import EventAttendancePanel from "../components/EventAttendancePanel";
import useDocumentTitle from "../hooks/useDocumentTitle";

// Chair/E-Board Events page — My Events (with QR + attendance) and All
// Events (read-only, no codes). Route gate mirrors pages/shop-manager.jsx:
// PrivateRoute handles "must be signed in", this page bounces anyone who
// isn't a chair or E-Board member back to the dashboard. isChair is NOT a
// superset of isEboard (the president is E-Board but not a chair), so both
// checks are required.
export default function MyEventsPage() {
  useDocumentTitle("Events");
  const { user } = useAuth();
  const [tab, setTab] = useState("mine");
  const [mineEvents, setMineEvents] = useState([]);
  const [allEvents, setAllEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [qrEvent, setQrEvent] = useState(null);
  const [expandedId, setExpandedId] = useState(null);

  const authorized = user && (isChair(user) || isEboard(user));

  useEffect(() => {
    if (!authorized) return;
    let cancelled = false;
    Promise.all([getMyEvents(), getAllChairEvents()])
      .then(([mine, all]) => {
        if (cancelled) return;
        setMineEvents(mine.data);
        setAllEvents(all.data);
      })
      .catch(() => {
        if (!cancelled) setLoadError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [authorized]);

  if (!user) {
    return (
      <div style={{ minHeight: "60vh", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--blue)", fontWeight: 600, fontFamily: "Work Sans, sans-serif" }}>
        Loading…
      </div>
    );
  }

  if (!authorized) {
    return <Navigate to="/dashboard" replace />;
  }

  const events = tab === "mine" ? mineEvents : allEvents;

  return (
    <div style={{ maxWidth: "1040px", margin: "0 auto", padding: "96px 20px 80px", fontFamily: "Work Sans, sans-serif" }}>
      <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
        <h1 style={{ margin: "0 0 6px", fontSize: "30px", fontWeight: 800, color: "var(--shpe-navy)" }}>Events</h1>
        <p style={{ margin: "0 0 24px", fontSize: "14px", color: "var(--muted)" }}>
          Present a QR code at the door for sign-in and sign-out, and review who checked in.
        </p>
      </motion.div>

      {loadError && (
        <p style={{ margin: "0 0 24px", fontSize: "14px", color: "var(--shpe-red)", fontWeight: 600 }}>
          Couldn't load events. Refresh to try again.
        </p>
      )}

      {/* Sub-tabs — underline style, matching Shop Manager / Members. */}
      <div style={{ display: "flex", gap: "28px", borderBottom: "1px solid var(--border)", marginBottom: "22px" }}>
        {[
          { key: "mine", label: "My Events" },
          { key: "all", label: "All Events" },
        ].map((t) => {
          const active = tab === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              style={{
                position: "relative",
                border: "none",
                background: "transparent",
                padding: "10px 2px 14px",
                fontSize: "16px",
                fontFamily: "inherit",
                fontWeight: active ? 700 : 500,
                color: active ? "var(--shpe-navy)" : "var(--muted)",
                cursor: "pointer",
              }}
            >
              {t.label}
              {active && (
                <span style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: "2px", background: "var(--shpe-navy)", borderRadius: "999px" }} />
              )}
            </button>
          );
        })}
      </div>

      {loading ? (
        <p style={{ color: "var(--muted)", fontSize: "14px" }}>Loading events…</p>
      ) : events.length === 0 ? (
        <div style={{ border: "1px solid var(--border)", borderRadius: "12px", padding: "48px 24px", textAlign: "center", color: "var(--muted)", fontSize: "14px", background: "#fff" }}>
          {tab === "mine" ? "You aren't hosting any events yet." : "No events on the calendar yet."}
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
          {events.map((ev) => (
            <div key={ev.id}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "16px",
                  background: "#fff",
                  border: "1px solid var(--border)",
                  borderLeft: `4px solid ${eventColor(ev.event_type)}`,
                  borderRadius: expandedId === ev.id ? "12px 12px 0 0" : "12px",
                  boxShadow: "var(--shadow-card)",
                  padding: "18px 20px",
                  flexWrap: "wrap",
                }}
              >
                <div style={{ flex: 1, minWidth: "220px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap", marginBottom: "4px" }}>
                    <span
                      style={{
                        display: "inline-block",
                        background: eventColor(ev.event_type),
                        color: "#fff",
                        borderRadius: "999px",
                        padding: "2px 10px",
                        fontSize: "11px",
                        fontWeight: 700,
                      }}
                    >
                      {eventTypeLabel(ev.event_type)}
                    </span>
                    <p style={{ margin: 0, fontWeight: 700, fontSize: "16px", color: "var(--ink)" }}>{ev.title}</p>
                  </div>
                  <p style={{ margin: 0, fontSize: "13px", color: "var(--muted)" }}>
                    🕒 {formatEventDay(ev.start_time)} · {formatEventTime(ev.start_time, ev.end_time)}
                  </p>
                  {ev.location && (
                    <p style={{ margin: "2px 0 0", fontSize: "13px", color: "var(--muted)" }}>📍 {ev.location}</p>
                  )}
                </div>

                {ev.points_value > 0 && (
                  <span
                    style={{
                      background: "var(--shpe-red)",
                      color: "#fff",
                      borderRadius: "999px",
                      padding: "4px 10px",
                      fontSize: "12px",
                      fontWeight: 700,
                      whiteSpace: "nowrap",
                    }}
                  >
                    +{ev.points_value} pts
                  </span>
                )}

                {tab === "mine" && (
                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    <button
                      onClick={() => setQrEvent(ev)}
                      className="primaryBtn"
                      style={{ padding: "8px 16px", fontSize: "13px" }}
                    >
                      Show QR
                    </button>
                    <button
                      onClick={() => setExpandedId(expandedId === ev.id ? null : ev.id)}
                      style={{
                        borderRadius: "999px",
                        padding: "8px 16px",
                        fontSize: "13px",
                        fontWeight: 700,
                        border: "1px solid var(--border-strong)",
                        background: "#fff",
                        color: "var(--shpe-blue)",
                        cursor: "pointer",
                      }}
                    >
                      {expandedId === ev.id ? "Hide attendance" : "Attendance"} ({ev.attendee_count})
                    </button>
                  </div>
                )}
              </div>

              {tab === "mine" && expandedId === ev.id && <EventAttendancePanel event={ev} />}
            </div>
          ))}
        </div>
      )}

      {qrEvent && <EventQrModal event={qrEvent} onClose={() => setQrEvent(null)} />}
    </div>
  );
}
