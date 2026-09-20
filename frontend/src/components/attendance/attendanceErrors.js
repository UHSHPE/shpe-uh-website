import { formatClock, formatDuration } from "../../utils/events";

export const ATTENDANCE_ERRORS = {
  alreadyCheckedIn: {
    title: "You're already checked in",
    body: (context) =>
      context.signedInAt
        ? `Checked in at ${formatClock(context.signedInAt)}. Your credit is already recorded — no need to scan again.`
        : "Your credit is already recorded — no need to scan again.",
  },
  alreadySignedOut: {
    title: "You're already signed out",
    body: (context) => {
      const duration = formatDuration(context.signedInAt, context.signedOutAt);
      return duration
        ? `You attended for ${duration}. Your points are recorded.`
        : "Your sign-out is already recorded. Your points are recorded.";
    },
  },
  noCheckIn: {
    title: "No check-in on record",
    body: () =>
      "We don't have a sign-in for you at this event. Please see a chair at the door.",
  },
  invalidCode: {
    title: "This code isn't valid",
    body: () =>
      "It may have expired or been mistyped. Ask a chair for a fresh code.",
  },
  notStarted: {
    title: "Check-in hasn't opened yet",
    body: (context) =>
      context.startTime
        ? `Check-in opens closer to ${formatClock(context.startTime)}. Come back then.`
        : "Come back closer to the event start time.",
  },
  ended: {
    title: "This code has expired",
    body: () =>
      "This event has already ended. Ask a chair if you still need credit.",
  },
  network: {
    title: "Something went wrong",
    body: () =>
      "We couldn't reach the server. Check your connection and retry — a chair can also add you manually.",
  },
};
