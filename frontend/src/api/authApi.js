import { api } from "./client";

export function loginUser(email, password) {
  const params = new URLSearchParams();
  params.append("username", email);
  params.append("password", password);
  return api.post("/login", params, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
}

export function signupUser(data) {
  return api.post("/signup", data);
}

export function requestPasswordReset(email) {
  return api.post("/password-reset/request", { email });
}

export function confirmPasswordReset(token, newPassword) {
  return api.post("/password-reset/confirm", {
    token,
    new_password: newPassword,
  });
}

export function verifyEmail(token) {
  return api.post("/verify-email", { token });
}

export function getMe(token) {
  return api.get("/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
}
