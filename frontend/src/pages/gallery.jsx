import GalleryApproved from "../components/GalleryApproved";
import useDocumentTitle from "../hooks/useDocumentTitle";

export default function Gallery() {
  useDocumentTitle("Gallery");
  // Header and Footer are already rendered globally in App.jsx.
  return (
    <div className="bg-white min-h-screen pt-10">
      <GalleryApproved />
    </div>
  );
}