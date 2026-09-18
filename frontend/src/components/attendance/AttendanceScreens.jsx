import CheckInSuccess from "../CheckInSuccess";
import shpeMark from "../../assets/logos/shpeMark.png";
import { formatEventTime } from "../../utils/events";
import { AttendanceShell, PrimaryCta, Reveal } from "./AttendanceLayout";

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
      <p style={{ margin: 0, fontSize: "19px", fontWeight: 700 }}>
        {event.title}
      </p>
      <p
        style={{ margin: 0, fontSize: "15px", color: "rgba(255,255,255,.85)" }}
      >
        🕒 {formatEventTime(event.start_time, event.end_time)}
      </p>
      {event.location && (
        <p
          style={{
            margin: 0,
            fontSize: "15px",
            color: "rgba(255,255,255,.85)",
          }}
        >
          📍 {event.location}
        </p>
      )}
    </div>
  );
}

const dotStyle = (filled) => ({
  width: "6px",
  height: "6px",
  borderRadius: "999px",
  background: filled ? "#fff" : "rgba(255,255,255,.3)",
});
const pillChoiceStyle = (primary) => ({
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
});

export function SignInScreen({ preview, onSignIn }) {
  return (
    <AttendanceShell>
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          gap: "22px",
        }}
      >
        <Reveal>
          <img
            src={shpeMark}
            alt=""
            width={56}
            height={56}
            style={{ marginBottom: "6px" }}
          />
        </Reveal>
        <Reveal
          delay={0.08}
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "10px",
            maxWidth: "320px",
          }}
        >
          <h2
            style={{
              margin: 0,
              fontSize: "30px",
              fontWeight: 700,
              lineHeight: 1.15,
              letterSpacing: "-.01em",
            }}
          >
            Sign in to check in.
          </h2>
          <p
            style={{
              margin: 0,
              fontSize: "17px",
              lineHeight: 1.5,
              color: "rgba(255,255,255,.82)",
            }}
          >
            Sign in to record your attendance at{" "}
            <strong style={{ color: "#fff" }}>{preview?.title}</strong>.
          </p>
        </Reveal>
        <Reveal delay={0.16} style={{ width: "100%", maxWidth: "320px" }}>
          <PrimaryCta onClick={onSignIn}>Sign in</PrimaryCta>
        </Reveal>
      </div>
    </AttendanceShell>
  );
}

export function ConfirmAttendanceScreen({ preview, user, onConfirm }) {
  const isSignOut = preview.action === "sign_out";
  return (
    <AttendanceShell>
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          gap: "22px",
          paddingTop: "26px",
        }}
      >
        <Reveal>
          <EventSummaryCard event={preview} />
        </Reveal>
        <Reveal delay={0.08}>
          <p
            style={{
              margin: 0,
              fontSize: "15px",
              color: "rgba(255,255,255,.75)",
            }}
          >
            Signed in as{" "}
            <strong style={{ color: "#fff" }}>
              {user?.first_name} {user?.last_name}
            </strong>
          </p>
        </Reveal>
        <Reveal delay={0.14}>
          <PrimaryCta onClick={onConfirm}>
            {isSignOut ? "Confirm sign-out" : "Confirm check-in"}
          </PrimaryCta>
        </Reveal>
      </div>
    </AttendanceShell>
  );
}

export function GuestQuestionScreen({ onYes, onNo }) {
  return (
    <AttendanceShell>
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          gap: "24px",
          paddingTop: "26px",
        }}
      >
        <div style={{ display: "flex", gap: "6px" }}>
          <span style={dotStyle(true)} />
          <span style={dotStyle(false)} />
        </div>
        <Reveal>
          <h2
            style={{
              margin: 0,
              fontSize: "26px",
              fontWeight: 700,
              lineHeight: 1.25,
            }}
          >
            Did you bring a new member?
          </h2>
        </Reveal>
        <Reveal delay={0.08} style={{ display: "flex", gap: "12px" }}>
          <button type="button" onClick={onYes} style={pillChoiceStyle(true)}>
            Yes
          </button>
          <button type="button" onClick={onNo} style={pillChoiceStyle(false)}>
            No
          </button>
        </Reveal>
      </div>
    </AttendanceShell>
  );
}

export function GuestCaptureScreen({
  guestName,
  onNameChange,
  onContinue,
  onSkip,
}) {
  return (
    <AttendanceShell>
      <div
        style={{
          display: "flex",
          gap: "6px",
          paddingTop: "26px",
          marginBottom: "24px",
        }}
      >
        <span style={dotStyle(true)} />
        <span style={dotStyle(true)} />
      </div>
      <div style={{ flex: 1, minHeight: 0, overflowY: "auto" }}>
        <h2 style={{ margin: "0 0 6px", fontSize: "24px", fontWeight: 700 }}>
          Who did you bring?
        </h2>
        <p
          style={{
            margin: "0 0 18px",
            fontSize: "15px",
            color: "rgba(255,255,255,.75)",
          }}
        >
          Optional — you can skip this and still get credit.
        </p>
        <input
          className="attendInput"
          value={guestName}
          onChange={(event) => onNameChange(event.target.value)}
          placeholder="New member's name"
        />
      </div>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "10px",
          paddingTop: "18px",
        }}
      >
        <PrimaryCta onClick={onContinue}>Continue</PrimaryCta>
        <button
          type="button"
          onClick={onSkip}
          style={{
            background: "none",
            border: "none",
            color: "rgba(255,255,255,.75)",
            fontSize: "14px",
            fontWeight: 600,
            padding: "8px",
            cursor: "pointer",
          }}
        >
          Skip
        </button>
      </div>
    </AttendanceShell>
  );
}

export function AttendanceSuccessScreen({ result, user }) {
  const isSignOut = result?.action === "sign_out";
  return (
    <AttendanceShell flat>
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          gap: "22px",
        }}
      >
        <Reveal>
          <CheckInSuccess />
        </Reveal>
        <Reveal
          delay={0.15}
          style={{ display: "flex", flexDirection: "column", gap: "6px" }}
        >
          <h2 style={{ margin: 0, fontSize: "26px", fontWeight: 700 }}>
            {isSignOut ? "Signed out!" : "You're checked in!"}
          </h2>
          {result?.points_awarded > 0 && (
            <p
              style={{
                margin: 0,
                fontSize: "17px",
                fontWeight: 600,
                color: "rgba(255,255,255,.85)",
              }}
            >
              +{result.points_awarded} points earned
            </p>
          )}
        </Reveal>
        <Reveal
          delay={0.3}
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "4px",
          }}
        >
          <span style={{ fontSize: "44px", fontWeight: 800, lineHeight: 1 }}>
            {result?.total_points ?? 0}
          </span>
          <span
            style={{
              fontSize: "11px",
              fontWeight: 700,
              letterSpacing: ".1em",
              textTransform: "uppercase",
              color: "rgba(255,255,255,.65)",
            }}
          >
            SHPE Points
          </span>
        </Reveal>
        {isSignOut ? (
          <Reveal delay={0.4}>
            <p
              style={{
                margin: 0,
                fontSize: "16px",
                color: "rgba(255,255,255,.85)",
                maxWidth: "300px",
              }}
            >
              Gracias for coming out, {user?.first_name}. See you at the next
              one.
            </p>
          </Reveal>
        ) : (
          <Reveal delay={0.4} style={{ width: "100%", maxWidth: "320px" }}>
            <div
              style={{
                background: "rgba(255,255,255,.12)",
                borderRadius: "14px",
                padding: "16px 18px",
                fontSize: "14px",
                lineHeight: 1.45,
                color: "rgba(255,255,255,.85)",
              }}
            >
              Don't forget to scan the sign-out code before you leave.
            </div>
          </Reveal>
        )}
      </div>
    </AttendanceShell>
  );
}

export function AttendanceErrorScreen({ title, body, onRetry }) {
  return (
    <AttendanceShell flat>
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          gap: "22px",
        }}
      >
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
        <Reveal
          delay={0.1}
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "10px",
            maxWidth: "320px",
          }}
        >
          <h2
            style={{
              margin: 0,
              fontSize: "26px",
              fontWeight: 700,
              lineHeight: 1.2,
              letterSpacing: "-.01em",
            }}
          >
            {title}
          </h2>
          <p
            style={{
              margin: 0,
              fontSize: "16px",
              lineHeight: 1.45,
              color: "rgba(255,255,255,.75)",
            }}
          >
            {body}
          </p>
        </Reveal>
        {onRetry && (
          <Reveal delay={0.18} style={{ width: "100%", maxWidth: "320px" }}>
            <PrimaryCta onClick={onRetry}>Retry</PrimaryCta>
          </Reveal>
        )}
      </div>
    </AttendanceShell>
  );
}
