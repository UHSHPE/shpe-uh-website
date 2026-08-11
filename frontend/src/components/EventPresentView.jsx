import { useEffect, useRef } from "react";
import { QRCodeSVG } from "qrcode.react";
import shpeHorizontalWhite from "../assets/logos/shpeHorizontalWhite.png";
import { formatEventTime } from "../utils/events";

// Fullscreen "present at the door" view, opened from EventQrModal's
// Fullscreen pill. Requests the real Fullscreen API on open and keeps the
// fixed overlay as the fallback either way (rejected/unsupported requests
// are a silent no-op) — Escape exits both. Polling for the scan count lives
// in the parent (EventQrModal), which keeps rendering this in place of the
// modal card while `presenting` is true, so the poll loop never restarts.
export default function EventPresentView({ event, mode, url, count, onExit }) {
  const rootRef = useRef(null);

  useEffect(() => {
    rootRef.current?.requestFullscreen?.().catch(() => {});
    function onKeyDown(e) {
      if (e.key === "Escape") onExit?.();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
    };
  }, [onExit]);

  const eyebrow = mode === "signIn" ? "Sign in · Check-in code" : "Sign out · Check-out code";

  return (
    <div
      ref={rootRef}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 3500,
        background: "var(--gradient-navy)",
        color: "#fff",
        display: "flex",
        flexDirection: "column",
        fontFamily: "var(--font-body)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "28px 48px", flexWrap: "wrap", gap: "14px" }}>
        <img src={shpeHorizontalWhite} alt="SHPE UH" style={{ height: "30px" }} />
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "8px 16px",
              borderRadius: "999px",
              background: "rgba(255,255,255,.15)",
              border: "1px solid rgba(255,255,255,.25)",
              fontSize: "14px",
              fontWeight: 700,
            }}
          >
            {count} scanned
          </span>
          <button
            type="button"
            onClick={onExit}
            style={{
              padding: "10px 18px",
              borderRadius: "999px",
              border: "1px solid rgba(255,255,255,.35)",
              background: "transparent",
              color: "#fff",
              fontSize: "14px",
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            Exit fullscreen
          </button>
        </div>
      </div>

      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: "56px", padding: "0 64px 40px", flexWrap: "wrap" }}>
        <div style={{ maxWidth: "480px" }}>
          <p style={{ margin: "0 0 16px", fontSize: "13px", fontWeight: 800, letterSpacing: ".16em", textTransform: "uppercase", color: "rgba(255,255,255,.7)" }}>
            {eyebrow}
          </p>
          <h1 style={{ margin: "0 0 18px", fontSize: "46px", fontWeight: 800, lineHeight: 1.08, letterSpacing: "-.02em" }}>{event.title}</h1>
          <p style={{ margin: 0, fontSize: "20px", fontWeight: 500, color: "rgba(255,255,255,.85)" }}>
            🕒 {formatEventTime(event.start_time, event.end_time)}
          </p>
          {event.location && (
            <p style={{ margin: "6px 0 0", fontSize: "20px", fontWeight: 500, color: "rgba(255,255,255,.85)" }}>📍 {event.location}</p>
          )}
        </div>
        <div style={{ background: "#fff", borderRadius: "20px", padding: "28px" }}>
          <QRCodeSVG value={url} size={320} fgColor="#001F5B" bgColor="#ffffff" level="M" />
        </div>
      </div>
    </div>
  );
}
