import axios from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
});

let onUnauthorized = null;

export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

export function authHeaders() {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// A 401 from a credential endpoint describes that request; it does not mean
// an existing session expired and should be cleared.
const CREDENTIAL_PATHS = [
  "/login",
  "/signup",
  "/verify-email",
  "/password-reset",
];

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = error.config?.url ?? "";
    const isCredentialCall = CREDENTIAL_PATHS.some((path) =>
      url.startsWith(path),
    );
    if (error.response?.status === 401 && !isCredentialCall) {
      localStorage.removeItem("token");
      onUnauthorized?.();
    }
    return Promise.reject(error);
  },
);
