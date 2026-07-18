"""One-time helper: set up Google Drive resume sync (token + folder).

The backend uploads as YOUR Google account via OAuth, restricted to the
drive.file scope — it can only see files/folders it created itself, never
the rest of your Drive. Because of that, this script also creates the
resume folder for you (the backend couldn't access a hand-made one) and
prints its id. The folder lives in your My Drive, owned by you — you can
move or rename it afterwards without breaking sync.

Setup (once):
  1. In Google Cloud Console (same project where the Drive API is enabled):
     APIs & Services -> OAuth consent screen -> set Publishing status to
     "In production" (tokens minted while in "Testing" expire after 7 days).
  2. APIs & Services -> Credentials -> Create Credentials -> OAuth client ID
     -> Application type: Desktop app. Copy the client id and secret.
  3. Run (from backend/):
       .venv/bin/python get_drive_refresh_token.py <client_id> <client_secret> [folder name]
     (folder name defaults to "SHPE Resume Book")
  4. A browser opens — sign in with your Google account and approve.
  5. Paste the four printed lines into backend/.env and restart the backend.
"""
import sys

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# drive.file = per-file access: only files/folders created by this app.
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

DEFAULT_FOLDER_NAME = "SHPE Resume Book"


def get_or_create_folder(service, name: str) -> tuple[str, bool]:
    """Reuse the app-created folder from a previous run, or create it.
    Returns (folder_id, created). Under drive.file this search can only
    ever see folders this app made — nothing else in the account."""
    safe_name = name.replace("'", "\\'")
    query = (
        f"name = '{safe_name}' "
        "and mimeType = 'application/vnd.google-apps.folder' "
        "and trashed = false"
    )
    found = service.files().list(q=query, fields="files(id)").execute().get("files", [])
    if found:
        return found[0]["id"], False

    folder = service.files().create(
        body={"name": name, "mimeType": "application/vnd.google-apps.folder"},
        fields="id",
    ).execute()
    return folder["id"], True


def main():
    if len(sys.argv) not in (3, 4):
        print(__doc__)
        sys.exit(1)

    client_id, client_secret = sys.argv[1], sys.argv[2]
    folder_name = sys.argv[3] if len(sys.argv) == 4 else DEFAULT_FOLDER_NAME

    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
    )
    # prompt="consent" forces Google to issue a refresh token even if this
    # account already authorized the app before.
    creds = flow.run_local_server(port=0, prompt="consent")

    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    folder_id, created = get_or_create_folder(service, folder_name)
    verb = "Created" if created else "Reusing existing"
    print(f"\n{verb} Drive folder '{folder_name}' (you can move/rename it in Drive).")

    print("\nAdd these lines to backend/.env (then restart the backend):\n")
    print(f"GDRIVE_OAUTH_CLIENT_ID={client_id}")
    print(f"GDRIVE_OAUTH_CLIENT_SECRET={client_secret}")
    print(f"GDRIVE_OAUTH_REFRESH_TOKEN={creds.refresh_token}")
    print(f"GDRIVE_RESUME_FOLDER_ID={folder_id}")


if __name__ == "__main__":
    main()
