"""One-time setup: get a Google refresh token for the company calendar (info@lextria.in).

1. In Google Cloud Console create a project, enable "Google Calendar API", and create an
   OAuth client ID of type "Desktop app". Download it as client_secret.json into backend/.
2. Run:  python scripts/google_auth.py
3. A browser opens. Sign in as info@lextria.in and allow calendar access.
4. Copy the printed values into backend/.env
"""
import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
secret_file = Path(__file__).resolve().parent.parent / "client_secret.json"

flow = InstalledAppFlow.from_client_secrets_file(str(secret_file), SCOPES)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
info = json.loads(creds.to_json())
print("\nAdd these to backend/.env:\n")
print(f"GOOGLE_CLIENT_ID={info['client_id']}")
print(f"GOOGLE_CLIENT_SECRET={info['client_secret']}")
print(f"GOOGLE_REFRESH_TOKEN={info['refresh_token']}")
