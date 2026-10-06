#!/usr/bin/env python3
"""
exocean — refresh content/bluesky.json from the lab's Bluesky account.

Pulls the most recent posts written by the account named in content/site.json
("bluesky" field) through Bluesky's public, read-only API — no login, no key —
and stores them so build.py can show a "Latest from Bluesky" strip on the
News page. Reposts and replies are skipped; only the lab's own posts appear.

Posts tagged #exoceannews also become news items on the site (News page and
home page), with their photos saved into assets/img/ — so posting on Bluesky
is enough to keep the site's news fresh.

Run automatically once a week by the GitHub Action; can also be run by hand:

    python3 fetch_bluesky.py

Nothing is written if Bluesky cannot be reached, so the page never goes blank.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request
from datetime import date
from html import escape

ROOT = pathlib.Path(__file__).parent
CONTENT = ROOT / "content"
OUT = CONTENT / "bluesky.json"
API = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"
KEEP = 4          # posts kept for the page
LOOKBACK = 60     # posts fetched before filtering
NEWS_TAG = "exoceannews"   # posts with this hashtag become news items
NEWS_KEEP = 30
IMG = ROOT / "assets" / "img"
UA = {"User-Agent": "exocean-website (https://github.com/exocean-lab/exocean-lab.github.io)"}


def handle_from_site() -> str:
    site = json.loads((CONTENT / "site.json").read_text(encoding="utf-8"))
    url = site.get("bluesky", "")
    # https://bsky.app/profile/<handle>  ->  <handle>
    return url.rstrip("/").split("/")[-1]


def render(record: dict) -> str:
    """Post text as HTML. Bluesky marks links and mentions with byte offsets
    ("facets") into the UTF-8 text; turn those into <a> tags, escape the rest."""
    text = record.get("text", "")
    raw = text.encode("utf-8")
    facets = sorted(record.get("facets", []), key=lambda f: f["index"]["byteStart"])
    out, pos = [], 0
    for f in facets:
        start, end = f["index"]["byteStart"], f["index"]["byteEnd"]
        if start < pos or end > len(raw):
            continue
        href = None
        for feat in f.get("features", []):
            t = feat.get("$type", "")
            if t.endswith("#link"):
                href = feat.get("uri")
            elif t.endswith("#mention") and feat.get("did"):
                href = "https://bsky.app/profile/" + feat["did"]
            elif t.endswith("#tag") and feat.get("tag"):
                href = "https://bsky.app/hashtag/" + urllib.parse.quote(feat["tag"])
        out.append(escape(raw[pos:start].decode("utf-8", "replace")))
        label = escape(raw[start:end].decode("utf-8", "replace"))
        out.append(f'<a href="{escape(href)}">{label}</a>' if href else label)
        pos = end
    out.append(escape(raw[pos:].decode("utf-8", "replace")))
    return "".join(out).replace("\n", "<br>")


def is_news(record: dict) -> bool:
    for f in record.get("facets", []):
        for feat in f.get("features", []):
            if feat.get("$type", "").endswith("#tag") and (feat.get("tag") or "").lower() == NEWS_TAG:
                return True
    return f"#{NEWS_TAG}" in (record.get("text") or "").lower()


def strip_tag(text: str) -> str:
    return re.sub(r"\s*#" + NEWS_TAG + r"\b", "", text or "", flags=re.I).strip()


def save_image(url: str, name: str) -> str | None:
    """Download a post's photo into assets/img/ (once); returns the file name."""
    dest = IMG / name
    if dest.exists():
        return name
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as resp:
            data = resp.read(8_000_001)
        if len(data) > 8_000_000 or data[:2] != b"\xff\xd8":
            return None
        dest.write_bytes(data)
        return name
    except Exception:
        return None


def news_item(post: dict, record: dict, url: str, rkey: str) -> dict:
    """A Bluesky post turned into a news item: first sentence as the title."""
    text = strip_tag(record.get("text", ""))
    first = re.split(r"(?<=[.!?])\s|\n", text, maxsplit=1)[0].strip()
    title = first if len(first) <= 110 else first[:109].rsplit(" ", 1)[0] + "…"
    item = {"date": record.get("createdAt", "")[:10], "url": url, "title": title, "text": text, "images": []}
    embed = post.get("embed") or {}
    if embed.get("$type", "").startswith("app.bsky.embed.recordWithMedia"):
        embed = embed.get("media") or {}
    if embed.get("$type", "").startswith("app.bsky.embed.images"):
        for i, im in enumerate(embed.get("images", [])[:4]):
            name = save_image(im.get("fullsize") or im.get("thumb", ""), f"bsky-{rkey}-{i + 1}.jpg")
            if name:
                item["images"].append({"file": name, "alt": im.get("alt") or ""})
    return item


def fetch(handle: str) -> tuple[list[dict], list[dict]]:
    query = urllib.parse.urlencode({"actor": handle, "limit": LOOKBACK, "filter": "posts_no_replies"})
    req = urllib.request.Request(API + "?" + query, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        feed = json.load(resp).get("feed", [])
    posts, news = [], []
    for entry in feed:
        if "reason" in entry:            # a repost of someone else's post
            continue
        post = entry["post"]
        if post["author"]["handle"] != handle:
            continue
        record = post["record"]
        if record.get("reply"):
            continue
        rkey = post["uri"].rsplit("/", 1)[-1]
        if is_news(record):
            news.append(news_item(post, record, f"https://bsky.app/profile/{handle}/post/{rkey}", rkey))
        if len(posts) == KEEP:
            continue
        item = {
            "date": record.get("createdAt", "")[:10],
            "url": f"https://bsky.app/profile/{handle}/post/{rkey}",
            "html": render(record),
            "likes": post.get("likeCount", 0),
            "reposts": post.get("repostCount", 0),
        }
        # What the post carries besides text: a quoted post, a link card, photos.
        embed = post.get("embed") or {}
        etype = embed.get("$type", "")
        if etype.startswith("app.bsky.embed.recordWithMedia"):
            quoted = (embed.get("record") or {}).get("record") or {}
            embed = embed.get("media") or {}
            etype = embed.get("$type", "")
        elif etype.startswith("app.bsky.embed.record"):
            quoted = embed.get("record") or {}
            embed, etype = {}, ""
        else:
            quoted = {}
        if quoted.get("$type", "").endswith("#viewRecord"):
            author = quoted.get("author", {})
            value = quoted.get("value") or {}
            q_rkey = quoted.get("uri", "").rsplit("/", 1)[-1]
            item["quote"] = {
                "author": author.get("displayName") or author.get("handle", ""),
                "handle": author.get("handle", ""),
                "text": (value.get("text") or "").strip(),
                "url": f"https://bsky.app/profile/{author.get('handle', '')}/post/{q_rkey}",
            }
            for sub in quoted.get("embeds", []):       # link card inside the quoted post
                if sub.get("$type", "").startswith("app.bsky.embed.external") and sub.get("external", {}).get("uri"):
                    embed, etype = sub, sub["$type"]
                    break
        if etype.startswith("app.bsky.embed.external") and embed.get("external", {}).get("uri"):
            item["link_url"] = embed["external"]["uri"]
            item["link_title"] = (embed["external"].get("title") or embed["external"]["uri"]).strip()
        elif etype.startswith("app.bsky.embed.images"):
            item["images"] = len(embed.get("images", []))
        posts.append(item)
    return posts, news


def main() -> int:
    handle = handle_from_site()
    if not handle:
        print("No Bluesky account in content/site.json — nothing to fetch.")
        return 1
    try:
        posts, news = fetch(handle)
    except Exception as exc:
        print(f"Bluesky could not be queried ({exc}); keeping the existing file.")
        return 1
    if not posts:
        print("No posts found; keeping the existing file.")
        return 1

    previous = {}
    if OUT.exists():
        try:
            previous = json.loads(OUT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = {}
    # news items accumulate: older tagged posts stay even when they leave the feed window
    known = {n["url"]: n for n in previous.get("news", [])}
    for n in news:
        known[n["url"]] = n
    all_news = sorted(known.values(), key=lambda n: n["date"], reverse=True)[:NEWS_KEEP]

    strip = lambda ps: [{k: v for k, v in p.items() if k not in ("likes", "reposts")} for p in ps]
    if strip(previous.get("posts", [])) == strip(posts) and previous.get("news", []) == all_news:
        print(f"bluesky.json already up to date ({len(posts)} posts, {len(all_news)} news items).")
        return 0

    payload = {"handle": handle, "updated": date.today().isoformat(), "posts": posts, "news": all_news}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} — {len(posts)} posts and {len(all_news)} news items from @{handle}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
