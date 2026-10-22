from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from youtube_insight import db

SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]


def get_credentials(client_secret_path: Path, token_path: Path) -> Credentials:
    credentials = None
    if token_path.exists():
        credentials = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())

    if not credentials or not credentials.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
        credentials = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(credentials.to_json(), encoding="utf-8")

    return credentials


def fetch_subscriptions(credentials: Credentials) -> list[dict]:
    youtube = build("youtube", "v3", credentials=credentials)
    channels = []
    page_token = None
    while True:
        response = youtube.subscriptions().list(
            part="snippet", mine=True, maxResults=50, pageToken=page_token,
        ).execute()
        for item in response.get("items", []):
            snippet = item["snippet"]
            channels.append({
                "channel_id": snippet["resourceId"]["channelId"],
                "channel_name": snippet["title"],
            })
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return channels


def sync_subscriptions(conn, credentials: Credentials) -> int:
    channels = fetch_subscriptions(credentials)
    for channel in channels:
        db.add_channel(conn, channel["channel_id"], channel["channel_name"], source="subscription")
    return len(channels)
