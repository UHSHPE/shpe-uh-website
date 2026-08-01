import { useEffect, useRef, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { getEventScanCount } from "../api/api";
import EventPresentView from "./EventPresentView";
import { CloseIcon } from "./shopIcons";

// QR modal for a hosted event — Sign in / Sign out segmented control, the
// QR itself (encoding a URL to our own site so the member's native camera
// opens it — no in-app scanner, see CLAUDE.md "QR attendance & points"),
// and a live scan counter polled every 5s. Escape-to-close, role="dialog",
// and focus-on-open borrowed from components/ConfirmDialog.jsx, which
// already solved these. Scrim uses the design handoff's navy value
// (rgba(0,31,91,.55)) rather than ConfirmDialog's rgba(3,10,30,.45).
export default function EventQrModal({ event, onClose }) {
  const [mode, setMode] = useState("signIn"); // "signIn" | "signOut"
  const [scanCount, setScanCount] = useState({ signed_in: 0, signed_out: 0 });
  const [presenting, setPresenting] = useState(false);
  const closeRef = useRef(null);

  // Polling lives here (not in EventPresentView) so switching into/out of
  // fullscreen never restarts the interval.
  useEffect(() => {
    let cancelled = false;
    function poll() {
      getEventScanCount(event.id)
        .then((res) => {
          if (!cancelled) setScanCount(res.data);
        })
        .catch(() => {});
    }
    poll();
    const id = setInterval(poll, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [event.id]);

  useEffect(() => {
    function onKeyDown(e) {
      if (e.key !== "Escape") return;
      if (presenting) setPresenting(false);
      else onClose?.();
    }
    document.addEventListener("keydown", onKeyDown);
    closeRef.current?.focus();
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [presenting, onClose]);

  const code = mode === "signIn" ? event.sign_in_code : event.sign_out_code;
  const url = `${window.location.origin}/attend/${code}`;
  const count = mode === "signIn" ? scanCount.signed_in : scanCount.signed_out;

  if (presenting) {
    return <EventPresentView event={event} mode={mode} url={url} count={count} onExit={() => setPresenting(false)} />;
  }

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,31,91,.55)",
        zIndex: 3200,
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        padding: "40px 16px",
        overflowY: "auto",
        animation: "shopFadeIn .2s ease",
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="qr-modal-title"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "460px",
          maxWidth: "100%",
          background: "#fff",
          borderRadius: "14px",
          boxShadow: "var(--shadow-modal)",
          animation: "shopRiseIn .25s ease",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "20px 24px", borderBottom: "1px solid var(--border)" }}>
          <h3 id="qr-modal-title" style={{ margin: 0, fontSize: "17px", fontWeight: 800, color: "var(--ink)" }}>
            {event.title}
          </h3>
          <button
            ref={closeRef}
            onClick={onClose}
            aria-label="Close"
            style={{ width: "32px", height: "32px", borderRadius: "999px", border: "none", background: "var(--surface-soft)", color: "var(--ink-soft)", cursor: "pointer", display: "grid", placeItems: "center" }}
          >
            <CloseIcon size={16} />
          </button>
        </div>

        <div style={{ padding: "28px 24px", display: "flex", flexDirection: "column", alignItems: "center", gap: "20px" }}>
          {/* Segmented control */}
          <div style={{ display: "inline-flex", padding: "4px", gap: "4px", borderRadius: "999px", background: "var(--page-bg)", border: "1px solid var(--border)" }}>
            {[
              { key: "signIn", label: "Sign in" },
              { key: "signOut", label: "Sign out" },
            ].map((seg) => {
              const active = mode === seg.key;
              return (
                <button
                  key={seg.key}
                  onClick={() => setMode(seg.key)}
                  style={{
                    padding: "8px 20px",
                    borderRadius: "999px",
                    border: "none",
                    background: active ? "var(--shpe-navy)" : "transparent",
                    color: active ? "#fff" : "var(--muted)",
                    fontSize: "14px",
                    fontWeight: active ? 700 : 600,
                    cursor: "pointer",
                  }}
                >
                  {seg.label}
                </button>
              );
            })}
          </div>

          <div style={{ padding: "16px", border: "1px solid var(--border)", borderRadius: "12px" }}>
            <QRCodeSVG value={url} size={300} fgColor="#001F5B" bgColor="#ffffff" level="M" />
          </div>

          <button
            onClick={() => setPresenting(true)}
            style={{
              width: "100%",
              height: "52px",
              borderRadius: "999px",
              border: "none",
              background: "var(--gradient-navy)",
              color: "#fff",
              fontSize: "16px",
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            Fullscreen
          </button>

          <p style={{ margin: 0, fontSize: "15px", fontWeight: 600, color: "var(--muted)" }}>
            {count} member{count === 1 ? "" : "s"} scanned so far
          </p>
        </div>
      </div>
    </div>
  );
}
