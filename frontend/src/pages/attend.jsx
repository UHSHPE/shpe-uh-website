import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { attendEvent, getAttendPreview } from "../api/api";
import {
  AttendanceShell,
  AttendanceSpinner,
} from "../components/attendance/AttendanceLayout";
import { ATTENDANCE_ERRORS } from "../components/attendance/attendanceErrors";
import {
  AttendanceErrorScreen,
  AttendanceSuccessScreen,
  ConfirmAttendanceScreen,
  GuestCaptureScreen,
  GuestQuestionScreen,
  SignInScreen,
} from "../components/attendance/AttendanceScreens";
import { useAuth } from "../context/AuthContext";
import useDocumentTitle from "../hooks/useDocumentTitle";

export default function Attend() {
  useDocumentTitle("Check In");
  const { code } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { token, user, refreshUser } = useAuth();
  const [status, setStatus] = useState("verifying");
  const [errorKind, setErrorKind] = useState(null);
  const [errorPhase, setErrorPhase] = useState(null);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [guestName, setGuestName] = useState("");
  const [lastAttempt, setLastAttempt] = useState(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getAttendPreview(code)
      .then((response) => {
        if (cancelled) return;
        const data = response.data;
        setPreview(data);
        if (data.state === "ended") showError("ended", "preview");
        else if (data.state === "not_started")
          showError("notStarted", "preview");
        else if (data.action === "sign_in" && data.signed_in_at)
          showError("alreadyCheckedIn", "preview");
        else if (data.action === "sign_out" && data.signed_out_at)
          showError("alreadySignedOut", "preview");
        else if (data.action === "sign_out" && token && !data.signed_in_at)
          showError("noCheckIn", "preview");
        else setStatus(token ? "confirm" : "unauthenticated");
      })
      .catch((error) => {
        if (cancelled) return;
        showError(
          error.response?.status === 404 ? "invalidCode" : "network",
          "preview",
        );
      });
    return () => {
      cancelled = true;
    };
    // A retry increments attempt. Unrelated auth changes should not refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code, attempt]);

  function showError(kind, phase) {
    setErrorKind(kind);
    setErrorPhase(phase);
    setStatus("error");
  }

  function submit(broughtNewMember, newMemberName) {
    setLastAttempt({ broughtNewMember, newMemberName });
    setStatus("submitting");
    attendEvent(code, { broughtNewMember, newMemberName })
      .then((response) => {
        const data = response.data;
        setResult(data);
        if (data.status === "already_recorded") {
          showError(
            data.action === "sign_in" ? "alreadyCheckedIn" : "alreadySignedOut",
            "submit",
          );
          return;
        }
        setStatus("success");
        refreshUser();
      })
      .catch((error) => {
        const responseStatus = error.response?.status;
        let kind = "network";
        if (responseStatus === 404) kind = "invalidCode";
        else if (responseStatus === 410) kind = "ended";
        else if (responseStatus === 425) kind = "notStarted";
        else if (responseStatus === 400) kind = "noCheckIn";
        showError(kind, "submit");
      });
  }

  function retry() {
    if (errorPhase === "preview") {
      setStatus("verifying");
      setErrorKind(null);
      setAttempt((value) => value + 1);
    } else if (lastAttempt) {
      submit(lastAttempt.broughtNewMember, lastAttempt.newMemberName);
    }
  }

  if (status === "verifying")
    return (
      <AttendanceShell>
        <AttendanceSpinner caption="Checking your code…" />
      </AttendanceShell>
    );
  if (status === "unauthenticated")
    return (
      <SignInScreen
        preview={preview}
        onSignIn={() => navigate("/signin", { state: { from: location } })}
      />
    );
  if (status === "confirm")
    return (
      <ConfirmAttendanceScreen
        preview={preview}
        user={user}
        onConfirm={() =>
          preview.action === "sign_out"
            ? submit(false, null)
            : setStatus("guestQuestion")
        }
      />
    );
  if (status === "guestQuestion")
    return (
      <GuestQuestionScreen
        onYes={() => setStatus("guestCapture")}
        onNo={() => submit(false, null)}
      />
    );
  if (status === "guestCapture")
    return (
      <GuestCaptureScreen
        guestName={guestName}
        onNameChange={setGuestName}
        onContinue={() => submit(true, guestName.trim() || null)}
        onSkip={() => submit(true, null)}
      />
    );
  if (status === "submitting")
    return (
      <AttendanceShell>
        <AttendanceSpinner caption="Recording your check-in…" />
      </AttendanceShell>
    );
  if (status === "success")
    return <AttendanceSuccessScreen result={result} user={user} />;

  const error = ATTENDANCE_ERRORS[errorKind] ?? ATTENDANCE_ERRORS.network;
  const context = {
    signedInAt: result?.signed_in_at ?? preview?.signed_in_at,
    signedOutAt: result?.signed_out_at ?? preview?.signed_out_at,
    startTime: preview?.start_time,
  };
  return (
    <AttendanceErrorScreen
      title={error.title}
      body={error.body(context)}
      onRetry={errorKind === "network" ? retry : null}
    />
  );
}
