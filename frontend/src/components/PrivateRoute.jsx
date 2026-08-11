import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function PrivateRoute({ children }) {
  const { token, user } = useAuth();
  const location = useLocation();

  // Token exists but user hasn't loaded from getMe yet — wait
  if (token && !user) {
    return (
      <div style={{
        minHeight: '60vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--blue)',
        fontWeight: 600,
        fontFamily: 'Work Sans, sans-serif',
      }}>
        Loading…
      </div>
    );
  }

  if (!token) {
    return <Navigate to="/signin" state={{ from: location }} replace />;
  }

  return children;
}
