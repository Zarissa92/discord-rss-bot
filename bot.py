import asyncio
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone

import discord
import feedparser
import yt_dlp
from discord.ext import tasks
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
DB_PATH = os.getenv("DB_PATH", "articles.db")

# Flux RSS -> ID du salon Discord où publier
FEEDS = {
    "https://www.infolibertaire.net/feed": 1565775693109919794,  # Salon du premier flux
    "https://portail.basta.media/spip.php?page=backend": 1565784501970407616,
    "https://paris-luttes.info/spip.php?page=backend": 1565794982797774848,
    "https://www.problematik-media.com/feed.xml": 1565829882691199107,
    "https://api.blast-info.fr/rss.xml": 1566144707334246420,
    "https://streetpress.com/rss.xml": 1566193832733839390,
    "https://www.mediapart.fr/journal/podcasts/rss": 1566384937442086993,  # mediapart
    "https://www.youtube.com/feeds/videos.xml?channel_id=UCdnaDhU-LDQrIEEmSIfq0-Q": 1566384937442086993,  # mediapart
    "https://www.youtube.com/feeds/videos.xml?channel_id=UCGvjUWz3mGV9cssraATuEsw": 1566387582579908608,  # radionova

}

# Chaînes Twitch (nom dans l'URL twitch.tv/<nom>) -> ID du salon Discord où publier
# Récupération via yt-dlp : pas de compte ni d'API Twitch.
TWITCH_CHANNELS = {
    "ostpolitik": 1566875561941401630,  
    "laurenemarx": 1566875561941401630,
}

MAX_POSTS_PER_RUN = 30
FIRST_RUN_POSTS = 30
TWITCH_SCAN_LIMIT = 30  # nb de vidéos récentes regardées par chaîne Twitch à chaque passage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("rss-bot")

client = discord.Client(intents=discord.Intents.default())


# ---------- Base de données ----------

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id       TEXT PRIMARY KEY,
                feed_url TEXT NOT NULL,
                title    TEXT,
                link     TEXT,
                seen_at  TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_feed ON articles(feed_url)")


def get_seen_ids() -> set[str]:
    with sqlite3.connect(DB_PATH) as conn:
        return {row[0] for row in conn.execute("SELECT id FROM articles")}


def get_seen_links() -> set[str]:
    with sqlite3.connect(DB_PATH) as conn:
        return {
            row[0] for row in conn.execute(
                "SELECT link FROM articles WHERE link IS NOT NULL AND link != ''"
            )
        }


def feed_known(feed_url: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT 1 FROM articles WHERE feed_url = ? LIMIT 1",
            (feed_url,),
        ).fetchone()
        return row is not None


def mark_seen(article_id: str, feed_url: str, title: str, link: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO articles (id, feed_url, title, link, seen_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                article_id,
                feed_url,
                title,
                link,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


# ---------- Utilitaires RSS ----------

def entry_id(entry) -> str:
    return entry.get("id") or entry.get("link") or entry.get("title", "")


def clean_html(text: str, limit: int = 300) -> str:
    text = re.sub(r"<[^>]+>", "", text or "").strip()
    return text[:limit] + "…" if len(text) > limit else text


def build_embed(entry, source_title: str) -> discord.Embed:
    embed = discord.Embed(
        title=(entry.get("title") or "Sans titre")[:256],
        url=entry.get("link"),
        description=clean_html(entry.get("summary", "")),
        color=discord.Color.blue(),
    )
    embed.set_footer(text=source_title[:100])
    return embed


# ---------- Utilitaires Twitch (yt-dlp) ----------

def twitch_video_number(entry) -> str | None:
    """ID numérique d'une vidéo Twitch à partir d'une entrée yt-dlp."""
    vid = str(entry.get("id") or "").lstrip("v")
    if vid.isdigit():
        return vid
    m = re.search(r"/videos/(\d+)", str(entry.get("url") or ""))
    return m.group(1) if m else None


def twitch_thumbnail(entry) -> str | None:
    url = entry.get("thumbnail")
    if not url and entry.get("thumbnails"):
        url = entry["thumbnails"][-1].get("url")
    if not url:
        return None
    # Les miniatures Twitch contiennent parfois des gabarits de taille à remplir
    return (url.replace("%{width}", "1280").replace("%{height}", "720")
               .replace("{width}", "1280").replace("{height}", "720"))


def fetch_twitch_videos(channel_name: str) -> list[dict]:
    """Vidéos récentes d'une chaîne Twitch, de la plus récente à la plus ancienne."""
    url = f"https://www.twitch.tv/{channel_name}/videos?filter=all&sort=time"
    options = {
        "extract_flat": "in_playlist",
        "playlistend": TWITCH_SCAN_LIMIT,
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False) or {}

    videos = []
    for e in info.get("entries") or []:
        if not e:
            continue
        num = twitch_video_number(e)
        if not num:
            continue
        videos.append({
            "id": f"twitch:{num}",
            "title": e.get("title") or "Sans titre",
            "link": f"https://www.twitch.tv/videos/{num}",
            "duration": e.get("duration"),
            "timestamp": e.get("timestamp"),
            "thumbnail": twitch_thumbnail(e),
        })
    return videos


def format_duration(seconds) -> str | None:
    if not seconds:
        return None
    h, rest = divmod(int(seconds), 3600)
    m, s = divmod(rest, 60)
    return f"{h}h{m:02d}" if h else f"{m}min{s:02d}"


def build_twitch_embed(video: dict, channel_name: str) -> discord.Embed:
    duration = format_duration(video["duration"])
    embed = discord.Embed(
        title=video["title"][:256],
        url=video["link"],
        description=f"Durée : {duration}" if duration else None,
        color=discord.Color.purple(),
        timestamp=(datetime.fromtimestamp(video["timestamp"], timezone.utc)
                   if video["timestamp"] else None),
    )
    if video["thumbnail"]:
        embed.set_image(url=video["thumbnail"])
    embed.set_footer(text=f"Twitch · {channel_name}"[:100])
    return embed


async def check_twitch(seen: set[str], seen_links: set[str]):
    for name, channel_id in TWITCH_CHANNELS.items():
        name = name.lower().strip()
        feed_key = f"twitch:{name}"
        try:
            channel = client.get_channel(channel_id)
            if channel is None:
                channel = await client.fetch_channel(channel_id)

            videos = await asyncio.to_thread(fetch_twitch_videos, name)
            if not videos:
                log.warning("Aucune vidéo pour la chaîne Twitch %s", name)
                continue

            is_new_feed = not await asyncio.to_thread(feed_known, feed_key)

            # On ignore aussi les vidéos déjà publiées par l'ancien flux openrss (même lien).
            new_videos = [
                v for v in videos
                if v["id"] not in seen and v["link"] not in seen_links
            ]
            new_videos.reverse()  # du plus ancien au plus récent

            if is_new_feed:
                split = max(len(new_videos) - FIRST_RUN_POSTS, 0)
                to_skip = new_videos[:split]
                to_post = new_videos[split:]

                # Lors du premier passage, on marque les anciennes vidéos
                # comme vues sans les publier.
                for v in to_skip:
                    await asyncio.to_thread(mark_seen, v["id"], feed_key, v["title"], v["link"])
                    seen.add(v["id"])
                    seen_links.add(v["link"])
            else:
                to_post = new_videos[:MAX_POSTS_PER_RUN]

            for v in to_post:
                await channel.send(embed=build_twitch_embed(v, name))

                await asyncio.to_thread(mark_seen, v["id"], feed_key, v["title"], v["link"])
                seen.add(v["id"])
                seen_links.add(v["link"])

            log.info(
                "Twitch %s : %d vidéo(s) publiée(s) dans le salon %s",
                name,
                len(to_post),
                channel_id,
            )

        except Exception:
            log.exception("Erreur lors du traitement de la chaîne Twitch %s", name)


# ---------- Tâche périodique ----------

@tasks.loop(minutes=10)
async def check_feeds():
    seen = await asyncio.to_thread(get_seen_ids)

    for url, channel_id in FEEDS.items():
        try:
            channel = client.get_channel(channel_id)
            if channel is None:
                channel = await client.fetch_channel(channel_id)

            parsed = await asyncio.to_thread(feedparser.parse, url)
            if not parsed.entries:
                log.warning("Aucune entrée pour %s", url)
                continue

            source = parsed.feed.get("title", url)
            is_new_feed = not await asyncio.to_thread(feed_known, url)

            # feedparser renvoie souvent les articles les plus récents en premier.
            # On inverse donc la liste pour publier du plus ancien au plus récent.
            new_entries = [
                entry for entry in parsed.entries
                if entry_id(entry) not in seen
            ]
            new_entries.reverse()

            if is_new_feed:
                split = max(len(new_entries) - FIRST_RUN_POSTS, 0)
                to_skip = new_entries[:split]
                to_post = new_entries[split:]

                # Lors du premier passage, on marque les anciens articles
                # comme vus sans les publier.
                for entry in to_skip:
                    article_id = entry_id(entry)
                    await asyncio.to_thread(
                        mark_seen,
                        article_id,
                        url,
                        entry.get("title", ""),
                        entry.get("link", ""),
                    )
                    seen.add(article_id)
            else:
                to_post = new_entries[:MAX_POSTS_PER_RUN]

            for entry in to_post:
                await channel.send(embed=build_embed(entry, source))

                article_id = entry_id(entry)
                await asyncio.to_thread(
                    mark_seen,
                    article_id,
                    url,
                    entry.get("title", ""),
                    entry.get("link", ""),
                )
                seen.add(article_id)

            log.info(
                "%s : %d article(s) publié(s) dans le salon %s",
                source,
                len(to_post),
                channel_id,
            )

        except Exception:
            log.exception("Erreur lors du traitement de %s", url)

    # ---- Chaînes Twitch ----
    seen_links = await asyncio.to_thread(get_seen_links)
    await check_twitch(seen, seen_links)


# ---------- Événements ----------

@client.event
async def on_ready():
    log.info("Connecté en tant que %s", client.user)
    if not check_feeds.is_running():
        check_feeds.start()


def main():
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN manquant dans .env")

    init_db()
    client.run(TOKEN, log_handler=None)


if __name__ == "__main__":
    main()