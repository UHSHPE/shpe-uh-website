import GalleryApproved from "../components/gallery/GalleryApproved";
import useDocumentTitle from "../hooks/useDocumentTitle";

export default function Gallery() {
  useDocumentTitle("Gallery");
  return (
    <div className="bg-white min-h-screen">
      <GalleryApproved />
    </div>
  );
}
