import { api, authHeaders } from "./client";

export function getUpcomingEvents(days = 7) {
  return api.get(`/events/upcoming?days=${days}`, { headers: authHeaders() });
}

export function getAllEvents() {
  return api.get("/events");
}

export function setEventReminder(eventId) {
  return api.post(`/events/${eventId}/remind`, {}, { headers: authHeaders() });
}

export function cancelEventReminder(eventId) {
  return api.delete(`/events/${eventId}/remind`, { headers: authHeaders() });
}

export function getMyReminders() {
  return api.get("/events/reminders/me", { headers: authHeaders() });
}

export function attendEvent(code, { broughtNewMember, newMemberName } = {}) {
  return api.post(
    "/events/attend",
    {
      code,
      brought_new_member: broughtNewMember ?? false,
      new_member_name: newMemberName ?? null,
    },
    { headers: authHeaders() },
  );
}

export function getMyEvents() {
  return api.get("/events/mine", { headers: authHeaders() });
}

export function getAllChairEvents() {
  return api.get("/events/all", { headers: authHeaders() });
}

export function getEventStats(eventId) {
  return api.get(`/events/${eventId}/stats`, { headers: authHeaders() });
}

export function getEventAttendance(eventId) {
  return api.get(`/events/${eventId}/attendance`, { headers: authHeaders() });
}

// Public preview with optional auth: a token adds the caller's attendance state.
export function getAttendPreview(code) {
  return api.get(`/events/code/${code}`, { headers: authHeaders() });
}

export function getEventScanCount(eventId) {
  return api.get(`/events/${eventId}/scan-count`, { headers: authHeaders() });
}
