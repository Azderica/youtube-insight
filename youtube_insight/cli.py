import argparse
import sqlite3

from youtube_insight import config, db
from youtube_insight.transcript import fetch_transcript
from youtube_insight.summarizer import summarize
from youtube_insight.notify import send_notification
from youtube_insight.feed import fetch_feed_entries, find_new_entries
from youtube_insight.notion_sync import sync_video_to_notion
from youtube_insight.publish import render_index
from youtube_insight.subscriptions import get_credentials, sync_subscriptions


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


def cmd_watch(conn: sqlite3.Connection, notify_url: str, notify_token: str) -> list[dict]:
    processed = []
    for channel in db.list_channels(conn):
        try:
            entries = fetch_feed_entries(channel["channel_id"])
            known_ids = {row["video_id"] for row in conn.execute("SELECT video_id FROM videos").fetchall()}
        except Exception:
            continue
        new_entries = find_new_entries(entries, known_ids)
        for entry in new_entries:
            try:
                result = cmd_process(
                    conn, entry["video_id"], entry["channel_id"], entry["title"],
                    entry["url"], entry["published_at"],
                )
                processed.append(result)
                if result["status"] == "success":
                    msg = f"🎬 새 영상: {result['title']}\n{result['insight']}\n{result['url']}"
                    send_notification(msg, url=notify_url, token=notify_token)
            except Exception:
                continue
    return processed


def cmd_publish(conn: sqlite3.Connection, site_dir) -> None:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT v.video_id, v.title, v.url, v.published_at, v.summary, v.insight, c.channel_name
        FROM videos v JOIN channels c ON v.channel_id = c.channel_id
        WHERE v.status = 'success'
        ORDER BY v.published_at DESC
        """
    ).fetchall()
    videos = [dict(row) for row in rows]
    html = render_index(videos)
    site_dir.mkdir(parents=True, exist_ok=True)
    (site_dir / "index.html").write_text(html, encoding="utf-8")


def cmd_search(conn: sqlite3.Connection, query: str) -> list[dict]:
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT v.title, v.url, v.insight, v.published_at, c.channel_name
            FROM videos v
            JOIN videos_fts fts ON v.video_id = fts.video_id
            JOIN channels c ON v.channel_id = c.channel_id
            WHERE videos_fts MATCH ? AND v.status = 'success'
            ORDER BY v.published_at DESC
            """,
            (f"{query}*",),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [dict(row) for row in rows]


def cmd_subscriptions_sync(conn: sqlite3.Connection) -> int:
    credentials = get_credentials(config.google_client_secret_path(), config.google_token_path())
    return sync_subscriptions(conn, credentials)


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

    sub.add_parser("watch")

    sub.add_parser("publish")

    p_search = sub.add_parser("search")
    p_search.add_argument("query")

    sub.add_parser("subscriptions-sync")

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
    elif args.command == "watch":
        processed = cmd_watch(conn, config.notify_url(), config.internal_api_token())
        print(f"처리된 신규 영상: {len(processed)}건")
    elif args.command == "publish":
        cmd_publish(conn, config.PROJECT_ROOT / "docs")
        print("docs/index.html 갱신됨")
    elif args.command == "search":
        results = cmd_search(conn, args.query)
        if not results:
            print("검색 결과 없음")
        for r in results:
            print(f"[{r['channel_name']}] {r['title']}\n  {r['insight']}\n  {r['url']}\n")
    elif args.command == "subscriptions-sync":
        count = cmd_subscriptions_sync(conn)
        print(f"구독 채널 동기화됨: {count}건")


if __name__ == "__main__":
    main()
