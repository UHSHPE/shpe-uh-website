import { useEffect, useRef, useState } from "react";
import { getAdminMember, getMemberResumeBlob } from "../api/api";
import { CloseIcon } from "./shopIcons";

// Full profile for one member, opened by clicking a row on pages/members.jsx.
// Modal shape (scrim + stopPropagation card + Escape-to-close + focus-on-open)
// is the one ConfirmDialog/EventQrModal already established; zIndex sits at
// 3200 alongside them, below the toast at 4000.
//
// Read-only by design. Role assignment stays on the row behind it — it has a
// confirm dialog of its own, and nesting one modal inside another is the kind
// of thing that ends with two scrims and a trapped Escape key.
export default function MemberDetailModal({ memberId, fallbackName, onClose }) {
  const [member, setMember] = useState(null);
  const [error, setError] = useState(false);
  const [resumeError, setResumeError] = useState(null);
  const closeRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    getAdminMember(memberId)
      .then((res) => {
        if (!cancelled) setMember(res.data);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [memberId]);

  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === "Escape") onClose?.();
    }
    document.addEventListener("keydown", onKeyDown);
    closeRef.current?.focus();
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  async function viewResume() {
    setResumeError(null);
    try {
      const res = await getMemberResumeBlob(memberId);
      const url = URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
      window.open(url, "_blank", "noopener");
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch {
      setResumeError("Couldn't open this resume.");
    }
  }

  const title = member ? `${member.first_name} ${member.last_name}` : fallbackName;

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
        aria-labelledby="member-detail-title"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "620px",
          maxWidth: "100%",
          background: "#fff",
          borderRadius: "14px",
          boxShadow: "var(--shadow-modal)",
          animation: "shopRiseIn .25s ease",
        }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "12px", padding: "20px 24px", borderBottom: "1px solid var(--border)" }}>
          <div style={{ minWidth: 0 }}>
            <h3 id="member-detail-title" style={{ margin: 0, fontSize: "18px", fontWeight: 800, color: "var(--ink)" }}>
              {title}
            </h3>
            {member && (
              <p style={{ margin: "3px 0 0", fontSize: "13px", color: "var(--muted)" }}>
                {member.role} · {member.points} pts
                {!member.email_verified && (
                  <span style={{ marginLeft: "8px", fontSize: "11px", fontWeight: 700, color: "var(--status-ready-text)", background: "var(--status-ready-bg)", border: "1px solid var(--status-ready-border)", borderRadius: "999px", padding: "2px 8px" }}>
                    Email not verified
                  </span>
                )}
              </p>
            )}
          </div>
          <button
            ref={closeRef}
            onClick={onClose}
            aria-label="Close"
            style={{ flexShrink: 0, width: "32px", height: "32px", borderRadius: "999px", border: "none", background: "var(--surface-soft)", color: "var(--ink-soft)", cursor: "pointer", display: "grid", placeItems: "center" }}
          >
            <CloseIcon size={16} />
          </button>
        </div>

        {error ? (
          <p style={{ padding: "32px 24px", textAlign: "center", color: "var(--shpe-red)", fontSize: "14px", margin: 0 }}>
            Couldn't load this member's profile.
          </p>
        ) : member === null ? (
          <p style={{ padding: "32px 24px", textAlign: "center", color: "var(--muted)", fontSize: "14px", margin: 0 }}>
            Loading…
          </p>
        ) : (
          <div style={{ padding: "20px 24px 24px", display: "flex", flexDirection: "column", gap: "22px" }}>
            <Section title="Contact">
              <Field label="CougarNet" value={member.cougarnet_email} copyable />
              <Field label="Personal email" value={member.personal_email} copyable />
              <Field label="Phone" value={member.phone_num} copyable />
              <Field label="PSID" value={member.psid} copyable />
              <Field label="Birthday" value={formatDate(member.birthday)} />
            </Section>

            <Section title="Academics">
              <Field label="College" value={member.college} />
              <Field label="Major" value={member.major} />
              <Field label="Classification" value={member.classification} />
              <Field label="Expected graduation" value={member.exp_grad_date} />
              <Field label="GPA range" value={member.gpa} />
              <Field label="First-generation" value={yesNo(member.first_gen)} />
            </Section>

            <Section title="Membership">
              <Field label="Dues" value={member.has_paid_dues ? "Paid this year" : "Not paid"} />
              <Field label="SHPE national member" value={yesNo(member.is_national_member)} />
              <Field label="Member status" value={member.is_returning} />
              <Field label="In Slack" value={yesNo(member.in_slack)} />
              <Field label="Shirt size" value={member.shirt_size} />
              <Field label="Gender" value={member.gender} />
            </Section>

            <Section title="Background">
              <Field label="Country of origin" value={joinList(member.country_origin)} wide />
              <Field label="Race / ethnicity" value={joinList(member.race_and_ethnicity)} wide />
              <Field label="Industries of interest" value={joinList(member.interested_industries)} wide />
              <Field label="Looking for" value={joinList(member.prof_dev)} wide />
            </Section>

            <div>
              <SectionTitle>Committees</SectionTitle>
              {member.committees.length === 0 ? (
                <p style={{ margin: 0, fontSize: "13px", color: "var(--muted-soft)" }}>Not in any committee.</p>
              ) : (
                <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                  {member.committees.map((c) => (
                    <span
                      key={c.id}
                      style={{
                        fontSize: "12px",
                        fontWeight: 600,
                        padding: "5px 12px",
                        borderRadius: "999px",
                        color: c.is_chair ? "#fff" : "var(--ink-soft)",
                        background: c.is_chair ? "var(--shpe-blue)" : "var(--surface-soft)",
                        border: c.is_chair ? "none" : "1px solid var(--border)",
                      }}
                    >
                      {c.name}
                      {c.is_chair && " · Chair"}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div>
              <SectionTitle>Resume</SectionTitle>
              {member.resume_filename ? (
                <>
                  <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
                    <span style={{ fontSize: "13px", color: "var(--ink-soft)", fontFamily: "var(--font-mono)" }}>
                      📄 {member.resume_filename}
                    </span>
                    <button onClick={viewResume} className="primaryBtn" style={{ padding: "7px 16px", fontSize: "13px" }}>
                      Open PDF
                    </button>
                  </div>
                  {resumeError && (
                    <p style={{ margin: "8px 0 0", fontSize: "13px", color: "var(--shpe-red)", fontWeight: 600 }}>{resumeError}</p>
                  )}
                </>
              ) : (
                <p style={{ margin: 0, fontSize: "13px", color: "var(--muted-soft)" }}>No resume uploaded.</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function SectionTitle({ children }) {
  return (
    <p style={{ margin: "0 0 10px", fontSize: "11px", fontWeight: 700, letterSpacing: ".05em", textTransform: "uppercase", color: "var(--muted-soft)" }}>
      {children}
    </p>
  );
}

function Section({ title, children }) {
  return (
    <div>
      <SectionTitle>{title}</SectionTitle>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "12px 20px" }}>
        {children}
      </div>
    </div>
  );
}

function Field({ label, value, copyable, wide }) {
  const [copied, setCopied] = useState(false);

  function copy() {
    navigator.clipboard?.writeText(value).then(
      () => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1400);
      },
      () => {},
    );
  }

  return (
    <div style={wide ? { gridColumn: "1 / -1" } : undefined}>
      <p style={{ margin: 0, fontSize: "11px", fontWeight: 600, color: "var(--muted-soft)" }}>{label}</p>
      <p style={{ margin: "2px 0 0", fontSize: "13px", color: "var(--ink)", display: "flex", alignItems: "center", gap: "8px", wordBreak: "break-word" }}>
        {value || "—"}
        {copyable && value && (
          <button
            type="button"
            onClick={copy}
            title={`Copy ${label.toLowerCase()}`}
            style={{ border: "none", background: "transparent", color: copied ? "var(--success-deep)" : "var(--muted-soft)", fontSize: "11px", fontWeight: 700, cursor: "pointer", padding: 0 }}
          >
            {copied ? "Copied" : "Copy"}
          </button>
        )}
      </p>
    </div>
  );
}

function yesNo(v) {
  return v ? "Yes" : "No";
}

function joinList(arr) {
  return Array.isArray(arr) && arr.length ? arr.join(", ") : "—";
}

function formatDate(iso) {
  if (!iso) return "—";
  // A bare YYYY-MM-DD is parsed as UTC midnight, so rendering it in a
  // western timezone would show the previous day. Split it instead.
  const [y, m, d] = iso.split("-").map(Number);
  return new Intl.DateTimeFormat("en-US", { month: "long", day: "numeric", year: "numeric" })
    .format(new Date(y, m - 1, d));
}
