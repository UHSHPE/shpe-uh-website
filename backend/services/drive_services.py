import logging
import os

from dotenv import load_dotenv

load_dotenv()

# Google Drive sync for resumes. Requires all four env vars:
#
#   GDRIVE_OAUTH_CLIENT_ID / GDRIVE_OAUTH_CLIENT_SECRET / GDRIVE_OAUTH_REFRESH_TOKEN
#   GDRIVE_RESUME_FOLDER_ID
#
# All four are printed by backend/get_drive_refresh_token.py (one-time setup).
# The backend uploads as the folder owner's Google account, scoped to
# drive.file: it can only see files/folders IT created — never the rest of
# the account's Drive. That's also why GDRIVE_RESUME_FOLDER_ID must be the
# app-created folder from the helper script (a hand-made folder's id 404s).
#
# Without config, upload is a no-op returning None — same dev-mode pattern as
# email_services.py — so local dev and tests never hit the network. Delete is
# the exception: it reports FAILURE rather than success, because its caller
# discards the file id on success and that id is the only handle on the Drive
# copy. A no-op that returns the success sentinel silently orphans a real file.
#
# All four vars are required under ENVIRONMENT=production (is_configured() is
# checked by main.assert_production_config), so the drifted-config case below
# cannot arise on the deployed instance. Sync is otherwise best-effort:
# failures are logged, never raised, and the local copy in uploads/resumes/
# remains the source of truth.

_OAUTH_SCOPES = ["https://www.googleapis.com/auth/drive.file"]
_TOKEN_URI = "https://oauth2.googleapis.com/token"

_ENV_VARS = (
    "GDRIVE_RESUME_FOLDER_ID",
    "GDRIVE_OAUTH_CLIENT_ID",
    "GDRIVE_OAUTH_CLIENT_SECRET",
    "GDRIVE_OAUTH_REFRESH_TOKEN",
)


def is_configured() -> bool:
    """True when all four Drive vars are set (read at call time, like SQUARE_*).

    Presence only, not validity — a revoked refresh token still reads as
    configured, and that is deliberate: it fails safely at call time (the API
    raises, the delete returns False, the file id is kept). Absence is the case
    that used to fail open, which is why main.assert_production_config() checks
    this one and a startup check can't do better than presence anyway."""
    return all(os.getenv(var) for var in _ENV_VARS)


def _drive_config():
    """Return (credentials, folder_id), or None when Drive sync is unconfigured."""
    if not is_configured():
        return None

    folder_id = os.getenv("GDRIVE_RESUME_FOLDER_ID")
    client_id = os.getenv("GDRIVE_OAUTH_CLIENT_ID")
    client_secret = os.getenv("GDRIVE_OAUTH_CLIENT_SECRET")
    refresh_token = os.getenv("GDRIVE_OAUTH_REFRESH_TOKEN")

    # Imported lazily so dev mode works even without the google packages.
    from google.oauth2.credentials import Credentials

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri=_TOKEN_URI,
        scopes=_OAUTH_SCOPES,
    )
    return creds, folder_id


def _drive_service(creds):
    from googleapiclient.discovery import build

    return build("drive", "v3", credentials=creds, cache_discovery=False)


def upload_resume_to_drive(existing_file_id: str | None, name: str, content: bytes) -> str | None:
    """Upload a resume PDF to the configured Drive folder and return its file id.

    If existing_file_id is given, the Drive file is updated in place (old content
    replaced, same id); if that file was deleted in Drive, a new one is created.
    Returns None when Drive sync is unconfigured or the upload fails."""
    config = _drive_config()
    if config is None:
        print(f"[drive dev mode] would upload '{name}' ({len(content)} bytes)")
        return None

    creds, folder_id = config
    try:
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaInMemoryUpload

        service = _drive_service(creds)
        media = MediaInMemoryUpload(content, mimetype="application/pdf")

        if existing_file_id:
            try:
                updated = service.files().update(
                    fileId=existing_file_id,
                    body={"name": name},
                    media_body=media,
                    fields="id",
                ).execute()
                return updated["id"]
            except HttpError as exc:
                if exc.resp.status != 404:
                    raise
                # File was removed in Drive directly — fall through and recreate.

        created = service.files().create(
            body={"name": name, "parents": [folder_id]},
            media_body=media,
            fields="id",
        ).execute()
        return created["id"]
    except Exception:
        logging.exception("Drive resume upload failed for '%s'", name)
        return None


def delete_resume_from_drive(file_id: str | None) -> bool:
    """Delete a resume from the Drive folder.

    True means the Drive copy is gone: there was nothing to delete, the delete
    succeeded, or it was already 404. False means it may still be there — Drive
    unreachable, or no config at all — and the caller MUST keep
    resume_drive_file_id, which under the drive.file scope is the only handle
    anything has on that file. The local delete proceeds either way."""
    if not file_id:
        return True

    config = _drive_config()
    if config is None:
        # Deliberately NOT True. The caller nulls the file id when this returns
        # success, which would strand a real Drive copy with nothing left
        # pointing at it — and a later retry would then short-circuit on the
        # `not file_id` branch above and report success forever. Unlike the
        # upload no-op, an unconfigured delete is a failure, not a skip.
        logging.warning(
            "Drive delete skipped for file id %s — GDRIVE_* not configured; "
            "the Drive copy may still exist",
            file_id,
        )
        return False

    creds, _ = config
    try:
        from googleapiclient.errors import HttpError

        service = _drive_service(creds)
        try:
            service.files().delete(fileId=file_id).execute()
        except HttpError as exc:
            if exc.resp.status != 404:
                raise
        return True
    except Exception:
        logging.exception("Drive resume delete failed for file id %s", file_id)
        return False
