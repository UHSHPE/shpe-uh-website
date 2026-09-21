import { useRef, useState } from "react";
import { Link } from "react-router-dom";

import { submitGalleryPhoto } from "../../api/api";
import { useAuth } from "../../context/AuthContext";

const MAX_IMAGE_BYTES = 2 * 1024 * 1024;
const ALLOWED_TYPES = new Set(["image/png", "image/jpeg"]);

export default function GalleryUpload() {
  const { user } = useAuth();
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  function chooseFile(event) {
    const selected = event.target.files?.[0] ?? null;
    setMessage("");
    setError("");

    if (!selected) {
      setFile(null);
      return;
    }
    if (!ALLOWED_TYPES.has(selected.type)) {
      setFile(null);
      setError("Choose a PNG or JPEG image.");
      event.target.value = "";
      return;
    }
    if (selected.size > MAX_IMAGE_BYTES) {
      setFile(null);
      setError("The image must be 2 MB or smaller.");
      event.target.value = "";
      return;
    }
    setFile(selected);
  }

  async function submit(event) {
    event.preventDefault();
    if (!file || submitting) return;

    setSubmitting(true);
    setError("");
    setMessage("");
    try {
      await submitGalleryPhoto(file);
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
      setMessage("Photo submitted for review. You’ll earn a point if it is approved.");
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
          Submit a PNG or JPEG from a SHPE event. Photos stay private until a reviewer approves them.
        </p>

        {user ? (
          <form onSubmit={submit} className="flex flex-col items-center gap-3">
            <input
              ref={inputRef}
              type="file"
              accept="image/png,image/jpeg"
              onChange={chooseFile}
              className="block w-full max-w-[500px] rounded-xl border border-[var(--border-strong)] bg-white p-3 text-sm text-[var(--ink-soft)] file:mr-3 file:rounded-full file:border-0 file:bg-[var(--surface-tint)] file:px-4 file:py-2 file:font-semibold file:text-[var(--shpe-blue)]"
            />
            <button
              type="submit"
              className="primaryBtn"
              disabled={!file || submitting}
              style={{ opacity: !file || submitting ? 0.55 : 1 }}
            >
              {submitting ? "Submitting…" : "Submit photo"}
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
