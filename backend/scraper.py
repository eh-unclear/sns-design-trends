import os
import re
import sqlite3
import feedparser
import deepl
from database import get_connection

# 日本語判定（ひらがな・カタカナ・漢字が含まれていれば日本語とみなす）
_JP_RE = re.compile(r'[\u3040-\u30ff\u4e00-\u9fff]')


def is_japanese(text: str) -> bool:
    return bool(_JP_RE.search(text))


def get_translator():
    api_key = os.environ.get("DEEPL_API_KEY")
    if not api_key:
        return None
    return deepl.Translator(api_key)


RSS_FEEDS = [
    # 海外
    {"source": "Dribbble - Advertising", "url": "https://dribbble.com/tags/advertising.rss", "lang": "en"},
    {"source": "Dribbble - Social Media", "url": "https://dribbble.com/tags/social_media.rss", "lang": "en"},
    {"source": "Ads of the World", "url": "https://www.adsoftheworld.com/feed", "lang": "en"},
    {"source": "Creative Bloq", "url": "https://www.creativebloq.com/feeds/all", "lang": "en"},
    {"source": "Smashing Magazine", "url": "https://www.smashingmagazine.com/feed/", "lang": "en"},
    # 国内
    {"source": "AdverTimes", "url": "https://www.advertimes.com/feed/", "lang": "ja"},
    {"source": "DIGIDAY Japan", "url": "https://digiday.jp/feed/", "lang": "ja"},
    {"source": "MarkeZine", "url": "https://markezine.jp/rss/index.rss", "lang": "ja"},
    {"source": "Web担当者Forum", "url": "https://webtan.impress.co.jp/rss.xml", "lang": "ja"},
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
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary)
        if m:
            return m.group(1)
    return None


def fetch_all():
    conn = get_connection()
    translator = get_translator()
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
                lang = feed_info["lang"]

                # 日本語記事はそのまま、海外記事はDeepLで翻訳
                if lang == "ja" or is_japanese(title):
                    title_ja = title
                elif translator:
                    try:
                        result = translator.translate_text(title, target_lang="JA")
                        title_ja = result.text
                    except Exception as e:
                        print(f"[translate] Error: {e}")
                        title_ja = None
                else:
                    title_ja = None

                try:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO posts (title, title_ja, link, thumbnail, source, lang, published_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (title, title_ja, link, thumbnail, feed_info["source"], lang, published),
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
