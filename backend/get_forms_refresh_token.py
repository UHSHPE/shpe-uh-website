"""One-time helper: mint the OAuth refresh token for the Forms points import.

The backend reads the points index Sheet and each committee's Google Form
as the shared chairs account, via OAuth, with read-only scopes only.

Setup (once):
  1. In Google Cloud Console: enable the Google Sheets API and the Google
     Forms API in the same project as the OAuth client.
  2. APIs & Services -> OAuth consent screen -> set Publishing status to
     "In production" (tokens minted while in "Testing" expire after 7 days).
     These scopes are sensitive, so the browser will show an "unverified
     app" warning — click Advanced -> continue.
  3. APIs & Services -> Credentials -> OAuth client ID (Desktop app).
     Copy the client id and secret.
  4. Run (from backend/):
       .venv/bin/python get_forms_refresh_token.py <client_id> <client_secret>
  5. A browser opens — sign in with the SHARED CHAIRS account (the one that
     owns the forms), not your personal account, and approve.
  6. Paste the three printed lines into backend/.env and restart the backend.
"""
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/forms.body.readonly",
    "https://www.googleapis.com/auth/forms.responses.readonly",
]


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    client_id, client_secret = sys.argv[1], sys.argv[2]

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

    print("\nAdd these lines to backend/.env (then restart the backend):\n")
    print(f"POINTS_OAUTH_CLIENT_ID={client_id}")
    print(f"POINTS_OAUTH_CLIENT_SECRET={client_secret}")
    print(f"POINTS_OAUTH_REFRESH_TOKEN={creds.refresh_token}")


if __name__ == "__main__":
    main()
