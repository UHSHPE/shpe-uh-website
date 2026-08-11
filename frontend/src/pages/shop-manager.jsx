import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import ShopManager from '../components/ShopManager';
import { isShopManager } from '../utils/shop';
import useDocumentTitle from "../hooks/useDocumentTitle";

// Dedicated shop-management page for shop admins (comms director / marketing
// chair — anyone isShopManager returns true for). Its route is wrapped in
// PrivateRoute (must be signed in); this also bounces signed-in NON-managers
// away from the admin tools. Previously this panel lived on the profile page.
export default function ShopManagerPage() {
  useDocumentTitle("Shop Manager");
  const { user } = useAuth();

  // PrivateRoute already waits for the user to load, but guard defensively.
  if (!user) {
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

  if (!isShopManager(user)) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div style={{
      maxWidth: '1040px',
      margin: '0 auto',
      padding: '96px 20px 80px',
      fontFamily: 'Work Sans, sans-serif',
    }}>
      <ShopManager />
    </div>
  );
}
