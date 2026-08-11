import { useEffect, useRef } from "react";
import { CloseIcon } from "./shopIcons";

// The app's one confirmation dialog — replaces window.confirm, which can't be
// styled and renders "\n\n" as literal text. Structure mirrors the ShopManager
// product modal (scrim + stopPropagation card + ghost/primary footer) and
// reuses its shopFadeIn/shopRiseIn keyframes, so no new CSS.
//
// zIndex 3400 sits above that modal (3200) and below the toast (4000), so a
// confirmation raised from inside a modal still covers it and a success toast
// still reads over the top.
export default function ConfirmDialog({
  title,
  body,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  tone = "primary",
  busy = false,
  onConfirm,
  onCancel,
}) {
  const confirmRef = useRef(null);

  // Escape to dismiss, and focus the confirm button on open. Neither existed
  // anywhere in this codebase before — window.confirm gave both for free.
  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === "Escape") onCancel?.();
    }
    document.addEventListener("keydown", onKeyDown);
    confirmRef.current?.focus();
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onCancel]);

  return (
    <div
      onClick={onCancel}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(3,10,30,.45)",
        zIndex: 3400,
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        padding: "80px 16px 40px",
        overflowY: "auto",
        animation: "shopFadeIn .2s ease",
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "460px",
          maxWidth: "100%",
          background: "#fff",
          borderRadius: "18px",
          boxShadow: "var(--shadow-modal)",
          animation: "shopRiseIn .25s ease",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "20px 24px", borderBottom: "1px solid var(--border)" }}>
          <h3 id="confirm-dialog-title" style={{ margin: 0, fontSize: "18px", fontWeight: 800, color: "var(--ink)" }}>
            {title}
          </h3>
          <button
            onClick={onCancel}
            aria-label="Close"
            style={{ width: "32px", height: "32px", borderRadius: "999px", border: "none", background: "var(--surface-soft)", color: "var(--ink-soft)", cursor: "pointer", display: "grid", placeItems: "center" }}
          >
            <CloseIcon size={16} />
          </button>
        </div>

        <div style={{ padding: "20px 24px", fontSize: "14px", lineHeight: 1.55, color: "var(--ink-soft)" }}>
          {body}
        </div>

        <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end", padding: "16px 24px", borderTop: "1px solid var(--border)" }}>
          <button
            onClick={onCancel}
            disabled={busy}
            style={{ borderRadius: "999px", padding: "10px 20px", fontSize: "14px", fontWeight: 700, border: "1px solid var(--border-strong)", background: "#fff", color: "var(--ink)", cursor: "pointer" }}
          >
            {cancelLabel}
          </button>
          <button
            ref={confirmRef}
            className={tone === "danger" ? "accentBtn" : "primaryBtn"}
            disabled={busy}
            onClick={onConfirm}
            style={{ padding: "10px 22px", fontSize: "14px", opacity: busy ? 0.6 : 1 }}
          >
            {busy ? "Working…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
