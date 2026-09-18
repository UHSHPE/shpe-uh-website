import { api, authHeaders } from "./client";

export function getNotifications() {
  return api.get("/notifications", { headers: authHeaders() });
}

export function markNotificationRead(notificationId) {
  return api.post(
    `/notifications/${notificationId}/read`,
    {},
    { headers: authHeaders() },
  );
}
