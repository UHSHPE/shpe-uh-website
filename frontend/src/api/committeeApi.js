import { api, authHeaders } from "./client";

export function getCommittees() {
  return api.get("/committees", { headers: authHeaders() });
}

export function joinCommittee(committeeId) {
  return api.post(
    `/committees/${committeeId}/join`,
    {},
    { headers: authHeaders() },
  );
}

export function leaveCommittee(committeeId) {
  return api.delete(`/committees/${committeeId}/leave`, {
    headers: authHeaders(),
  });
}

export function getCommitteeMembers(committeeId) {
  return api.get(`/committees/${committeeId}/members`, {
    headers: authHeaders(),
  });
}

export function getCommitteeMessages(committeeId) {
  return api.get(`/committees/${committeeId}/messages`, {
    headers: authHeaders(),
  });
}

export function sendCommitteeMessage(committeeId, body) {
  return api.post(
    `/committees/${committeeId}/messages`,
    { body },
    { headers: authHeaders() },
  );
}
