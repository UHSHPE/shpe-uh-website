import { api, authHeaders } from "./client";

export function getAdminMembers(params = {}) {
  return api.get("/admin/members", { headers: authHeaders(), params });
}

export function getAdminMember(userId) {
  return api.get(`/admin/members/${userId}`, { headers: authHeaders() });
}

export function getMemberResumeBlob(userId) {
  return api.get(`/admin/members/${userId}/resume`, {
    headers: authHeaders(),
    responseType: "blob",
  });
}

export function getAdminStats() {
  return api.get("/admin/stats", { headers: authHeaders() });
}

export function getAssignableRoles() {
  return api.get("/admin/roles", { headers: authHeaders() });
}

export function updateMemberRole(userId, role) {
  return api.patch(
    `/admin/members/${userId}/role`,
    { role },
    { headers: authHeaders() },
  );
}

export function getOrgStructure() {
  return api.get("/admin/structure", { headers: authHeaders() });
}

export function setRoleSupervisor(role, supervisorRole) {
  return api.put(
    `/admin/structure/${encodeURIComponent(role)}`,
    { supervisor_role: supervisorRole },
    { headers: authHeaders() },
  );
}
