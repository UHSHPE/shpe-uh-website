import { Navigate } from "react-router-dom";

import GalleryManager from "../components/gallery/GalleryManager";
import { useAuth } from "../context/AuthContext";
import useDocumentTitle from "../hooks/useDocumentTitle";
import { isGalleryAdmin } from "../utils/gallery";

export default function GalleryManagerPage() {
  useDocumentTitle("Gallery Manager");
  const { user } = useAuth();

  if (!user) {
    return <p className="py-20 text-center font-semibold text-[var(--muted)]">Loading…</p>;
  }
  if (!isGalleryAdmin(user)) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className="mx-auto w-full max-w-[1100px] px-5 py-10">
      <GalleryManager />
    </div>
  );
}
