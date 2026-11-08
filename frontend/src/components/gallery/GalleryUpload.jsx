import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { submitGalleryPhotos } from "../../api/api";
import { useAuth } from "../../context/AuthContext";

const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
const MAX_PHOTOS_PER_SUBMISSION = 3;
const ALLOWED_TYPES = new Set(["image/png", "image/jpeg"]);

function fileKey(file) {
  return `${file.name}:${file.size}:${file.lastModified}:${file.type}`;
}

function SelectedPhoto({ file, onRemove }) {
  const imageRef = useRef(null);

  useEffect(() => {
    const previewUrl = URL.createObjectURL(file);
    if (imageRef.current) imageRef.current.src = previewUrl;

    return () => URL.revokeObjectURL(previewUrl);
  }, [file]);

  return (
    <figure className="relative m-0 overflow-hidden rounded-xl border border-[var(--border-strong)] bg-white">
      <img
        ref={imageRef}
        alt={`Selected photo: ${file.name}`}
        className="aspect-square w-full object-cover"
      />
      <button
        type="button"
        onClick={onRemove}
        aria-label={`Remove ${file.name}`}
        className="absolute right-2 top-2 flex h-7 w-7 items-center justify-center rounded-full bg-black/70 text-lg font-semibold leading-none text-white transition hover:bg-black focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
      >
        ×
      </button>
      <figcaption className="truncate px-2 py-2 text-left text-xs text-[var(--ink-soft)]">
        {file.name}
      </figcaption>
    </figure>
  );
}

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

    if (selected.length === 0) {
      return;
    }

    const nextFiles = [...files];
    const knownFiles = new Set(files.map(fileKey));
    let invalidTypeCount = 0;
    let oversizedCount = 0;
    let duplicateCount = 0;

    selected.forEach((file) => {
      if (!ALLOWED_TYPES.has(file.type)) {
        invalidTypeCount += 1;
        return;
      }
      if (file.size > MAX_IMAGE_BYTES) {
        oversizedCount += 1;
        return;
      }

      const key = fileKey(file);
      if (knownFiles.has(key)) {
        duplicateCount += 1;
        return;
      }

      knownFiles.add(key);
      nextFiles.push(file);
    });

    const errors = [];
    if (invalidTypeCount > 0) {
      errors.push(`${invalidTypeCount} file${invalidTypeCount === 1 ? " was" : "s were"} skipped because only PNG and JPEG images are allowed.`);
    }
    if (oversizedCount > 0) {
      errors.push(`${oversizedCount} photo${oversizedCount === 1 ? " was" : "s were"} skipped because each image must be 10 MB or smaller.`);
    }
    if (duplicateCount > 0) {
      errors.push(`${duplicateCount} duplicate photo${duplicateCount === 1 ? " was" : "s were"} skipped.`);
    }
    if (nextFiles.length > MAX_PHOTOS_PER_SUBMISSION) {
      const excess = nextFiles.length - MAX_PHOTOS_PER_SUBMISSION;
      errors.push(`Remove ${excess} photo${excess === 1 ? "" : "s"} before submitting.`);
    }

    setFiles(nextFiles);
    setError(errors.join(" "));
    event.target.value = "";
  }

  function removeFile(keyToRemove) {
    const remainingFiles = files.filter((file) => fileKey(file) !== keyToRemove);
    setFiles(remainingFiles);
    setMessage("");

    if (remainingFiles.length > MAX_PHOTOS_PER_SUBMISSION) {
      const excess = remainingFiles.length - MAX_PHOTOS_PER_SUBMISSION;
      setError(`Remove ${excess} photo${excess === 1 ? "" : "s"} before submitting.`);
    } else {
      setError("");
    }
  }

  async function submit(event) {
    event.preventDefault();
    if (files.length === 0 || files.length > MAX_PHOTOS_PER_SUBMISSION || submitting) return;

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
              disabled={submitting}
              onChange={chooseFile}
              className="block w-full max-w-[500px] rounded-xl border border-[var(--border-strong)] bg-white p-3 text-sm text-[var(--ink-soft)] file:mr-3 file:rounded-full file:border-0 file:bg-[var(--surface-tint)] file:px-4 file:py-2 file:font-semibold file:text-[var(--shpe-blue)]"
            />

            {files.length > 0 && (
              <div className="w-full max-w-[500px]">
                <p className="mb-2 mt-1 text-sm font-semibold text-[var(--ink-soft)]">
                  {files.length} of {MAX_PHOTOS_PER_SUBMISSION} selected
                </p>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {files.map((file) => (
                    <SelectedPhoto
                      key={fileKey(file)}
                      file={file}
                      onRemove={() => removeFile(fileKey(file))}
                    />
                  ))}
                </div>
              </div>
            )}

            <button
              type="submit"
              className="primaryBtn"
              disabled={files.length === 0 || files.length > MAX_PHOTOS_PER_SUBMISSION || submitting}
              style={{ opacity: files.length === 0 || files.length > MAX_PHOTOS_PER_SUBMISSION || submitting ? 0.55 : 1 }}
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
