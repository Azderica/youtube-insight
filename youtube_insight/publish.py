import html as html_escape

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>유튜브 인사이트</title>
<link rel="stylesheet" as="style" crossorigin
  href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@latest/dist/web/variable/pretendardvariable-dynamic-subset.css">
{preload}<style>
  :root {{
    --bg: #f7f7f8;
    --card-bg: #ffffff;
    --text: #1a1a1a;
    --muted: #6b7280;
    --accent: #ef4444;
    --accent-bg: #fef2f2;
    --border: #e5e7eb;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #16171a;
      --card-bg: #1f2023;
      --text: #f2f2f3;
      --muted: #9ca3af;
      --accent: #f87171;
      --accent-bg: #2a1c1c;
      --border: #2d2e32;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 2.5rem 1.25rem 4rem;
    background: var(--bg);
    color: var(--text);
    font-family: "Pretendard Variable", Pretendard, -apple-system, BlinkMacSystemFont, "Segoe UI",
      Roboto, "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif;
    line-height: 1.6;
  }}
  .wrap {{ max-width: 680px; margin: 0 auto; }}
  h1 {{
    font-size: 1.5rem;
    font-weight: 700;
    margin: 0 0 0.25rem;
  }}
  .subtitle {{
    color: var(--muted);
    font-size: 0.9rem;
    margin: 0 0 2rem;
  }}
  .empty {{
    color: var(--muted);
    padding: 3rem 0;
    text-align: center;
  }}
  article {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
  }}
  .thumb {{
    display: block;
    width: 100%;
    aspect-ratio: 16 / 9;
    object-fit: cover;
    border-radius: 8px;
    margin: 0 0 0.85rem;
    background: var(--border);
  }}
  article h2 {{
    font-size: 1.05rem;
    margin: 0 0 0.35rem;
    line-height: 1.4;
  }}
  article h2 a {{
    color: var(--text);
    text-decoration: none;
  }}
  article h2 a:hover {{
    color: var(--accent);
    text-decoration: underline;
  }}
  .meta {{
    color: var(--muted);
    font-size: 0.82rem;
    margin: 0 0 0.75rem;
  }}
  .summary {{
    margin: 0 0 0.85rem;
    font-size: 0.94rem;
  }}
  .insight {{
    background: var(--accent-bg);
    border-left: 3px solid var(--accent);
    border-radius: 6px;
    padding: 0.65rem 0.85rem;
    margin: 0;
    font-size: 0.92rem;
  }}
  .insight strong {{
    color: var(--accent);
  }}
</style>
</head>
<body>
<div class="wrap">
<h1>유튜브 인사이트</h1>
<p class="subtitle">보지 않고도 먼저 아는 요약 저장소</p>
{body}
</div>
</body>
</html>
"""

ITEM_TEMPLATE = """<article>
<img class="thumb" src="{thumbnail_url}" alt="" loading="{loading}" fetchpriority="{fetchpriority}">
<h2><a href="{url}">{title}</a></h2>
<p class="meta">{channel_name} · {published_at}</p>
<p class="summary">{summary}</p>
<p class="insight"><strong>인사이트</strong> {insight}</p>
</article>
"""

PRELOAD_TEMPLATE = '<link rel="preload" as="image" fetchpriority="high" href="{thumbnail_url}">\n'


def _thumbnail_url(video_id: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def render_index(videos: list[dict]) -> str:
    if not videos:
        return PAGE_TEMPLATE.format(preload="", body='<p class="empty">아직 정리된 영상이 없습니다.</p>')
    items = []
    for index, video in enumerate(videos):
        is_first = index == 0
        items.append(ITEM_TEMPLATE.format(
            thumbnail_url=html_escape.escape(_thumbnail_url(video["video_id"])),
            url=html_escape.escape(video["url"]),
            title=html_escape.escape(video["title"]),
            channel_name=html_escape.escape(video["channel_name"]),
            published_at=html_escape.escape(video["published_at"]),
            summary=html_escape.escape(video.get("summary") or ""),
            insight=html_escape.escape(video.get("insight") or ""),
            loading="eager" if is_first else "lazy",
            fetchpriority="high" if is_first else "auto",
        ))
    preload = PRELOAD_TEMPLATE.format(thumbnail_url=html_escape.escape(_thumbnail_url(videos[0]["video_id"])))
    return PAGE_TEMPLATE.format(preload=preload, body="\n".join(items))
