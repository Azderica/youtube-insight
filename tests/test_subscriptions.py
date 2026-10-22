import sqlite3
from unittest.mock import MagicMock, patch

from youtube_insight import db, subscriptions


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    db.init_db(conn)
    return conn


def test_get_credentials_토큰파일_있으면_유효하면_그대로_사용(tmp_path):
    token_path = tmp_path / "token.json"
    token_path.write_text("{}", encoding="utf-8")
    mock_credentials = MagicMock(expired=False, valid=True)
    with patch("youtube_insight.subscriptions.Credentials.from_authorized_user_file", return_value=mock_credentials):
        result = subscriptions.get_credentials(tmp_path / "client_secret.json", token_path)
    assert result is mock_credentials


def test_get_credentials_만료되고_리프레시토큰있으면_갱신(tmp_path):
    token_path = tmp_path / "token.json"
    token_path.write_text("{}", encoding="utf-8")
    mock_credentials = MagicMock(expired=True, refresh_token="r", valid=True)
    with patch("youtube_insight.subscriptions.Credentials.from_authorized_user_file", return_value=mock_credentials):
        with patch("youtube_insight.subscriptions.Request"):
            result = subscriptions.get_credentials(tmp_path / "client_secret.json", token_path)
    mock_credentials.refresh.assert_called_once()
    assert result is mock_credentials


def test_get_credentials_토큰없으면_oauth플로우_실행후_저장(tmp_path):
    token_path = tmp_path / "token.json"
    client_secret_path = tmp_path / "client_secret.json"
    mock_credentials = MagicMock()
    mock_credentials.to_json.return_value = '{"token": "new"}'
    mock_flow = MagicMock()
    mock_flow.run_local_server.return_value = mock_credentials
    with patch("youtube_insight.subscriptions.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow) as mock_from_secrets:
        result = subscriptions.get_credentials(client_secret_path, token_path)
    mock_from_secrets.assert_called_once_with(str(client_secret_path), subscriptions.SCOPES)
    assert result is mock_credentials
    assert token_path.read_text(encoding="utf-8") == '{"token": "new"}'


def test_fetch_subscriptions_페이지네이션_모두_수집():
    mock_youtube = MagicMock()
    mock_youtube.subscriptions.return_value.list.return_value.execute.side_effect = [
        {
            "items": [
                {"snippet": {"resourceId": {"channelId": "UC1"}, "title": "채널1"}},
            ],
            "nextPageToken": "page2",
        },
        {
            "items": [
                {"snippet": {"resourceId": {"channelId": "UC2"}, "title": "채널2"}},
            ],
        },
    ]
    with patch("youtube_insight.subscriptions.build", return_value=mock_youtube):
        result = subscriptions.fetch_subscriptions(credentials=MagicMock())
    assert result == [
        {"channel_id": "UC1", "channel_name": "채널1"},
        {"channel_id": "UC2", "channel_name": "채널2"},
    ]


def test_sync_subscriptions_구독채널을_channels테이블에_저장():
    conn = _conn()
    with patch("youtube_insight.subscriptions.fetch_subscriptions", return_value=[
        {"channel_id": "UC1", "channel_name": "채널1"},
        {"channel_id": "UC2", "channel_name": "채널2"},
    ]):
        count = subscriptions.sync_subscriptions(conn, credentials=MagicMock())
    assert count == 2
    channels = db.list_channels(conn)
    assert len(channels) == 2
    assert all(ch["source"] == "subscription" for ch in channels)
