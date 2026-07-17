import { createContext, useContext, useState, useEffect } from "react";
import { getMe } from "../api/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("token"));
  const [user, setUser] = useState(null);

  useEffect(() => {
    if (!token) return;
    getMe(token)
      .then((res) => setUser(res.data))
      .catch(() => {
        localStorage.removeItem("token");
        setToken(null);
      });
  }, [token]);

  function login(newToken) {
    localStorage.setItem("token", newToken);
    setToken(newToken);
    getMe(newToken).then((res) => setUser(res.data));
  }

  function logout() {
    localStorage.removeItem("token");
    setToken(null);
    setUser(null);
  }

  // Re-fetch /me so computed fields update immediately (e.g. has_paid_dues
  // after paying dues — the banner disappears without a page reload).
  function refreshUser() {
    if (!token) return;
    getMe(token)
      .then((res) => setUser(res.data))
      .catch(() => {});
  }

  return (
    <AuthContext.Provider value={{ token, user, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  return useContext(AuthContext);
}
