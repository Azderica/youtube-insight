# 유튜브 인사이트 파이프라인 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 구독/지정 유튜브 채널의 신규 영상을 감지해 자막을 추출·요약하고, SQLite(검색용)와 Notion(훑어보기용)에 이중 저장한 뒤 Discord(`/internal/notify`)로 알리고 GitHub Pages에 요약을 공개 발행한다.

**Architecture:** 순수 Python 표준 라이브러리 + 최소 의존성(`youtube-transcript-api`, Google OAuth 라이브러리)으로 만든 CLI(`python -m youtube_insight.cli ...`). 요약 생성은 별도 API 키 없이 이 환경에 이미 설치된 `claude --print` 헤드리스 호출을 재사용한다(기존 `scripts/project-nudge.sh`와 동일 패턴, `backend/.env`의 `CLAUDE_CODE_OAUTH_TOKEN` 재사용). 알림은 기존 봇의 `/internal/notify` 엔드포인트를 그대로 호출한다(신규 인프라 불필요). 자동 실행은 macOS `launchd`로 매일 1회 트리거한다.

**Tech Stack:** Python 3.11+, `sqlite3`(표준 라이브러리, FTS5), `xml.etree.ElementTree`(RSS 파싱), `urllib.request`(HTTP), `youtube-transcript-api`, `google-auth-oauthlib`/`google-api-python-client`(Task 13, YouTube 구독 동기화), `pytest`.

---

## 사전 확인 사항 (구현 시작 전 1회 확인)

- `backend/.env`에 `CLAUDE_CODE_OAUTH_TOKEN`, `INTERNAL_API_TOKEN`이 이미 존재하는지 확인한다 (`grep -E '^(CLAUDE_CODE_OAUTH_TOKEN|INTERNAL_API_TOKEN)=' backend/.env`). 없으면 봇이 정상 동작하지 않는 상태이므로 먼저 그것부터 해결해야 한다.
- 봇 프로세스가 `http://localhost:8080`에서 떠 있어야 `/internal/notify`가 동작한다. `curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/internal/notify`로 확인 (POST 없이 GET이라 405가 나오면 살아있는 것).
- Notion 동기화(Task 10)는 이 프로젝트 전용 Notion Integration Token이 필요하다 — notion.so/my-integrations 에서 새 integration을 만들고, 대상 데이터베이스에 그 integration을 공유해야 한다. 이건 브라우저 작업이라 사람이 해야 한다. 토큰이 없으면 Task 10은 건너뛰고 이후 태스크는 정상 진행 가능하다(Notion 동기화만 비활성화됨).

---

## 파일 구조

```
project-youtube-insight/
├── youtube_insight/
│   ├── __init__.py
│   ├── config.py        # 환경변수/경로 로딩
│   ├── db.py             # SQLite 스키마 + CRUD + FTS5 검색
│   ├── transcript.py     # youtube-transcript-api 래퍼
│   ├── feed.py            # RSS 피드 fetch + 파싱 + 신규 감지
│   ├── summarizer.py      # claude --print 헤드리스 호출
│   ├── notify.py          # /internal/notify POST
│   ├── notion_sync.py     # Notion 데이터베이스 동기화
│   ├── publish.py         # GitHub Pages용 정적 HTML 생성
│   ├── subscriptions.py   # YouTube 구독 목록 OAuth 동기화 (Task 13)
│   └── cli.py             # argparse 서브커맨드 진입점
├── tests/
│   ├── test_db.py
│   ├── test_transcript.py
│   ├── test_feed.py
│   ├── test_summarizer.py
│   ├── test_notify.py
│   ├── test_notion_sync.py
│   ├── test_publish.py
│   └── test_cli.py
├── scripts/
│   ├── watch.sh
│   └── com.azderica.youtube-insight-watch.plist
├── data/                 # gitignore 대상, sqlite db + oauth 토큰 저장
├── site/                 # GitHub Pages 발행 대상 (생성됨, gitignore 안 함)
├── requirements.txt
├── conftest.py
└── .env.example
```

---

### Task 1: 프로젝트 스캐폴딩 + 설정 모듈

**Files:**
- Create: `requirements.txt`
- Create: `conftest.py`
- Create: `youtube_insight/__init__.py`
- Create: `youtube_insight/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: requirements.txt 작성**

```txt
youtube-transcript-api>=0.6.2
pytest>=8.0
google-auth-oauthlib>=1.2.0
google-api-python-client>=2.100.0
```

- [ ] **Step 2: 가상환경 생성 및 의존성 설치**

Run: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
Expected: 설치 완료, 에러 없음

- [ ] **Step 3: conftest.py로 루트 경로를 sys.path에 추가**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
```

- [ ] **Step 4: youtube_insight/__init__.py 생성 (빈 파일)**

```python
```

- [ ] **Step 5: 실패하는 테스트 작성 (config 기본값)**

```python
# tests/test_config.py
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
```

- [ ] **Step 6: 테스트 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'youtube_insight.config'`

- [ ] **Step 7: config.py 구현**

```python
# youtube_insight/config.py
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def db_path() -> Path:
    override = os.environ.get("YOUTUBE_INSIGHT_DB")
    if override:
        return Path(override)
    return PROJECT_ROOT / "data" / "youtube_insight.db"


def notify_url() -> str:
    return os.environ.get("NOTIFY_URL", "http://localhost:8080/internal/notify")


def internal_api_token() -> str:
    return os.environ.get("INTERNAL_API_TOKEN", "")


def notion_token() -> str:
    return os.environ.get("NOTION_TOKEN", "")


def notion_database_id() -> str:
    return os.environ.get("NOTION_DATABASE_ID", "")
```

- [ ] **Step 8: 테스트 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: PASS (3 passed)

- [ ] **Step 9: .env.example 작성**

```txt
NOTIFY_URL=http://localhost:8080/internal/notify
INTERNAL_API_TOKEN=
NOTION_TOKEN=
NOTION_DATABASE_ID=
YOUTUBE_OAUTH_CLIENT_SECRET_FILE=data/google_client_secret.json
```

- [ ] **Step 10: .gitignore에 data/ 추가 확인 (이미 있으면 스킵)**

Modify: `.gitignore` — `.venv/` 아래에 `data/` 한 줄 추가

- [ ] **Step 11: 커밋**

```bash
git add requirements.txt conftest.py youtube_insight/__init__.py youtube_insight/config.py tests/test_config.py .env.example .gitignore
git commit -m "feat: 프로젝트 스캐폴딩과 설정 모듈 추가"
```

---

### Task 2: SQLite 저장소 모듈

**Files:**
- Create: `youtube_insight/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: 실패하는 테스트 작성 — 채널 CRUD**

```python
# tests/test_db.py
import sqlite3
import pytest
from youtube_insight import db


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    db.init_db(connection)
    yield connection
    connection.close()


def test_add_channel_후_list_channels에_나타남(conn):
    db.add_channel(conn, "UC123", "테스트채널", source="manual")
    channels = db.list_channels(conn)
    assert len(channels) == 1
    assert channels[0]["channel_id"] == "UC123"
    assert channels[0]["channel_name"] == "테스트채널"
    assert channels[0]["source"] == "manual"


def test_remove_channel_후_list에서_사라짐(conn):
    db.add_channel(conn, "UC123", "테스트채널", source="manual")
    db.remove_channel(conn, "UC123")
    assert db.list_channels(conn) == []


def test_add_channel_중복_추가시_에러없이_무시(conn):
    db.add_channel(conn, "UC123", "테스트채널", source="manual")
    db.add_channel(conn, "UC123", "테스트채널", source="manual")
    assert len(db.list_channels(conn)) == 1
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'youtube_insight.db'`

- [ ] **Step 3: db.py — 스키마 초기화 + 채널 CRUD 구현**

```python
# youtube_insight/db.py
import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS channels (
    channel_id TEXT PRIMARY KEY,
    channel_name TEXT NOT NULL,
    source TEXT NOT NULL CHECK(source IN ('subscription', 'manual')),
    added_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS videos (
    video_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    published_at TEXT NOT NULL,
    transcript_full TEXT,
    summary TEXT,
    insight TEXT,
    tags TEXT,
    status TEXT NOT NULL CHECK(status IN ('pending', 'success', 'no_transcript', 'failed')),
    processed_at TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS videos_fts USING fts5(
    video_id UNINDEXED, title, transcript_full, summary
);
"""


def init_db(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_channel(conn: sqlite3.Connection, channel_id: str, channel_name: str, source: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO channels (channel_id, channel_name, source, added_at) VALUES (?, ?, ?, ?)",
        (channel_id, channel_name, source, _now()),
    )
    conn.commit()


def remove_channel(conn: sqlite3.Connection, channel_id: str) -> None:
    conn.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
    conn.commit()


def list_channels(conn: sqlite3.Connection) -> list[dict]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM channels ORDER BY added_at").fetchall()
    return [dict(row) for row in rows]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_db.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 실패하는 테스트 작성 — 영상 저장/조회/검색**

```python
# tests/test_db.py 에 이어서 추가

def test_has_video_없으면_False(conn):
    assert db.has_video(conn, "vid1") is False


def test_upsert_video_후_has_video_True(conn):
    db.add_channel(conn, "UC123", "테스트채널", source="manual")
    db.upsert_video(conn, {
        "video_id": "vid1",
        "channel_id": "UC123",
        "title": "테스트 영상",
        "url": "https://youtu.be/vid1",
        "published_at": "2026-08-01T00:00:00+00:00",
        "transcript_full": "이것은 자막 전문입니다",
        "summary": "요약입니다",
        "insight": "인사이트입니다",
        "tags": "재테크,절약",
        "status": "success",
    })
    assert db.has_video(conn, "vid1") is True


def test_search_videos_키워드로_찾음(conn):
    db.add_channel(conn, "UC123", "테스트채널", source="manual")
    db.upsert_video(conn, {
        "video_id": "vid1",
        "channel_id": "UC123",
        "title": "순자산 4층 모델",
        "url": "https://youtu.be/vid1",
        "published_at": "2026-08-01T00:00:00+00:00",
        "transcript_full": "레버리지를 써야 하는 시점에 대한 이야기",
        "summary": "레버리지 전환 시점 요약",
        "insight": "3층에서 4층으로",
        "tags": "재테크",
        "status": "success",
    })
    results = db.search_videos(conn, "레버리지")
    assert len(results) == 1
    assert results[0]["video_id"] == "vid1"


def test_search_videos_결과없으면_빈리스트(conn):
    assert db.search_videos(conn, "존재하지않는단어") == []
```

- [ ] **Step 6: 테스트 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_db.py -v`
Expected: FAIL — `AttributeError: module 'youtube_insight.db' has no attribute 'has_video'`

- [ ] **Step 7: db.py — 영상 저장/조회/검색 구현 추가**

```python
# youtube_insight/db.py 에 이어서 추가

def has_video(conn: sqlite3.Connection, video_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM videos WHERE video_id = ?", (video_id,)).fetchone()
    return row is not None


def upsert_video(conn: sqlite3.Connection, video: dict) -> None:
    conn.execute(
        """
        INSERT INTO videos
            (video_id, channel_id, title, url, published_at, transcript_full,
             summary, insight, tags, status, processed_at)
        VALUES (:video_id, :channel_id, :title, :url, :published_at, :transcript_full,
                :summary, :insight, :tags, :status, :processed_at)
        ON CONFLICT(video_id) DO UPDATE SET
            title=excluded.title, transcript_full=excluded.transcript_full,
            summary=excluded.summary, insight=excluded.insight, tags=excluded.tags,
            status=excluded.status, processed_at=excluded.processed_at
        """,
        {**video, "processed_at": _now()},
    )
    conn.execute("DELETE FROM videos_fts WHERE video_id = ?", (video["video_id"],))
    conn.execute(
        "INSERT INTO videos_fts (video_id, title, transcript_full, summary) VALUES (?, ?, ?, ?)",
        (video["video_id"], video["title"], video.get("transcript_full") or "", video.get("summary") or ""),
    )
    conn.commit()


def search_videos(conn: sqlite3.Connection, query: str) -> list[dict]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT v.* FROM videos v
        JOIN videos_fts fts ON v.video_id = fts.video_id
        WHERE videos_fts MATCH ?
        ORDER BY v.published_at DESC
        """,
        (query,),
    ).fetchall()
    return [dict(row) for row in rows]
```

- [ ] **Step 8: 테스트 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_db.py -v`
Expected: PASS (7 passed)

- [ ] **Step 9: 커밋**

```bash
git add youtube_insight/db.py tests/test_db.py
git commit -m "feat: SQLite 채널/영상 저장소와 FTS5 검색 추가"
```

---

### Task 3: 자막 추출 모듈

**Files:**
- Create: `youtube_insight/transcript.py`
- Test: `tests/test_transcript.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_transcript.py
from unittest.mock import MagicMock, patch
from youtube_insight import transcript


class FakeSnippet:
    def __init__(self, text):
        self.text = text


def test_fetch_transcript_성공하면_텍스트_반환():
    fake_api = MagicMock()
    fake_api.fetch.return_value = [FakeSnippet("안녕하세요"), FakeSnippet("반갑습니다")]
    with patch("youtube_insight.transcript.YouTubeTranscriptApi", return_value=fake_api):
        result = transcript.fetch_transcript("vid1")
    assert result == "안녕하세요 반갑습니다"
    fake_api.fetch.assert_called_once_with("vid1", languages=["ko", "en"])


def test_fetch_transcript_자막없으면_None_반환():
    fake_api = MagicMock()
    fake_api.fetch.side_effect = Exception("no transcript")
    with patch("youtube_insight.transcript.YouTubeTranscriptApi", return_value=fake_api):
        result = transcript.fetch_transcript("vid1")
    assert result is None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_transcript.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'youtube_insight.transcript'`

- [ ] **Step 3: transcript.py 구현**

```python
# youtube_insight/transcript.py
from youtube_transcript_api import YouTubeTranscriptApi


def fetch_transcript(video_id: str) -> str | None:
    try:
        api = YouTubeTranscriptApi()
        snippets = api.fetch(video_id, languages=["ko", "en"])
    except Exception:
        return None
    return " ".join(snippet.text for snippet in snippets)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_transcript.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 실제 영상으로 통합 확인 (수동, 커밋 불필요)**

Run: `.venv/bin/python -c "from youtube_insight.transcript import fetch_transcript; t = fetch_transcript('G21BbAn1lm4'); print(len(t) if t else 'None')"`
Expected: 자막 글자 수가 출력됨 (예: `40343`) — 브레인스토밍 단계에서 이미 검증된 영상

- [ ] **Step 6: 커밋**

```bash
git add youtube_insight/transcript.py tests/test_transcript.py
git commit -m "feat: youtube-transcript-api 기반 자막 추출 모듈 추가"
```

---

### Task 4: RSS 피드 신규 영상 감지 모듈

**Files:**
- Create: `youtube_insight/feed.py`
- Test: `tests/test_feed.py`

- [ ] **Step 1: 실패하는 테스트 작성 (샘플 Atom XML 파싱)**

```python
# tests/test_feed.py
from unittest.mock import patch
from youtube_insight import feed

SAMPLE_FEED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
 <yt:channelId>UC123</yt:channelId>
 <title>테스트채널</title>
 <entry>
  <yt:videoId>vid1</yt:videoId>
  <yt:channelId>UC123</yt:channelId>
  <title>첫번째 영상</title>
  <link rel="alternate" href="https://www.youtube.com/watch?v=vid1"/>
  <published>2026-08-01T00:00:00+00:00</published>
 </entry>
 <entry>
  <yt:videoId>vid2</yt:videoId>
  <yt:channelId>UC123</yt:channelId>
  <title>두번째 영상</title>
  <link rel="alternate" href="https://www.youtube.com/watch?v=vid2"/>
  <published>2026-08-02T00:00:00+00:00</published>
 </entry>
</feed>
"""


def test_parse_feed_엔트리_2개_파싱():
    entries = feed.parse_feed(SAMPLE_FEED_XML)
    assert len(entries) == 2
    assert entries[0] == {
        "video_id": "vid1",
        "channel_id": "UC123",
        "title": "첫번째 영상",
        "url": "https://www.youtube.com/watch?v=vid1",
        "published_at": "2026-08-01T00:00:00+00:00",
    }


def test_fetch_feed_entries_urlopen_호출():
    with patch("youtube_insight.feed.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.read.return_value = SAMPLE_FEED_XML.encode()
        entries = feed.fetch_feed_entries("UC123")
    assert len(entries) == 2
    called_url = mock_urlopen.call_args[0][0]
    assert called_url == "https://www.youtube.com/feeds/videos.xml?channel_id=UC123"


def test_find_new_entries_이미_처리된_video_id는_제외():
    entries = [
        {"video_id": "vid1", "channel_id": "UC123", "title": "a", "url": "u1", "published_at": "p1"},
        {"video_id": "vid2", "channel_id": "UC123", "title": "b", "url": "u2", "published_at": "p2"},
    ]
    known_ids = {"vid1"}
    new_entries = feed.find_new_entries(entries, known_ids)
    assert len(new_entries) == 1
    assert new_entries[0]["video_id"] == "vid2"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_feed.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'youtube_insight.feed'`

- [ ] **Step 3: feed.py 구현**

```python
# youtube_insight/feed.py
import xml.etree.ElementTree as ET
from urllib.request import urlopen

FEED_URL_TEMPLATE = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}


def parse_feed(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    entries = []
    for entry in root.findall("atom:entry", NS):
        video_id = entry.find("yt:videoId", NS).text
        channel_id = entry.find("yt:channelId", NS).text
        title = entry.find("atom:title", NS).text
        link = entry.find("atom:link[@rel='alternate']", NS).get("href")
        published = entry.find("atom:published", NS).text
        entries.append({
            "video_id": video_id,
            "channel_id": channel_id,
            "title": title,
            "url": link,
            "published_at": published,
        })
    return entries


def fetch_feed_entries(channel_id: str) -> list[dict]:
    url = FEED_URL_TEMPLATE.format(channel_id=channel_id)
    with urlopen(url, timeout=15) as response:
        xml_text = response.read().decode("utf-8")
    return parse_feed(xml_text)


def find_new_entries(entries: list[dict], known_video_ids: set[str]) -> list[dict]:
    return [entry for entry in entries if entry["video_id"] not in known_video_ids]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_feed.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add youtube_insight/feed.py tests/test_feed.py
git commit -m "feat: 채널 RSS 피드 파싱과 신규 영상 감지 추가"
```

---

### Task 5: 요약/인사이트 생성 모듈 (claude --print 헤드리스 호출)

**Files:**
- Create: `youtube_insight/summarizer.py`
- Test: `tests/test_summarizer.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_summarizer.py
from unittest.mock import patch, MagicMock
from youtube_insight import summarizer


def test_summarize_claude_print_호출하고_결과_파싱():
    fake_result = MagicMock()
    fake_result.stdout = "SUMMARY: 요약 내용입니다\nINSIGHT: 인사이트 내용입니다\nTAGS: 재테크,절약"
    fake_result.returncode = 0
    with patch("youtube_insight.summarizer.subprocess.run", return_value=fake_result) as mock_run:
        result = summarizer.summarize("영상 제목", "자막 전문 텍스트")
    assert result == {
        "summary": "요약 내용입니다",
        "insight": "인사이트 내용입니다",
        "tags": "재테크,절약",
    }
    args, kwargs = mock_run.call_args
    assert args[0] == ["claude", "--print", "--permission-mode", "bypassPermissions"]
    assert "자막 전문 텍스트" in kwargs["input"]


def test_summarize_claude_실패하면_None_반환():
    fake_result = MagicMock()
    fake_result.returncode = 1
    fake_result.stdout = ""
    with patch("youtube_insight.summarizer.subprocess.run", return_value=fake_result):
        result = summarizer.summarize("영상 제목", "자막 전문 텍스트")
    assert result is None


def test_parse_summary_output_형식_어긋나면_None():
    assert summarizer.parse_summary_output("형식이 안 맞는 응답") is None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_summarizer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'youtube_insight.summarizer'`

- [ ] **Step 3: summarizer.py 구현**

```python
# youtube_insight/summarizer.py
import subprocess

PROMPT_TEMPLATE = """다음은 유튜브 영상 "{title}"의 자막 전문이다. 아래 형식을 정확히 지켜서 응답하라. 다른 말은 하지 마라.

SUMMARY: <5줄 이내 한국어 요약>
INSIGHT: <이 영상에서 가장 핵심적인 통찰 1~2문장>
TAGS: <쉼표로 구분한 태그 2~5개>

자막 전문:
{transcript}
"""


def parse_summary_output(text: str) -> dict | None:
    lines = {"summary": None, "insight": None, "tags": None}
    for line in text.splitlines():
        if line.startswith("SUMMARY:"):
            lines["summary"] = line[len("SUMMARY:"):].strip()
        elif line.startswith("INSIGHT:"):
            lines["insight"] = line[len("INSIGHT:"):].strip()
        elif line.startswith("TAGS:"):
            lines["tags"] = line[len("TAGS:"):].strip()
    if not all(lines.values()):
        return None
    return lines


def summarize(title: str, transcript_text: str) -> dict | None:
    prompt = PROMPT_TEMPLATE.format(title=title, transcript=transcript_text[:15000])
    result = subprocess.run(
        ["claude", "--print", "--permission-mode", "bypassPermissions"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        return None
    return parse_summary_output(result.stdout)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_summarizer.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add youtube_insight/summarizer.py tests/test_summarizer.py
git commit -m "feat: claude --print 헤드리스 호출 기반 요약 생성 모듈 추가"
```

---

### Task 6: 알림 모듈 (/internal/notify)

**Files:**
- Create: `youtube_insight/notify.py`
- Test: `tests/test_notify.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_notify.py
import json
from unittest.mock import patch, MagicMock
from youtube_insight import notify


def test_send_notification_urlopen에_올바른_body_전달():
    mock_response = MagicMock()
    mock_response.__enter__.return_value.status = 200
    with patch("youtube_insight.notify.urlopen", return_value=mock_response) as mock_urlopen:
        notify.send_notification("새 영상: 제목", url="http://localhost:8080/internal/notify", token="tok123")
    request = mock_urlopen.call_args[0][0]
    body = json.loads(request.data.decode())
    assert body["msg"] == "새 영상: 제목"
    assert body["level"] == "info"
    assert request.headers["X-internal-token"] == "tok123"


def test_send_notification_실패하면_False_반환():
    with patch("youtube_insight.notify.urlopen", side_effect=Exception("연결 실패")):
        result = notify.send_notification("메시지", url="http://localhost:8080/internal/notify", token="tok123")
    assert result is False
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_notify.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'youtube_insight.notify'`

- [ ] **Step 3: notify.py 구현**

```python
# youtube_insight/notify.py
import json
from urllib.request import Request, urlopen
from youtube_insight.config import PROJECT_ROOT


def send_notification(msg: str, url: str, token: str) -> bool:
    body = json.dumps({"dir": str(PROJECT_ROOT), "level": "info", "msg": msg}).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Internal-Token"] = token
    request = Request(url, data=body, headers=headers)
    try:
        with urlopen(request, timeout=15) as response:
            return response.status == 200
    except Exception:
        return False
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_notify.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add youtube_insight/notify.py tests/test_notify.py
git commit -m "feat: /internal/notify 기반 Discord 알림 모듈 추가"
```

---

### Task 7: CLI — channels add/remove/list, process

**Files:**
- Create: `youtube_insight/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_cli.py
import sqlite3
from unittest.mock import patch
from youtube_insight import cli, db


def make_conn():
    conn = sqlite3.connect(":memory:")
    db.init_db(conn)
    return conn


def test_cmd_channels_add_채널_추가():
    conn = make_conn()
    cli.cmd_channels_add(conn, channel_id="UC123", channel_name="테스트채널")
    channels = db.list_channels(conn)
    assert len(channels) == 1
    assert channels[0]["source"] == "manual"


def test_cmd_process_자막없으면_no_transcript_상태로_저장():
    conn = make_conn()
    db.add_channel(conn, "UC123", "테스트채널", source="manual")
    with patch("youtube_insight.cli.fetch_transcript", return_value=None):
        result = cli.cmd_process(
            conn,
            video_id="vid1",
            channel_id="UC123",
            title="영상 제목",
            url="https://youtu.be/vid1",
            published_at="2026-08-01T00:00:00+00:00",
        )
    assert result["status"] == "no_transcript"
    stored = db.search_videos(conn, "영상")
    assert stored == []  # 자막 없으면 FTS에 남길 요약이 없음


def test_cmd_process_성공하면_success_상태로_저장():
    conn = make_conn()
    db.add_channel(conn, "UC123", "테스트채널", source="manual")
    with patch("youtube_insight.cli.fetch_transcript", return_value="자막 전문"), \
         patch("youtube_insight.cli.summarize", return_value={"summary": "요약", "insight": "인사이트", "tags": "재테크"}):
        result = cli.cmd_process(
            conn,
            video_id="vid1",
            channel_id="UC123",
            title="영상 제목",
            url="https://youtu.be/vid1",
            published_at="2026-08-01T00:00:00+00:00",
        )
    assert result["status"] == "success"
    assert db.has_video(conn, "vid1") is True
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'youtube_insight.cli'`

- [ ] **Step 3: cli.py — 핵심 커맨드 함수 구현 (argparse 진입점은 Step 5)**

```python
# youtube_insight/cli.py
import argparse
import sqlite3

from youtube_insight import config, db
from youtube_insight.transcript import fetch_transcript
from youtube_insight.summarizer import summarize
from youtube_insight.notify import send_notification


def cmd_channels_add(conn: sqlite3.Connection, channel_id: str, channel_name: str) -> None:
    db.add_channel(conn, channel_id, channel_name, source="manual")


def cmd_channels_remove(conn: sqlite3.Connection, channel_id: str) -> None:
    db.remove_channel(conn, channel_id)


def cmd_process(conn: sqlite3.Connection, video_id: str, channel_id: str, title: str,
                 url: str, published_at: str) -> dict:
    transcript_text = fetch_transcript(video_id)
    if transcript_text is None:
        video = {
            "video_id": video_id, "channel_id": channel_id, "title": title, "url": url,
            "published_at": published_at, "transcript_full": None, "summary": None,
            "insight": None, "tags": None, "status": "no_transcript",
        }
        db.upsert_video(conn, video)
        return video

    result = summarize(title, transcript_text)
    if result is None:
        video = {
            "video_id": video_id, "channel_id": channel_id, "title": title, "url": url,
            "published_at": published_at, "transcript_full": transcript_text, "summary": None,
            "insight": None, "tags": None, "status": "failed",
        }
        db.upsert_video(conn, video)
        return video

    video = {
        "video_id": video_id, "channel_id": channel_id, "title": title, "url": url,
        "published_at": published_at, "transcript_full": transcript_text,
        "summary": result["summary"], "insight": result["insight"], "tags": result["tags"],
        "status": "success",
    }
    db.upsert_video(conn, video)
    return video


def _get_connection() -> sqlite3.Connection:
    path = config.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    db.init_db(conn)
    return conn


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="youtube_insight")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("channels-add")
    p_add.add_argument("channel_id")
    p_add.add_argument("channel_name")

    p_remove = sub.add_parser("channels-remove")
    p_remove.add_argument("channel_id")

    sub.add_parser("channels-list")

    p_process = sub.add_parser("process")
    p_process.add_argument("video_id")
    p_process.add_argument("channel_id")
    p_process.add_argument("title")
    p_process.add_argument("url")
    p_process.add_argument("published_at")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    conn = _get_connection()

    if args.command == "channels-add":
        cmd_channels_add(conn, args.channel_id, args.channel_name)
        print(f"채널 추가됨: {args.channel_name} ({args.channel_id})")
    elif args.command == "channels-remove":
        cmd_channels_remove(conn, args.channel_id)
        print(f"채널 제거됨: {args.channel_id}")
    elif args.command == "channels-list":
        for ch in db.list_channels(conn):
            print(f"{ch['channel_id']}\t{ch['channel_name']}\t{ch['source']}")
    elif args.command == "process":
        result = cmd_process(conn, args.video_id, args.channel_id, args.title, args.url, args.published_at)
        print(f"처리 완료: {result['status']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 수동 확인 — 실제 CLI로 채널 추가/조회**

Run: `.venv/bin/python -m youtube_insight.cli channels-add UCtest 테스트채널 && .venv/bin/python -m youtube_insight.cli channels-list`
Expected: `UCtest	테스트채널	manual` 출력

- [ ] **Step 6: 커밋**

```bash
git add youtube_insight/cli.py tests/test_cli.py
git commit -m "feat: 채널 관리·수동 처리 CLI 커맨드 추가"
```

---

### Task 8: CLI — watch (신규 영상 자동 감지 + 알림)

**Files:**
- Modify: `youtube_insight/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_cli.py 에 이어서 추가
from youtube_insight import cli, db


def test_cmd_watch_신규영상_있으면_process_호출하고_알림전송():
    conn = make_conn()
    db.add_channel(conn, "UC123", "테스트채널", source="manual")
    fake_entries = [{
        "video_id": "vid1", "channel_id": "UC123", "title": "새 영상",
        "url": "https://youtu.be/vid1", "published_at": "2026-08-01T00:00:00+00:00",
    }]
    with patch("youtube_insight.cli.fetch_feed_entries", return_value=fake_entries), \
         patch("youtube_insight.cli.fetch_transcript", return_value="자막"), \
         patch("youtube_insight.cli.summarize", return_value={"summary": "요약", "insight": "인사이트", "tags": "태그"}), \
         patch("youtube_insight.cli.send_notification", return_value=True) as mock_notify:
        processed = cli.cmd_watch(conn, notify_url="http://x", notify_token="tok")
    assert len(processed) == 1
    assert processed[0]["status"] == "success"
    mock_notify.assert_called_once()
    assert "새 영상" in mock_notify.call_args[0][0]


def test_cmd_watch_이미_처리된_영상은_건너뜀():
    conn = make_conn()
    db.add_channel(conn, "UC123", "테스트채널", source="manual")
    db.upsert_video(conn, {
        "video_id": "vid1", "channel_id": "UC123", "title": "기존 영상", "url": "u",
        "published_at": "p", "transcript_full": "t", "summary": "s", "insight": "i",
        "tags": "tag", "status": "success",
    })
    fake_entries = [{
        "video_id": "vid1", "channel_id": "UC123", "title": "기존 영상",
        "url": "u", "published_at": "p",
    }]
    with patch("youtube_insight.cli.fetch_feed_entries", return_value=fake_entries), \
         patch("youtube_insight.cli.send_notification") as mock_notify:
        processed = cli.cmd_watch(conn, notify_url="http://x", notify_token="tok")
    assert processed == []
    mock_notify.assert_not_called()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: FAIL — `AttributeError: module 'youtube_insight.cli' has no attribute 'cmd_watch'`

- [ ] **Step 3: cli.py에 cmd_watch 추가 (import 및 서브커맨드 등록 포함)**

```python
# youtube_insight/cli.py 상단 import에 추가
from youtube_insight.feed import fetch_feed_entries, find_new_entries
```

```python
# youtube_insight/cli.py — cmd_process 아래에 추가
def cmd_watch(conn: sqlite3.Connection, notify_url: str, notify_token: str) -> list[dict]:
    processed = []
    for channel in db.list_channels(conn):
        try:
            entries = fetch_feed_entries(channel["channel_id"])
        except Exception:
            continue
        known_ids = {v["video_id"] for v in db.search_videos(conn, "*")} if False else None
        new_entries = [e for e in entries if not db.has_video(conn, e["video_id"])]
        for entry in new_entries:
            result = cmd_process(
                conn, entry["video_id"], entry["channel_id"], entry["title"],
                entry["url"], entry["published_at"],
            )
            processed.append(result)
            if result["status"] == "success":
                msg = f"🎬 새 영상: {result['title']}\n{result['insight']}\n{result['url']}"
                send_notification(msg, url=notify_url, token=notify_token)
    return processed
```

```python
# youtube_insight/cli.py — build_parser()의 sub.add_parser 목록에 추가
    sub.add_parser("watch")
```

```python
# youtube_insight/cli.py — main()의 elif 체인에 추가
    elif args.command == "watch":
        processed = cmd_watch(conn, config.notify_url(), config.internal_api_token())
        print(f"처리된 신규 영상: {len(processed)}건")
```

- [ ] **Step 4: cmd_watch 안의 죽은 코드 정리 (find_new_entries 사용하도록 단순화)**

```python
# youtube_insight/cli.py — cmd_watch 재작성
def cmd_watch(conn: sqlite3.Connection, notify_url: str, notify_token: str) -> list[dict]:
    processed = []
    for channel in db.list_channels(conn):
        try:
            entries = fetch_feed_entries(channel["channel_id"])
        except Exception:
            continue
        known_ids = {row["video_id"] for row in conn.execute("SELECT video_id FROM videos").fetchall()}
        new_entries = find_new_entries(entries, known_ids)
        for entry in new_entries:
            result = cmd_process(
                conn, entry["video_id"], entry["channel_id"], entry["title"],
                entry["url"], entry["published_at"],
            )
            processed.append(result)
            if result["status"] == "success":
                msg = f"🎬 새 영상: {result['title']}\n{result['insight']}\n{result['url']}"
                send_notification(msg, url=notify_url, token=notify_token)
    return processed
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: PASS (5 passed)

- [ ] **Step 6: 커밋**

```bash
git add youtube_insight/cli.py tests/test_cli.py
git commit -m "feat: watch 커맨드로 신규 영상 자동 감지·처리·알림 연결"
```

---

### Task 9: 자동 실행 스크립트 + launchd 등록 (수동 설치)

**Files:**
- Create: `scripts/watch.sh`
- Create: `scripts/com.azderica.youtube-insight-watch.plist`

- [ ] **Step 1: watch.sh 작성 (project-nudge.sh와 동일한 토큰 재사용 패턴)**

```bash
#!/usr/bin/env bash
# 매일 1회: 구독/등록 채널의 신규 영상을 감지해 요약하고 Discord로 알린다.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ -f "/Users/mh97888/business/backend/.env" ]]; then
  export INTERNAL_API_TOKEN="$(grep -m1 '^INTERNAL_API_TOKEN=' /Users/mh97888/business/backend/.env | cut -d= -f2- | tr -d '"'\''\r')"
  export CLAUDE_CODE_OAUTH_TOKEN="$(grep -m1 '^CLAUDE_CODE_OAUTH_TOKEN=' /Users/mh97888/business/backend/.env | cut -d= -f2- | tr -d '"'\''\r')"
fi

"$REPO_ROOT/.venv/bin/python" -m youtube_insight.cli watch
```

- [ ] **Step 2: 실행 권한 부여**

Run: `chmod +x scripts/watch.sh`

- [ ] **Step 3: 드라이런 — 봇이 꺼져 있어도 에러 없이 끝나는지 확인**

Run: `./scripts/watch.sh`
Expected: `처리된 신규 영상: 0건` (등록된 채널이 없으므로) 또는 실제 등록 채널이 있으면 처리 건수 출력

- [ ] **Step 4: plist 작성 (project-nudge 패턴 그대로)**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!--
  유튜브 인사이트 파이프라인 — 매일 09:00

  등록된 채널의 신규 영상을 감지해 자막 추출·요약하고 Discord 채널로 알린다.

  설치:
    cp scripts/com.azderica.youtube-insight-watch.plist ~/Library/LaunchAgents/
    launchctl load ~/Library/LaunchAgents/com.azderica.youtube-insight-watch.plist

  먼저 확인:
    ./scripts/watch.sh
-->
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.azderica.youtube-insight-watch</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/mh97888/business/projects/youtube-insight/scripts/watch.sh</string>
    </array>

    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>/Users/mh97888</string>
        <key>PATH</key>
        <string>/Users/mh97888/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>/Users/mh97888/business/logs/youtube-insight-watch.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/mh97888/business/logs/youtube-insight-watch.err.log</string>

    <key>ProcessType</key>
    <string>Background</string>
</dict>
</plist>
```

- [ ] **Step 5: 커밋 (launchctl load는 사람이 직접 실행 — 시스템 등록은 플랜 실행자가 자동으로 하지 않는다)**

```bash
git add scripts/watch.sh scripts/com.azderica.youtube-insight-watch.plist
git commit -m "feat: 매일 1회 자동 감시용 watch.sh와 launchd plist 추가"
```

---

### Task 10: Notion 동기화 모듈

**전제조건:** notion.so/my-integrations에서 이 프로젝트용 integration을 만들고 대상 데이터베이스에 공유한 뒤 `NOTION_TOKEN`, `NOTION_DATABASE_ID`를 `.env`에 설정해야 한다. 토큰이 없으면 이 태스크는 건너뛰고 `sync_video_to_notion`은 호출부에서 자연히 스킵된다.

**Files:**
- Create: `youtube_insight/notion_sync.py`
- Test: `tests/test_notion_sync.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_notion_sync.py
import json
from unittest.mock import patch, MagicMock
from youtube_insight import notion_sync


def test_sync_video_to_notion_토큰없으면_스킵():
    result = notion_sync.sync_video_to_notion(
        {"title": "제목", "url": "u", "channel_name": "채널", "published_at": "2026-08-01",
         "insight": "인사이트", "tags": "태그", "status": "success"},
        token="", database_id="",
    )
    assert result is False


def test_sync_video_to_notion_토큰있으면_page_생성_요청():
    mock_response = MagicMock()
    mock_response.__enter__.return_value.status = 200
    with patch("youtube_insight.notion_sync.urlopen", return_value=mock_response) as mock_urlopen:
        result = notion_sync.sync_video_to_notion(
            {"title": "제목", "url": "https://youtu.be/vid1", "channel_name": "채널",
             "published_at": "2026-08-01", "insight": "인사이트", "tags": "태그,재테크", "status": "success"},
            token="secret_abc", database_id="db123",
        )
    assert result is True
    request = mock_urlopen.call_args[0][0]
    assert request.full_url == "https://api.notion.com/v1/pages"
    assert request.headers["Authorization"] == "Bearer secret_abc"
    body = json.loads(request.data.decode())
    assert body["parent"]["database_id"] == "db123"
    assert body["properties"]["제목"]["title"][0]["text"]["content"] == "제목"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_notion_sync.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'youtube_insight.notion_sync'`

- [ ] **Step 3: notion_sync.py 구현**

```python
# youtube_insight/notion_sync.py
import json
from urllib.request import Request, urlopen

NOTION_API_URL = "https://api.notion.com/v1/pages"
NOTION_VERSION = "2022-06-28"


def _build_page_body(video: dict, database_id: str) -> dict:
    return {
        "parent": {"database_id": database_id},
        "properties": {
            "제목": {"title": [{"text": {"content": video["title"]}}]},
            "채널명": {"rich_text": [{"text": {"content": video["channel_name"]}}]},
            "링크": {"url": video["url"]},
            "업로드일": {"date": {"start": video["published_at"]}},
            "한줄인사이트": {"rich_text": [{"text": {"content": video.get("insight") or ""}}]},
            "태그": {"multi_select": [{"name": t.strip()} for t in (video.get("tags") or "").split(",") if t.strip()]},
            "처리상태": {"select": {"name": "성공" if video["status"] == "success" else "실패"}},
        },
    }


def sync_video_to_notion(video: dict, token: str, database_id: str) -> bool:
    if not token or not database_id:
        return False
    body = json.dumps(_build_page_body(video, database_id)).encode()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }
    request = Request(NOTION_API_URL, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=15) as response:
            return response.status in (200, 201)
    except Exception:
        return False
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_notion_sync.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: cli.py의 cmd_process에서 성공 시 Notion 동기화 호출하도록 연결**

```python
# youtube_insight/cli.py 상단 import에 추가
from youtube_insight.notion_sync import sync_video_to_notion
```

```python
# youtube_insight/cli.py — cmd_process의 성공 분기 마지막 줄(db.upsert_video(conn, video)) 다음에 추가
    if video["status"] == "success":
        channel_row = conn.execute(
            "SELECT channel_name FROM channels WHERE channel_id = ?", (channel_id,)
        ).fetchone()
        channel_name = channel_row[0] if channel_row else channel_id
        sync_video_to_notion(
            {**video, "channel_name": channel_name},
            token=config.notion_token(),
            database_id=config.notion_database_id(),
        )
    return video
```

- [ ] **Step 6: 기존 테스트가 여전히 통과하는지 확인 (Notion 미설정 시 자연 스킵)**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: PASS (5 passed) — 테스트 환경에는 `NOTION_TOKEN`이 없으므로 `sync_video_to_notion`이 조용히 `False`를 반환하고 넘어감

- [ ] **Step 7: 커밋**

```bash
git add youtube_insight/notion_sync.py tests/test_notion_sync.py youtube_insight/cli.py
git commit -m "feat: 처리 성공 시 Notion 데이터베이스로 동기화"
```

---

### Task 11: GitHub Pages 발행 모듈

**Files:**
- Create: `youtube_insight/publish.py`
- Test: `tests/test_publish.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_publish.py
from youtube_insight import publish


def test_render_index_영상없으면_빈목록_안내():
    html = publish.render_index([])
    assert "아직 정리된 영상이 없습니다" in html


def test_render_index_영상목록_링크_포함하고_자막전문은_제외():
    videos = [{
        "title": "테스트 영상", "url": "https://youtu.be/vid1", "channel_name": "테스트채널",
        "published_at": "2026-08-01", "summary": "요약 내용", "insight": "인사이트 내용",
        "transcript_full": "이 자막 전문은 공개 페이지에 노출되면 안 된다",
    }]
    html = publish.render_index(videos)
    assert "테스트 영상" in html
    assert "https://youtu.be/vid1" in html
    assert "요약 내용" in html
    assert "인사이트 내용" in html
    assert "이 자막 전문은 공개 페이지에 노출되면 안 된다" not in html
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_publish.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'youtube_insight.publish'`

- [ ] **Step 3: publish.py 구현**

```python
# youtube_insight/publish.py
import html as html_escape

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>유튜브 인사이트</title>
</head>
<body>
<h1>유튜브 인사이트</h1>
{body}
</body>
</html>
"""

ITEM_TEMPLATE = """<article>
<h2><a href="{url}">{title}</a></h2>
<p>{channel_name} · {published_at}</p>
<p>{summary}</p>
<p><strong>인사이트:</strong> {insight}</p>
</article>
"""


def render_index(videos: list[dict]) -> str:
    if not videos:
        return PAGE_TEMPLATE.format(body="<p>아직 정리된 영상이 없습니다.</p>")
    items = []
    for video in videos:
        items.append(ITEM_TEMPLATE.format(
            url=html_escape.escape(video["url"]),
            title=html_escape.escape(video["title"]),
            channel_name=html_escape.escape(video["channel_name"]),
            published_at=html_escape.escape(video["published_at"]),
            summary=html_escape.escape(video.get("summary") or ""),
            insight=html_escape.escape(video.get("insight") or ""),
        ))
    return PAGE_TEMPLATE.format(body="\n".join(items))
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_publish.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: CLI에 publish 커맨드 추가**

```python
# youtube_insight/cli.py 상단 import에 추가
from youtube_insight.publish import render_index
```

```python
# youtube_insight/cli.py — cmd_watch 아래에 추가
def cmd_publish(conn: sqlite3.Connection, site_dir) -> None:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT v.title, v.url, v.published_at, v.summary, v.insight, c.channel_name
        FROM videos v JOIN channels c ON v.channel_id = c.channel_id
        WHERE v.status = 'success'
        ORDER BY v.published_at DESC
        """
    ).fetchall()
    videos = [dict(row) for row in rows]
    html = render_index(videos)
    site_dir.mkdir(parents=True, exist_ok=True)
    (site_dir / "index.html").write_text(html, encoding="utf-8")
```

```python
# youtube_insight/cli.py — build_parser()의 sub.add_parser 목록에 추가
    sub.add_parser("publish")
```

```python
# youtube_insight/cli.py — main()의 elif 체인에 추가
    elif args.command == "publish":
        cmd_publish(conn, config.PROJECT_ROOT / "site")
        print("site/index.html 갱신됨")
```

- [ ] **Step 6: 수동 확인**

Run: `.venv/bin/python -m youtube_insight.cli publish && cat site/index.html`
Expected: `<h1>유튜브 인사이트</h1>` 포함된 HTML 출력 (처리된 영상이 없으면 "아직 정리된 영상이 없습니다" 문구)

- [ ] **Step 7: 커밋**

```bash
git add youtube_insight/publish.py tests/test_publish.py youtube_insight/cli.py
git commit -m "feat: GitHub Pages용 정적 인덱스 생성과 publish 커맨드 추가"
```

---

### Task 12: GitHub Pages 활성화 (수동 확인 필요)

**Files:** 없음 (레포 설정 변경)

- [ ] **Step 1: site/ 디렉토리를 최초 커밋 (publish 1회 실행 후)**

```bash
.venv/bin/python -m youtube_insight.cli publish
git add site/
git commit -m "chore: 초기 site/index.html 생성"
git push
```

- [ ] **Step 2: GitHub Pages를 site/ 폴더 기준으로 활성화 — 실행 전 사용자에게 확인**

이 단계는 레포 설정을 바꾸는 되돌리기 쉬운 변경이지만, 외부에 공개되는 URL이 생기므로 실행 직전에 사용자에게 알리고 진행한다.

Run: `gh api repos/Azderica/project-youtube-insight/pages -X POST -f "source[branch]=main" -f "source[path]=/site"`
Expected: Pages 사이트 정보 JSON 응답, `https://azderica.github.io/project-youtube-insight/` 형태의 URL 포함

- [ ] **Step 3: 배포 확인**

Run: `curl -s -o /dev/null -w '%{http_code}' https://azderica.github.io/project-youtube-insight/`
Expected: `200` (배포 직후엔 몇 분 지연될 수 있어 404가 나오면 잠시 후 재확인)

---

### Task 13: YouTube 구독 목록 OAuth 동기화 (보류 — 2026-08-31 범위 조정, 2026-09-01 정정)

> **보류 사유**: 실제로 검증된 수요는 "수동으로 채널 등록 → 요약 → 검색/다른 프로젝트가 참고"(수동 `/addchannel` + 검색)였다. 구독 목록 자동 동기화는 아직 아무도 안 쓴 기능을 위해 계속 투자하는 가정이라, 검증된 방향(수동 채널 등록 + 검색 커맨드)에 먼저 집중하기로 했다. 필요해지면 이 태스크를 다시 꺼낸다 — 코드/설계는 아래 그대로 유효하다.
>
> **정정 (2026-09-01)**: 이 프로젝트의 목표는 "게임 개발 레퍼런스"로 한정되지 않는다 — 채널/주제 범위를 의도적으로 제한하지 않는다. 목표는 어떤 채널이든 "인사이트"를 뽑아 쌓는 것 자체다 (실제로 게임개발 채널 외에 AI 콘텐츠 제작·사이드허슬 채널도 등록되어 쌓이고 있다). 위 보류 사유는 "OAuth 자동 구독 동기화를 미룬다"는 결정에만 해당하고, 다루는 주제/채널의 범위를 게임 개발로 좁힌다는 뜻이 아니다.

**전제조건 (브라우저에서 사람이 직접):**
1. https://console.cloud.google.com 에서 새 프로젝트 생성
2. "YouTube Data API v3" 활성화
3. OAuth 동의 화면 구성 (테스트 사용자로 본인 계정 추가)
4. OAuth 클라이언트 ID(데스크톱 앱) 생성 후 JSON을 `data/google_client_secret.json`으로 저장 (`data/`는 gitignore 대상이라 커밋되지 않음)

**Files:**
- Create: `youtube_insight/subscriptions.py`
- Test: `tests/test_subscriptions.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_subscriptions.py
from unittest.mock import patch, MagicMock
from youtube_insight import subscriptions


def test_list_subscriptions_페이지네이션_모두_수집():
    fake_service = MagicMock()
    fake_service.subscriptions.return_value.list.return_value.execute.side_effect = [
        {
            "items": [{"snippet": {"resourceId": {"channelId": "UC1"}, "title": "채널1"}}],
            "nextPageToken": "page2",
        },
        {
            "items": [{"snippet": {"resourceId": {"channelId": "UC2"}, "title": "채널2"}}],
        },
    ]
    with patch("youtube_insight.subscriptions._build_service", return_value=fake_service):
        result = subscriptions.list_subscriptions(credentials=MagicMock())
    assert result == [
        {"channel_id": "UC1", "channel_name": "채널1"},
        {"channel_id": "UC2", "channel_name": "채널2"},
    ]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_subscriptions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'youtube_insight.subscriptions'`

- [ ] **Step 3: subscriptions.py 구현**

```python
# youtube_insight/subscriptions.py
from pathlib import Path

from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]


def _build_service(credentials):
    return build("youtube", "v3", credentials=credentials)


def load_or_run_oauth_flow(client_secret_file: Path, token_file: Path) -> Credentials:
    credentials = None
    if token_file.exists():
        credentials = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(GoogleRequest())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_file), SCOPES)
            credentials = flow.run_local_server(port=0)
        token_file.write_text(credentials.to_json())
    return credentials


def list_subscriptions(credentials) -> list[dict]:
    service = _build_service(credentials)
    subscriptions = []
    page_token = None
    while True:
        request = service.subscriptions().list(
            part="snippet", mine=True, maxResults=50, pageToken=page_token
        )
        response = request.execute()
        for item in response.get("items", []):
            subscriptions.append({
                "channel_id": item["snippet"]["resourceId"]["channelId"],
                "channel_name": item["snippet"]["title"],
            })
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return subscriptions
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_subscriptions.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: CLI에 channels-sync-subscriptions 커맨드 추가**

```python
# youtube_insight/cli.py 상단 import에 추가
from youtube_insight.subscriptions import list_subscriptions, load_or_run_oauth_flow
```

```python
# youtube_insight/cli.py — cmd_channels_remove 아래에 추가
def cmd_channels_sync_subscriptions(conn: sqlite3.Connection) -> int:
    client_secret = config.PROJECT_ROOT / "data" / "google_client_secret.json"
    token_file = config.PROJECT_ROOT / "data" / "google_token.json"
    credentials = load_or_run_oauth_flow(client_secret, token_file)
    subs = list_subscriptions(credentials)
    for sub in subs:
        db.add_channel(conn, sub["channel_id"], sub["channel_name"], source="subscription")
    return len(subs)
```

```python
# youtube_insight/cli.py — build_parser()의 sub.add_parser 목록에 추가
    sub.add_parser("channels-sync-subscriptions")
```

```python
# youtube_insight/cli.py — main()의 elif 체인에 추가
    elif args.command == "channels-sync-subscriptions":
        count = cmd_channels_sync_subscriptions(conn)
        print(f"구독 채널 {count}개 동기화됨")
```

- [ ] **Step 6: 수동 확인 (브라우저 OAuth 동의 필요, 전제조건의 client_secret.json 준비된 뒤에만 실행)**

Run: `.venv/bin/python -m youtube_insight.cli channels-sync-subscriptions`
Expected: 브라우저가 열리고 로그인/동의 후 "구독 채널 N개 동기화됨" 출력

- [ ] **Step 7: 커밋**

```bash
git add youtube_insight/subscriptions.py tests/test_subscriptions.py youtube_insight/cli.py
git commit -m "feat: YouTube 구독 목록 OAuth 동기화 커맨드 추가"
```

---

## 자가 점검 결과

- **스펙 커버리지**: 스펙의 7개 파이프라인 단계 모두 태스크로 매핑됨 — 채널소스(Task 7, 13), 신규감지(Task 4, 8), 자막추출(Task 3), 요약생성(Task 5), 이중저장(Task 2, 10), 자동알림(Task 6, 8, 9), 수동요청(Task 7 — 대화 인터페이스에서 CLI 직접 호출), 퍼블리시(Task 11, 12).
- **플레이스홀더 스캔**: "TODO/TBD/나중에 구현" 형태 문구 없음. 모든 코드 스텝에 완전한 구현 포함.
- **타입/시그니처 일관성**: `video` dict 키(`video_id, channel_id, title, url, published_at, transcript_full, summary, insight, tags, status`)가 Task 2의 스키마부터 Task 11의 publish까지 동일하게 사용됨을 확인.
- **알려진 축소 범위**: Whisper STT 폴백 없음(스펙에서 이미 결정), 자막 없는 영상은 재시도 없이 스킵. Discord "명령"(`/addchannel` 등)은 실제 슬래시 커맨드가 아니라 이 세션(대화형 인터페이스)에서 CLI를 직접 호출하는 방식으로 구현 — 별도 봇 슬래시커맨드 핸들러가 필요하면 `backend`(공유 인프라) 수정이 필요하므로 이번 계획 범위 밖으로 명시적으로 뺐다.
