/* eslint-disable no-unused-vars */
import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { attendEvent, getAttendPreview } from "../api/api";
import { useAuth } from "../context/AuthContext";
import CheckInSuccess from "../components/CheckInSuccess";
import shpeMark from "../assets/logos/shpeMark.png";
import { formatClock, formatDuration, formatEventTime } from "../utils/events";

// Mobile QR check-in flow — reached ONLY by scanning a code (never linked
// from nav), so it renders with zero site chrome (see App.jsx's `bare`
// branch) and its own full-bleed navy shell. State machine and screens per
// the design handoff (Event Check-In System §1-4) and the implementation
// plan's Part 3.

const EASE = [0.22, 1, 0.36, 1];

function Shell({ flat, children }) {
  return (
    <div
      style={{
        minHeight: "100dvh",
        background: flat ? "#003A70" : "var(--gradient-navy)",
        color: "#fff",
        display: "flex",
        flexDirection: "column",
        fontFamily: "var(--font-body)",
      }}
    >
      <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", padding: "0 24px 40px" }}>
        {children}
      </div>
    </div>
  );
}

function Reveal({ delay = 0, children, style }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay, ease: EASE }}
      style={style}
    >
      {children}
    </motion.div>
  );
}

function PrimaryCta({ children, disabled, ...props }) {
  return (
    <button
      type="button"
      disabled={disabled}
      {...props}
      style={{
        width: "100%",
        height: "56px",
        borderRadius: "999px",
        background: "#fff",
        color: "var(--shpe-navy)",
        border: "none",
        fontSize: "17px",
        fontWeight: 700,
        fontFamily: "inherit",
        cursor: disabled ? "default" : "pointer",
        opacity: disabled ? 0.6 : 1,
        boxShadow: "0 4px 30px rgba(0,31,91,.25)",
      }}
    >
      {children}
    </button>
  );
}

function EventSummaryCard({ event }) {
  return (
    <div
      style={{
        background: "rgba(255,255,255,.12)",
        border: "1px solid rgba(255,255,255,.2)",
        borderRadius: "14px",
        padding: "18px 20px",
        display: "flex",
        flexDirection: "column",
        gap: "8px",
      }}
    >
      <p style={{ margin: 0, fontSize: "19px", fontWeight: 700 }}>{event.title}</p>
      <p style={{ margin: 0, fontSize: "15px", color: "rgba(255,255,255,.85)" }}>
        🕒 {formatEventTime(event.start_time, event.end_time)}
      </p>
      {event.location && (
        <p style={{ margin: 0, fontSize: "15px", color: "rgba(255,255,255,.85)" }}>📍 {event.location}</p>
      )}
    </div>
  );
}

function Spinner({ caption }) {
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "28px" }}>
      <div
        style={{
          width: "64px",
          height: "64px",
          borderRadius: "999px",
          border: "3px solid rgba(255,255,255,.25)",
          borderTopColor: "#fff",
          animation: "shopSpin .9s linear infinite",
        }}
      />
      <p style={{ margin: 0, fontSize: "17px", lineHeight: 1.45, fontWeight: 500, color: "rgba(255,255,255,.8)" }}>
        {caption}
      </p>
    </div>
  );
}

// Shared language for the six terminal error screens (design handoff §4):
// centered column, 120px white circle with a red "!", H2, muted explanation.
// Never a browser alert(). All terminal except network, which offers Retry.
function ErrorScreen({ title, body, onRetry }) {
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", gap: "22px" }}>
      <Reveal>
        <div
          style={{
            width: "120px",
            height: "120px",
            borderRadius: "999px",
            background: "#fff",
            display: "grid",
            placeItems: "center",
            fontSize: "62px",
            fontWeight: 800,
            color: "var(--shpe-red)",
          }}
        >
          !
        </div>
      </Reveal>
      <Reveal delay={0.1} style={{ display: "flex", flexDirection: "column", gap: "10px", maxWidth: "320px" }}>
        <h2 style={{ margin: 0, fontSize: "26px", fontWeight: 700, lineHeight: 1.2, letterSpacing: "-.01em" }}>{title}</h2>
        <p style={{ margin: 0, fontSize: "16px", lineHeight: 1.45, color: "rgba(255,255,255,.75)" }}>{body}</p>
      </Reveal>
      {onRetry && (
        <Reveal delay={0.18} style={{ width: "100%", maxWidth: "320px" }}>
          <PrimaryCta onClick={onRetry}>Retry</PrimaryCta>
        </Reveal>
      )}
    </div>
  );
}

const ERROR_COPY = {
  alreadyCheckedIn: {
    title: "You're already checked in",
    body: (ctx) =>
      ctx.signedInAt
        ? `Checked in at ${formatClock(ctx.signedInAt)}. Your credit is already recorded — no need to scan again.`
        : "Your credit is already recorded — no need to scan again.",
  },
  alreadySignedOut: {
    title: "You're already signed out",
    body: (ctx) => {
      const duration = formatDuration(ctx.signedInAt, ctx.signedOutAt);
      return duration
        ? `You attended for ${duration}. Your points are recorded.`
        : "Your sign-out is already recorded. Your points are recorded.";
    },
  },
  noCheckIn: {
    title: "No check-in on record",
    body: () => "We don't have a sign-in for you at this event. Please see a chair at the door.",
  },
  invalidCode: {
    title: "This code isn't valid",
    body: () => "It may have expired or been mistyped. Ask a chair for a fresh code.",
  },
  notStarted: {
    title: "Check-in hasn't opened yet",
    body: (ctx) =>
      ctx.startTime
        ? `Check-in opens closer to ${formatClock(ctx.startTime)}. Come back then.`
        : "Come back closer to the event start time.",
  },
  ended: {
    title: "This code has expired",
    body: () => "This event has already ended. Ask a chair if you still need credit.",
  },
  network: {
    title: "Something went wrong",
    body: () => "We couldn't reach the server. Check your connection and retry — a chair can also add you manually.",
  },
};

function dotStyle(filled) {
  return {
    width: "6px",
    height: "6px",
    borderRadius: "999px",
    background: filled ? "#fff" : "rgba(255,255,255,.3)",
  };
}

function pillChoiceStyle(primary) {
  return {
    flex: 1,
    height: "52px",
    borderRadius: "999px",
    border: primary ? "none" : "1.5px solid rgba(255,255,255,.35)",
    background: primary ? "#fff" : "transparent",
    color: primary ? "var(--shpe-navy)" : "#fff",
    fontSize: "16px",
    fontWeight: 700,
    fontFamily: "inherit",
    cursor: "pointer",
  };
}

export default function Attend() {
  const { code } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { token, user, refreshUser } = useAuth();

  // status: verifying | unauthenticated | confirm | guestQuestion |
  //         guestCapture | submitting | success | error
  const [status, setStatus] = useState("verifying");
  const [errorKind, setErrorKind] = useState(null);
  // Which phase produced the current error — decides what Retry does.
  const [errorPhase, setErrorPhase] = useState(null); // "preview" | "submit"
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [guestName, setGuestName] = useState("");
  const [lastAttempt, setLastAttempt] = useState(null); // { broughtNewMember, newMemberName }
  // Bumped by the Retry button on a preview-phase network failure to force
  // the effect below to refetch (dependency-driven, not a synchronous
  // setState-in-effect reset).
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;

    getAttendPreview(code)
      .then((res) => {
        if (cancelled) return;
        const data = res.data;
        setPreview(data);

        if (data.state === "ended") {
          setErrorKind("ended");
          setErrorPhase("preview");
          setStatus("error");
        } else if (data.state === "not_started") {
          setErrorKind("notStarted");
          setErrorPhase("preview");
          setStatus("error");
        } else if (data.action === "sign_in" && data.signed_in_at) {
          setErrorKind("alreadyCheckedIn");
          setErrorPhase("preview");
          setStatus("error");
        } else if (data.action === "sign_out" && data.signed_out_at) {
          setErrorKind("alreadySignedOut");
          setErrorPhase("preview");
          setStatus("error");
        } else if (data.action === "sign_out" && token && !data.signed_in_at) {
          setErrorKind("noCheckIn");
          setErrorPhase("preview");
          setStatus("error");
        } else if (!token) {
          setStatus("unauthenticated");
        } else {
          setStatus("confirm");
        }
      })
      .catch((err) => {
        if (cancelled) return;
        setErrorKind(err.response?.status === 404 ? "invalidCode" : "network");
        setErrorPhase("preview");
        setStatus("error");
      });

    return () => {
      cancelled = true;
    };
    // Reads `token` once per fetch by design — a fresh scan/page-load, not a
    // live subscription that should refire on every unrelated auth change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code, attempt]);

  function submit(broughtNewMember, newMemberName) {
    setLastAttempt({ broughtNewMember, newMemberName });
    setStatus("submitting");
    attendEvent(code, { broughtNewMember, newMemberName })
      .then((res) => {
        const body = res.data;
        setResult(body);
        if (body.status === "already_recorded") {
          setErrorKind(body.action === "sign_in" ? "alreadyCheckedIn" : "alreadySignedOut");
          setErrorPhase("submit");
          setStatus("error");
          return;
        }
        setStatus("success");
        refreshUser();
      })
      .catch((err) => {
        const s = err.response?.status;
        if (!err.response) setErrorKind("network");
        else if (s === 404) setErrorKind("invalidCode");
        else if (s === 410) setErrorKind("ended");
        else if (s === 425) setErrorKind("notStarted");
        else if (s === 400) setErrorKind("noCheckIn");
        else setErrorKind("network");
        setErrorPhase("submit");
        setStatus("error");
      });
  }

  function retry() {
    if (errorPhase === "preview") {
      setStatus("verifying");
      setErrorKind(null);
      setAttempt((a) => a + 1);
    } else if (lastAttempt) {
      submit(lastAttempt.broughtNewMember, lastAttempt.newMemberName);
    }
  }

  if (status === "verifying") {
    return (
      <Shell>
        <Spinner caption="Checking your code…" />
      </Shell>
    );
  }

  if (status === "unauthenticated") {
    return (
      <Shell>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", gap: "22px" }}>
          <Reveal>
            <img src={shpeMark} alt="" width={56} height={56} style={{ marginBottom: "6px" }} />
          </Reveal>
          <Reveal delay={0.08} style={{ display: "flex", flexDirection: "column", gap: "10px", maxWidth: "320px" }}>
            <h2 style={{ margin: 0, fontSize: "30px", fontWeight: 700, lineHeight: 1.15, letterSpacing: "-.01em" }}>
              Sign in to check in.
            </h2>
            <p style={{ margin: 0, fontSize: "17px", lineHeight: 1.5, color: "rgba(255,255,255,.82)" }}>
              Sign in to record your attendance at <strong style={{ color: "#fff" }}>{preview?.title}</strong>.
            </p>
          </Reveal>
          <Reveal delay={0.16} style={{ width: "100%", maxWidth: "320px" }}>
            <PrimaryCta onClick={() => navigate("/signin", { state: { from: location } })}>Sign in</PrimaryCta>
          </Reveal>
        </div>
      </Shell>
    );
  }

  if (status === "confirm") {
    const isSignOut = preview.action === "sign_out";
    return (
      <Shell>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", gap: "22px", paddingTop: "26px" }}>
          <Reveal>
            <EventSummaryCard event={preview} />
          </Reveal>
          <Reveal delay={0.08}>
            <p style={{ margin: 0, fontSize: "15px", color: "rgba(255,255,255,.75)" }}>
              Signed in as{" "}
              <strong style={{ color: "#fff" }}>
                {user?.first_name} {user?.last_name}
              </strong>
            </p>
          </Reveal>
          <Reveal delay={0.14}>
            <PrimaryCta onClick={() => (isSignOut ? submit(false, null) : setStatus("guestQuestion"))}>
              {isSignOut ? "Confirm sign-out" : "Confirm check-in"}
            </PrimaryCta>
          </Reveal>
        </div>
      </Shell>
    );
  }

  if (status === "guestQuestion") {
    return (
      <Shell>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", gap: "24px", paddingTop: "26px" }}>
          <div style={{ display: "flex", gap: "6px" }}>
            <span style={dotStyle(true)} />
            <span style={dotStyle(false)} />
          </div>
          <Reveal>
            <h2 style={{ margin: 0, fontSize: "26px", fontWeight: 700, lineHeight: 1.25 }}>Did you bring a new member?</h2>
          </Reveal>
          <Reveal delay={0.08} style={{ display: "flex", gap: "12px" }}>
            <button type="button" onClick={() => setStatus("guestCapture")} style={pillChoiceStyle(true)}>
              Yes
            </button>
            <button type="button" onClick={() => submit(false, null)} style={pillChoiceStyle(false)}>
              No
            </button>
          </Reveal>
        </div>
      </Shell>
    );
  }

  if (status === "guestCapture") {
    return (
      <Shell>
        <div style={{ display: "flex", gap: "6px", paddingTop: "26px", marginBottom: "24px" }}>
          <span style={dotStyle(true)} />
          <span style={dotStyle(true)} />
        </div>
        <div style={{ flex: 1, minHeight: 0, overflowY: "auto" }}>
          <h2 style={{ margin: "0 0 6px", fontSize: "24px", fontWeight: 700 }}>Who did you bring?</h2>
          <p style={{ margin: "0 0 18px", fontSize: "15px", color: "rgba(255,255,255,.75)" }}>
            Optional — you can skip this and still get credit.
          </p>
          <input
            className="attendInput"
            value={guestName}
            onChange={(e) => setGuestName(e.target.value)}
            placeholder="New member's name"
          />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "10px", paddingTop: "18px" }}>
          <PrimaryCta onClick={() => submit(true, guestName.trim() || null)}>Continue</PrimaryCta>
          <button
            type="button"
            onClick={() => submit(true, null)}
            style={{ background: "none", border: "none", color: "rgba(255,255,255,.75)", fontSize: "14px", fontWeight: 600, padding: "8px", cursor: "pointer" }}
          >
            Skip
          </button>
        </div>
      </Shell>
    );
  }

  if (status === "submitting") {
    return (
      <Shell>
        <Spinner caption="Recording your check-in…" />
      </Shell>
    );
  }

  if (status === "success") {
    const isSignOut = result?.action === "sign_out";
    return (
      <Shell flat>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", gap: "22px" }}>
          <Reveal>
            <CheckInSuccess />
          </Reveal>
          <Reveal delay={0.15} style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <h2 style={{ margin: 0, fontSize: "26px", fontWeight: 700 }}>{isSignOut ? "Signed out!" : "You're checked in!"}</h2>
            {result?.points_awarded > 0 && (
              <p style={{ margin: 0, fontSize: "17px", fontWeight: 600, color: "rgba(255,255,255,.85)" }}>
                +{result.points_awarded} points earned
              </p>
            )}
          </Reveal>
          <Reveal delay={0.3} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "4px" }}>
            <span style={{ fontSize: "44px", fontWeight: 800, lineHeight: 1 }}>{result?.total_points ?? 0}</span>
            <span style={{ fontSize: "11px", fontWeight: 700, letterSpacing: ".1em", textTransform: "uppercase", color: "rgba(255,255,255,.65)" }}>
              SHPE Points
            </span>
          </Reveal>
          {isSignOut ? (
            <Reveal delay={0.4}>
              <p style={{ margin: 0, fontSize: "16px", color: "rgba(255,255,255,.85)", maxWidth: "300px" }}>
                Gracias for coming out, {user?.first_name}. See you at the next one.
              </p>
            </Reveal>
          ) : (
            <Reveal delay={0.4} style={{ width: "100%", maxWidth: "320px" }}>
              <div style={{ background: "rgba(255,255,255,.12)", borderRadius: "14px", padding: "16px 18px", fontSize: "14px", lineHeight: 1.45, color: "rgba(255,255,255,.85)" }}>
                Don't forget to scan the sign-out code before you leave.
              </div>
            </Reveal>
          )}
        </div>
      </Shell>
    );
  }

  // --- error (terminal, except network which offers Retry) ---
  const copy = ERROR_COPY[errorKind] ?? ERROR_COPY.network;
  const ctx = {
    signedInAt: result?.signed_in_at ?? preview?.signed_in_at,
    signedOutAt: result?.signed_out_at ?? preview?.signed_out_at,
    startTime: preview?.start_time,
  };
  return (
    <Shell flat>
      <ErrorScreen title={copy.title} body={copy.body(ctx)} onRetry={errorKind === "network" ? retry : null} />
    </Shell>
  );
}
