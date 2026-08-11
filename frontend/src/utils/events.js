// Shared helpers for the QR check-in / chair Events surfaces. Pure helpers
// only, no component export here — react-refresh's lint rule fails any file
// that exports both a component and a helper (same reason utils/shop.js has
// no JSX and StatusPill is its own file).

// event_type is a snake_case slug produced by
// event_tracker_services.get_event_type() (a Role name minus "_chair", e.g.
// "academic", "web_dev", or the "eboard" catch-all) — NOT the display
// strings ('General Meeting' | 'Professional' | 'Outreach' | 'Social' |
// 'SRT') that calendar.jsx's and dashboard.jsx's older EVENT_TYPE_COLORS
// maps are keyed on. The API never returns those display strings, so both
// of those maps only ever hit their `?? '#0070C0'` fallback and the badge
// renders the raw slug. This file is the real slug -> label/color map;
// re-pointing calendar.jsx/dashboard.jsx at it is a small follow-on
// cleanup, not required for the QR check-in feature itself.
export const EVENT_TYPE_LABELS = {
  eboard: "E-Board",
  academic: "Academic",
  athletic: "Athletic",
  career_fair: "Career Fair",
  eec: "Engineering Events",
  marketing: "Marketing",
  member_relations: "Member Relations",
  mentorshpe: "MentorSHPE",
  outreach: "Outreach",
  professional: "Professional",
  projects: "Projects",
  shpe_jr: "SHPE Jr",
  shpetina: "SHPEtina",
  social: "Social",
  web_dev: "Web Development",
};

// Slug -> a --event-* design token, grouped by design intent (general /
// professional / outreach / social / SRT accents) rather than 1:1 with the
// slug — there are 14 chair slugs plus "eboard" but only 5 accent tokens.
const EVENT_TYPE_COLOR_TOKENS = {
  eboard: "var(--event-general)",
  academic: "var(--event-professional)",
  professional: "var(--event-professional)",
  career_fair: "var(--event-professional)",
  web_dev: "var(--event-professional)",
  projects: "var(--event-professional)",
  eec: "var(--event-srt)",
  athletic: "var(--event-srt)",
  outreach: "var(--event-outreach)",
  member_relations: "var(--event-outreach)",
  marketing: "var(--event-outreach)",
  social: "var(--event-social)",
  shpetina: "var(--event-social)",
  mentorshpe: "var(--event-social)",
  shpe_jr: "var(--event-social)",
};

export function eventTypeLabel(type) {
  if (!type) return "General";
  return EVENT_TYPE_LABELS[type] ?? type.replace(/_/g, " ");
}

export function eventColor(type) {
  return EVENT_TYPE_COLOR_TOKENS[type] ?? "var(--event-general)";
}

// Stored datetimes are naive UTC — append 'Z' so the browser reads them as
// UTC (see CLAUDE.md "SQLite / datetime note").
export function parseUTC(str) {
  return str ? new Date(str + "Z") : null;
}

export function formatEventDay(startStr) {
  const start = parseUTC(startStr);
  return new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  }).format(start);
}

export function formatEventTime(startStr, endStr) {
  const start = parseUTC(startStr);
  const end = endStr ? parseUTC(endStr) : null;
  const timeFmt = new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
  return timeFmt.format(start) + (end ? ` – ${timeFmt.format(end)}` : "");
}

export function formatClock(str) {
  if (!str) return null;
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  }).format(parseUTC(str));
}

// Duration between two naive-UTC ISO timestamps, e.g. "1h 24m". Returns
// null when either side is missing or the math doesn't make sense.
export function formatDuration(startStr, endStr) {
  if (!startStr || !endStr) return null;
  const ms = parseUTC(endStr) - parseUTC(startStr);
  if (!(ms > 0)) return null;
  const totalMinutes = Math.round(ms / 60000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) return `${minutes}m`;
  if (minutes === 0) return `${hours}h`;
  return `${hours}h ${minutes}m`;
}
