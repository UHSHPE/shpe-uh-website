import { useEffect, useMemo, useRef, useState } from "react";

import {
  deleteGalleryPhoto,
  getAdminGalleryPhotoImage,
  getAdminGalleryPhotos,
  updateGalleryPhoto,
} from "../../api/api";
import usePagination from "../../hooks/usePagination";
import { formatGalleryDate, gallerySectionTitle } from "../../utils/gallery";
import Pagination from "../Pagination";

const FILTERS = ["pending", "approved", "rejected", "all"];

function AdminThumbnail({ photoId, alt, onOpen }) {
  const [url, setUrl] = useState("");
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    let objectUrl = "";
    getAdminGalleryPhotoImage(photoId)
      .then((response) => {
        objectUrl = URL.createObjectURL(response.data);
        if (active) setUrl(objectUrl);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [photoId]);

  if (failed) {
    return <div className="flex h-full items-center justify-center px-4 text-center text-sm text-[var(--muted)]">Preview unavailable</div>;
  }
  if (!url) {
    return <div className="h-full animate-pulse bg-[var(--surface-soft)]" />;
  }
  return (
    <button
      type="button"
      className="group relative h-full w-full cursor-zoom-in"
      onClick={onOpen}
      aria-label={`View full-screen photo: ${alt}`}
    >
      <img src={url} alt={alt} className="h-full w-full object-cover" />
      <span className="absolute inset-x-0 bottom-0 bg-black/65 px-3 py-2 text-center text-sm font-semibold text-white opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
        View full screen
      </span>
    </button>
  );
}

function FullScreenPreview({ photo, onClose }) {
  const [url, setUrl] = useState("");
  const [failed, setFailed] = useState(false);
  const closeButtonRef = useRef(null);

  useEffect(() => {
    let active = true;
    let objectUrl = "";
    getAdminGalleryPhotoImage(photo.id)
      .then((response) => {
        objectUrl = URL.createObjectURL(response.data);
        if (active) setUrl(objectUrl);
      })
      .catch(() => {
        if (active) setFailed(true);
      });

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    function closeOnEscape(event) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", closeOnEscape);

    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [onClose, photo.id]);

  return (
    <div
      className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/90 p-4 sm:p-8"
      role="dialog"
      aria-modal="true"
      aria-label={`Full-screen photo submitted by ${photo.submitter_name}`}
      onClick={onClose}
    >
      <button
        ref={closeButtonRef}
        type="button"
        className="absolute right-4 top-4 rounded-full bg-white/15 px-4 py-2 text-2xl font-bold text-white hover:bg-white/25 focus-visible:outline focus-visible:outline-2 focus-visible:outline-white"
        onClick={onClose}
        aria-label="Close full-screen photo"
      >
        ×
      </button>

      <div className="flex h-full w-full items-center justify-center" onClick={(event) => event.stopPropagation()}>
        {failed ? (
          <p className="text-center font-semibold text-white">The full-size preview could not be loaded.</p>
        ) : url ? (
          <img
            src={url}
            alt={`Submitted by ${photo.submitter_name}`}
            className="max-h-full max-w-full object-contain"
          />
        ) : (
          <p className="text-center font-semibold text-white">Loading photo…</p>
        )}
      </div>
    </div>
  );
}

function PhotoCard({ photo, busy, onUpdate, onDelete, onPreview }) {
  const [semester, setSemester] = useState(photo.semester);
  const [year, setYear] = useState(String(photo.year));

  function update(decision) {
    onUpdate(photo.id, {
      decision,
      semester,
      year: Number(year),
    });
  }

  return (
    <article className="overflow-hidden rounded-2xl border border-[var(--border)] bg-white shadow-[var(--shadow-card)]">
      <div className="h-52 bg-[var(--surface-muted)]">
        <AdminThumbnail
          photoId={photo.id}
          alt={`Submitted by ${photo.submitter_name}`}
          onOpen={() => onPreview(photo)}
        />
      </div>
      <div className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="m-0 text-lg font-bold text-[var(--shpe-navy)]">{photo.submitter_name}</h3>
            <p className="mb-0 mt-1 text-sm text-[var(--muted)]">Submitted {formatGalleryDate(photo.submitted_at)}</p>
          </div>
          <span className="rounded-full bg-[var(--surface-tint)] px-3 py-1 text-xs font-bold capitalize text-[var(--shpe-blue)]">
            {photo.status}
          </span>
        </div>

        {photo.reviewer_name && (
          <p className="mb-0 mt-3 text-sm text-[var(--ink-soft)]">
            Reviewed by {photo.reviewer_name}
            {photo.reviewed_at ? ` · ${formatGalleryDate(photo.reviewed_at)}` : ""}
          </p>
        )}

        <div className="mt-4 grid grid-cols-2 gap-3">
          <label className="text-xs font-semibold text-[var(--ink-soft)]">
            Semester
            <select
              value={semester}
              onChange={(event) => setSemester(event.target.value)}
              className="mt-1 block w-full rounded-lg border border-[var(--border-strong)] bg-white p-2 text-sm"
            >
              <option value="spring">Spring</option>
              <option value="fall">Fall</option>
            </select>
          </label>
          <label className="text-xs font-semibold text-[var(--ink-soft)]">
            Year
            <input
              type="number"
              min="2020"
              max="2100"
              value={year}
              onChange={(event) => setYear(event.target.value)}
              className="mt-1 block w-full rounded-lg border border-[var(--border-strong)] p-2 text-sm"
            />
          </label>
        </div>

        <p className="mb-0 mt-3 text-xs text-[var(--muted)]">
          Gallery section: {gallerySectionTitle(semester, year)}
        </p>

        <div className="mt-5 flex flex-wrap gap-2">
          <button type="button" className="primaryBtn" disabled={busy} onClick={() => update("approved")}>Approve</button>
          <button type="button" className="ghostBtn" disabled={busy} onClick={() => update("rejected")}>Reject</button>
          <button
            type="button"
            className="accentBtn"
            disabled={busy}
            onClick={() => onDelete(photo)}
          >
            Delete
          </button>
        </div>
      </div>
    </article>
  );
}

export default function GalleryManager() {
  const [photos, setPhotos] = useState([]);
  const [filter, setFilter] = useState("pending");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState("");
  const [previewPhoto, setPreviewPhoto] = useState(null);

  async function loadPhotos() {
    setError("");
    try {
      const response = await getAdminGalleryPhotos("all");
      setPhotos(response.data);
    } catch (err) {
      setError(err.response?.data?.detail ?? "Gallery submissions could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPhotos();
  }, []);

  const visible = useMemo(
    () => (filter === "all" ? photos : photos.filter((photo) => photo.status === filter)),
    [filter, photos],
  );
  const pager = usePagination(visible, { pageSize: 8, resetKey: filter });

  async function updatePhoto(photoId, data) {
    setBusyId(photoId);
    setError("");
    try {
      await updateGalleryPhoto(photoId, data);
      await loadPhotos();
    } catch (err) {
      setError(err.response?.data?.detail ?? "The photo could not be updated.");
    } finally {
      setBusyId(null);
    }
  }

  async function removePhoto(photo) {
    if (!window.confirm(`Delete the photo submitted by ${photo.submitter_name}?`)) return;
    setBusyId(photo.id);
    setError("");
    try {
      await deleteGalleryPhoto(photo.id);
      await loadPhotos();
    } catch (err) {
      setError(err.response?.data?.detail ?? "The photo could not be deleted.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section>
      <div className="mb-6">
        <p className="m-0 text-sm font-bold uppercase tracking-[0.16em] text-[var(--shpe-red)]">Gallery moderation</p>
        <h1 className="mb-2 mt-1 text-4xl font-bold text-[var(--shpe-navy)]">Photo submissions</h1>
        <p className="m-0 text-[var(--muted)]">Approve photos for the public gallery, correct their section, or remove them.</p>
      </div>

      <div className="mb-6 flex flex-wrap gap-2">
        {FILTERS.map((item) => {
          const count = item === "all" ? photos.length : photos.filter((photo) => photo.status === item).length;
          const active = filter === item;
          return (
            <button
              key={item}
              type="button"
              onClick={() => setFilter(item)}
              className={`rounded-full border px-4 py-2 text-sm font-semibold capitalize ${active ? "border-[var(--shpe-blue)] bg-[var(--shpe-blue)] text-white" : "border-[var(--border)] bg-white text-[var(--ink-soft)]"}`}
            >
              {item} ({count})
            </button>
          );
        })}
      </div>

      {error && <p className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm font-semibold text-[var(--shpe-red)]">{error}</p>}
      {loading ? (
        <p className="py-12 text-center font-semibold text-[var(--muted)]">Loading submissions…</p>
      ) : visible.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-[var(--border-strong)] p-10 text-center text-[var(--muted)]">No {filter === "all" ? "gallery" : filter} photos.</p>
      ) : (
        <>
          <div className="grid gap-5 md:grid-cols-2">
            {pager.pageItems.map((photo) => (
              <PhotoCard
                key={photo.id}
                photo={photo}
                busy={busyId === photo.id}
                onUpdate={updatePhoto}
                onDelete={removePhoto}
                onPreview={setPreviewPhoto}
              />
            ))}
          </div>
          <Pagination {...pager} label="photos" />
        </>
      )}

      {previewPhoto && (
        <FullScreenPreview
          photo={previewPhoto}
          onClose={() => setPreviewPhoto(null)}
        />
      )}
    </section>
  );
}
