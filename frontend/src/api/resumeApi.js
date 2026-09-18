import { api, authHeaders } from "./client";

export function uploadResume(file) {
  const formData = new FormData();
  formData.append("file", file);
  return api.post("/me/resume", formData, { headers: authHeaders() });
}

export function getResumeBlob() {
  return api.get("/me/resume", {
    headers: authHeaders(),
    responseType: "blob",
  });
}

export function deleteResume() {
  return api.delete("/me/resume", { headers: authHeaders() });
}
