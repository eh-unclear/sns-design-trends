import feedparser
import sqlite3
from database import get_connection

RSS_FEEDS = [
    {
        "source": "Dribbble - Advertising",
        "url": "https://dribbble.com/tags/advertising.rss",
    },
    {
        "source": "Dribbble - Social Media",
        "url": "https://dribbble.com/tags/social_media.rss",
    },
    {
        "source": "Ads of the World",
        "url": "https://www.adsoftheworld.com/feed",
    },
    {
        "source": "Creative Bloq",
        "url": "https://www.creativebloq.com/feeds/all",
    },
    {
        "source": "Smashing Magazine - Design",
        "url": "https://www.smashingmagazine.com/feed/",
    },
]


def extract_thumbnail(entry) -> str | None:
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        return entry.media_thumbnail[0].get("url")
    if hasattr(entry, "media_content") and entry.media_content:
        for m in entry.media_content:
            if m.get("medium") == "image" or m.get("type", "").startswith("image"):
                return m.get("url")
    if hasattr(entry, "enclosures") and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image"):
                return enc.get("url") or enc.get("href")
    summary = getattr(entry, "summary", "") or ""
    if "<img" in summary:
        import re
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary)
        if m:
            return m.group(1)
    return None


def fetch_all():
    conn = get_connection()
    saved = 0
    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if not title or not link:
                    continue
                thumbnail = extract_thumbnail(entry)
                published = entry.get("published", entry.get("updated", ""))
                try:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO posts (title, link, thumbnail, source, published_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (title, link, thumbnail, feed_info["source"], published),
                    )
                    saved += conn.execute("SELECT changes()").fetchone()[0]
                except sqlite3.IntegrityError:
                    pass
        except Exception as e:
            print(f"[scraper] Error fetching {feed_info['source']}: {e}")
    conn.commit()
    conn.close()
    print(f"[scraper] Saved {saved} new posts.")
    return saved


if __name__ == "__main__":
    from database import init_db
    init_db()
    fetch_all()
