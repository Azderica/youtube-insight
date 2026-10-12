"""나비계곡의 웹소설 이야기 채널 백로그 — 요약 결과를 DB에 넣고 backlog를 done으로 표시.

/tmp/webnovel_summaries.json 형식: {video_id: {"summary":..., "insight":..., "tags":...}, ...}
/tmp/webnovel_batch.json 의 각 항목(video_id, title, channel_name, transcript)과 매칭해서 삽입한다.
"""
import json
import sqlite3
import sys

sys.path.insert(0, "/Users/mh97888/business/projects/youtube-insight")
from youtube_insight import config, db
from youtube_insight.notion_sync import sync_video_to_notion

BACKLOG_PATH = "/Users/mh97888/business/projects/youtube-insight/data/webnovel_backlog.json"
BATCH_PATH = "/tmp/webnovel_batch.json"
SUMMARIES_PATH = "/tmp/webnovel_summaries.json"
CHANNEL_ID = "UCulMZ7UvkXA3pJrmvXg-BHA"


def main():
    with open(BATCH_PATH, encoding="utf-8") as f:
        batch = json.load(f)
    with open(SUMMARIES_PATH, encoding="utf-8") as f:
        summaries = json.load(f)
    with open(BACKLOG_PATH, encoding="utf-8") as f:
        backlog = json.load(f)
    by_id = {e["video_id"]: e for e in backlog}

    path = config.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    db.init_db(conn)

    inserted = 0
    for item in batch:
        vid = item["video_id"]
        if vid not in summaries:
            continue
        s = summaries[vid]
        video = {
            "video_id": vid,
            "channel_id": CHANNEL_ID,
            "title": item["title"],
            "url": f"https://youtu.be/{vid}",
            "published_at": "2026-10-12T00:00:00+00:00",
            "transcript_full": item["transcript"],
            "summary": s["summary"],
            "insight": s["insight"],
            "tags": s["tags"],
            "status": "success",
        }
        db.upsert_video(conn, video)
        sync_video_to_notion({**video, "channel_name": item["channel_name"]},
                              token=config.notion_token(), database_id=config.notion_database_id())
        by_id[vid]["status"] = "done"
        inserted += 1

    with open(BACKLOG_PATH, "w", encoding="utf-8") as f:
        json.dump(backlog, f, ensure_ascii=False, indent=1)

    remaining = sum(1 for e in backlog if e["status"] == "pending")
    print(f"inserted {inserted}, remaining pending: {remaining}")


if __name__ == "__main__":
    main()
