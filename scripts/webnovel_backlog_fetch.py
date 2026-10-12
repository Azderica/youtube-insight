"""나비계곡의 웹소설 이야기 채널 백로그 일괄 처리용 1회성 스크립트.

사용법:
  .venv/bin/python scripts/webnovel_backlog_fetch.py <batch_size>

data/webnovel_backlog.json 에서 status=="pending"인 항목을 batch_size개 꺼내
oEmbed 메타데이터 + 자막을 가져와 /tmp/webnovel_batch.json 에 쓴다.
자막이 없는 영상은 바로 backlog에서 status="no_transcript"로 표시한다.
"""
import json
import sys
import urllib.request

sys.path.insert(0, "/Users/mh97888/business/projects/youtube-insight")
from youtube_insight.transcript import fetch_transcript

BACKLOG_PATH = "/Users/mh97888/business/projects/youtube-insight/data/webnovel_backlog.json"
OUTPUT_PATH = "/tmp/webnovel_batch.json"


def fetch_oembed(video_id: str) -> dict | None:
    url = f"https://www.youtube.com/oembed?url=https://youtu.be/{video_id}&format=json"
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            return json.loads(response.read().decode())
    except Exception:
        return None


def main():
    batch_size = int(sys.argv[1]) if len(sys.argv) > 1 else 15

    with open(BACKLOG_PATH, encoding="utf-8") as f:
        backlog = json.load(f)

    pending = [entry for entry in backlog if entry["status"] == "pending"]
    batch = pending[:batch_size]

    results = []
    for entry in batch:
        video_id = entry["video_id"]
        meta = fetch_oembed(video_id)
        if meta is None:
            entry["status"] = "no_transcript"
            continue
        transcript = fetch_transcript(video_id)
        if transcript is None:
            entry["status"] = "no_transcript"
            continue
        results.append({
            "video_id": video_id,
            "title": meta["title"],
            "channel_name": meta["author_name"],
            "transcript": transcript,
        })

    with open(BACKLOG_PATH, "w", encoding="utf-8") as f:
        json.dump(backlog, f, ensure_ascii=False, indent=1)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)

    remaining = sum(1 for e in backlog if e["status"] == "pending")
    print(f"fetched {len(results)} with transcript, batch had {len(batch)}, remaining pending: {remaining}")


if __name__ == "__main__":
    main()
