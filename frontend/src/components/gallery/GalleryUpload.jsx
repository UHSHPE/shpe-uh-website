import { useRef, useState } from "react";
import { Link } from "react-router-dom";

import { submitGalleryPhotos } from "../../api/api";
import { useAuth } from "../../context/AuthContext";

const MAX_IMAGE_BYTES = 2 * 1024 * 1024;
const MAX_PHOTOS_PER_SUBMISSION = 3;
const ALLOWED_TYPES = new Set(["image/png", "image/jpeg"]);

export default function GalleryUpload() {
  const { user } = useAuth();
  const inputRef = useRef(null);
  const [files, setFiles] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  function chooseFile(event) {
    const selected = Array.from(event.target.files ?? []);
    setMessage("");
    setError("");

    if (selected.length === 0) {
      setFiles([]);
      return;
    }
    if (selected.length > MAX_PHOTOS_PER_SUBMISSION) {
      setFiles([]);
      setError("Choose up to 3 photos per submission.");
      event.target.value = "";
      return;
    }
    if (selected.some((file) => !ALLOWED_TYPES.has(file.type))) {
      setFiles([]);
      setError("Every photo must be a PNG or JPEG image.");
      event.target.value = "";
      return;
    }
    if (selected.some((file) => file.size > MAX_IMAGE_BYTES)) {
      setFiles([]);
      setError("Each image must be 2 MB or smaller.");
      event.target.value = "";
      return;
    }
    setFiles(selected);
  }

  async function submit(event) {
    event.preventDefault();
    if (files.length === 0 || submitting) return;

    setSubmitting(true);
    setError("");
    setMessage("");
    try {
      await submitGalleryPhotos(files);
      setFiles([]);
      if (inputRef.current) inputRef.current.value = "";
      setMessage("Photos submitted for review. You’ll earn a point for each approved photo.");
    } catch (err) {
      setError(err.response?.data?.detail ?? "The photo could not be submitted.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="mx-auto mt-10 w-full max-w-[760px] px-4">
      <div className="rounded-[25px] border border-[var(--border)] bg-[var(--surface-tint)] p-6 text-center shadow-[var(--shadow-card)] sm:p-8">
        <p className="m-0 text-[clamp(26px,4vw,35px)] font-semibold tracking-[-0.7px] text-[var(--shpe-blue-mid)]">
          Want to earn points?
        </p>
        <p className="mx-auto mb-5 mt-2 max-w-[560px] text-[15px] text-[var(--ink-soft)]">
          Submit up to 3 PNG or JPEG photos from a SHPE event. You can make 5 submissions each week, and photos stay private until a reviewer approves them.
        </p>

        {user ? (
          <form onSubmit={submit} className="flex flex-col items-center gap-3">
            <input
              ref={inputRef}
              type="file"
              accept="image/png,image/jpeg"
              multiple
              onChange={chooseFile}
              className="block w-full max-w-[500px] rounded-xl border border-[var(--border-strong)] bg-white p-3 text-sm text-[var(--ink-soft)] file:mr-3 file:rounded-full file:border-0 file:bg-[var(--surface-tint)] file:px-4 file:py-2 file:font-semibold file:text-[var(--shpe-blue)]"
            />
            <button
              type="submit"
              className="primaryBtn"
              disabled={files.length === 0 || submitting}
              style={{ opacity: files.length === 0 || submitting ? 0.55 : 1 }}
            >
              {submitting
                ? "Submitting…"
                : files.length > 0
                  ? `Submit ${files.length} photo${files.length === 1 ? "" : "s"}`
                  : "Submit photos"}
            </button>
          </form>
        ) : (
          <Link to="/signin" className="primaryBtn inline-flex">
            Sign in to submit a photo
          </Link>
        )}

        {message && <p className="mb-0 mt-4 text-sm font-semibold text-[var(--success-deep)]">{message}</p>}
        {error && <p className="mb-0 mt-4 text-sm font-semibold text-[var(--shpe-red)]">{error}</p>}
      </div>
    </section>
  );
}
