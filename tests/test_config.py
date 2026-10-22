import os
from youtube_insight import config


def test_db_path_기본값_data디렉토리_아래(tmp_path, monkeypatch):
    monkeypatch.delenv("YOUTUBE_INSIGHT_DB", raising=False)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    assert config.db_path() == tmp_path / "data" / "youtube_insight.db"


def test_db_path_환경변수로_오버라이드(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUTUBE_INSIGHT_DB", str(tmp_path / "custom.db"))
    assert config.db_path() == tmp_path / "custom.db"


def test_notify_url_기본값():
    assert config.notify_url() == "http://localhost:8080/internal/notify"


def test_google_client_secret_path_기본값_data디렉토리_아래(tmp_path, monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET_PATH", raising=False)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    assert config.google_client_secret_path() == tmp_path / "data" / "client_secret.json"


def test_google_token_path_환경변수로_오버라이드(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_TOKEN_PATH", str(tmp_path / "custom_token.json"))
    assert config.google_token_path() == tmp_path / "custom_token.json"
