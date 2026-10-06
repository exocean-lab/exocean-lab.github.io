#!/usr/bin/env python3
"""
exocean — static site generator.

Reads the JSON files in content/ and writes plain HTML next to this file.
No dependencies beyond the Python standard library.

    python3 build.py

Everything an editor would ever want to change lives in content/*.json:
site.json (home page, Research, Services, Data & Models, Join us, Contact,
legal notice), team.json, projects.json, news.json, and fr.json (the French
versions of Services, Join us and Contact). Nothing in this file needs
touching to add a person, a project, a news item or an instrument.

Three more files are written by scripts, not by hand: content/publications.json
(fetch_hal.py), content/bluesky.json (fetch_bluesky.py) and the WebP copies of
the photos in assets/img/w/ (optimise_images.py). The GitHub Action runs all
three. If any is missing the site still builds.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import struct
import unicodedata
from html import escape

ROOT = pathlib.Path(__file__).parent
CONTENT = ROOT / "content"
OUT = ROOT
IMG = ROOT / "assets" / "img"


def load(name: str, optional: bool = False) -> dict:
    path = CONTENT / f"{name}.json"
    if optional and not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


SITE = load("site")
TEAM = load("team")
PROJECTS = load("projects")
NEWS = load("news")
FR = load("fr", optional=True)
PUBLICATIONS = load("publications", optional=True)
try:                                     # tidy author names stored before fetch_hal.py did it
    import sys
    sys.dont_write_bytecode = True
    from fetch_hal import tidy_name
    for _it in (PUBLICATIONS or {}).get("items", []):
        _it["authors"] = [tidy_name(a) for a in _it.get("authors", [])]
except ImportError:
    pass
BLUESKY = load("bluesky", optional=True)


def _version(path: str) -> str:
    """Short content hash of an asset, appended as ?v=… to its URL: when the file
    changes, the URL changes, so browsers cannot keep using a stale cached copy."""
    try:
        return hashlib.sha1((ROOT / path).read_bytes()).hexdigest()[:8]
    except OSError:
        return ""


CSS_V = _version("assets/css/style.css")
JS_V = _version("assets/js/main.js")

ALL_MEMBERS = {m["slug"]: m for g in TEAM["groups"] for m in g.get("members", [])}
PROJECT_BY_SLUG = {p["slug"]: p for p in PROJECTS["projects"]}

# Absolute address of the site, without trailing slash. Used wherever a
# relative link would not do: link previews, the sitemap, the 404 page.
BASE = (SITE.get("baseurl") or "").rstrip("/")
ABS = -1  # pass as `depth` to get absolute URLs

MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"],
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"],
}

# Pages that also exist in French, under fr/ with the same file name.
FR_PAGES = ("services.html", "join.html", "contact.html")

# Words of the page furniture (menu, footer…) in both languages. Everything
# else comes from the content files.
UI = {
    "en": {
        "skip": "Skip to content", "menu": "Menu", "home": "home",
        "nav": {}, "cta": None,
        "switch": "Français", "switch_title": "Version française de cette page",
        "f_explore": "Explore", "f_lab": "The lab", "f_follow": "Follow",
        "f_legal": "Legal notice", "f_access": "Accessibility",
        "f_french": "En français", "f_french_pages": [("services.html", "Services"), ("join.html", "Nous rejoindre"), ("contact.html", "Contact")],
        "f_place": "CEREGE, Technopôle de l'Environnement Arbois-Méditerranée, Aix-en-Provence, France",
        "tagline": None, "colon": ": ",
        "read_more": "Read more", "all_news": "All news", "on_bluesky": "On Bluesky",
        "photos": "photos", "photo": "photo",
    },
    "fr": {
        "skip": "Aller au contenu", "menu": "Menu", "home": "accueil",
        "nav": {"projects.html": "Recherche", "services.html": "Services", "data.html": "Données et modèles",
                "publications.html": "Publications", "team.html": "Équipe", "news.html": "Actualités",
                "join.html": "Nous rejoindre"},
        "cta": "Contact",
        "switch": "English", "switch_title": "English version of this page",
        "f_explore": "Explorer", "f_lab": "Le laboratoire", "f_follow": "Suivre",
        "f_legal": "Mentions légales", "f_access": "Accessibilité",
        "f_french": "In English", "f_french_pages": [("services.html", "Services"), ("join.html", "Join us"), ("contact.html", "Contact")],
        "f_place": "CEREGE, Technopôle de l'Environnement Arbois-Méditerranée, Aix-en-Provence, France",
        "tagline": "Laboratoire d'océanologie expérimentale", "colon": " : ",
        "read_more": "Lire la suite", "all_news": "Toutes les actualités", "on_bluesky": "Sur Bluesky",
        "photos": "photos", "photo": "photo",
    },
}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def rel(depth: int, path: str) -> str:
    """Resolve a root-relative path for a page nested `depth` levels down.
    With depth=ABS the result is an absolute URL (needs "baseurl" in site.json)."""
    if depth == ABS:
        return f"{BASE}/{path}"
    return ("../" * depth) + path


def absurl(path: str) -> str:
    return f"{BASE}/{path}" if BASE else path


def month_name(ym: str, lang: str = "en") -> str:
    """'2026-02' -> 'February 2026' (or 'février 2026'); anything else untouched."""
    m = re.fullmatch(r"(\d{4})-(\d{2})", ym or "")
    if not m:
        return ym or ""
    return f"{MONTHS[lang][int(m.group(2)) - 1]} {m.group(1)}"


def day_name(ymd: str, lang: str = "en") -> str:
    y, m, d = ymd.split("-")
    return f"{int(d)} {MONTHS[lang][int(m) - 1]} {y}"


_HYPHENS = re.compile("[\u2010\u2011\u2012\u2013\u2212]")


def _name_key(name: str) -> tuple[str, str]:
    """('j', 'suarez-ibarra') for 'Jaime Y. Suárez-Ibarra' — first initial and
    last word, accents stripped, so HAL's spelling matches team.json's."""
    plain = unicodedata.normalize("NFKD", _HYPHENS.sub("-", name)).encode("ascii", "ignore").decode()
    words = [w for w in re.split(r"[\s,]+", plain.strip()) if w]
    if not words:
        return ("", "")
    return (words[0][0].lower(), words[-1].lower().strip("."))


TEAM_KEYS = {_name_key(m["name"]): slug for slug, m in ALL_MEMBERS.items()}


def img_name(value: str) -> str:
    """An image as named in the content files: "photo.jpg" — or "/photo.jpg"
    and "assets/img/photo.jpg", as the Pages CMS editor may write it."""
    name = (value or "").strip().lstrip("/")
    for prefix in ("exocean/assets/img/", "assets/img/"):
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name


def asset(depth: int, filename: str) -> str:
    return rel(depth, f"assets/img/{img_name(filename)}")


def email_span(user: str, domain: str, cls: str = "eml") -> str:
    """An address assembled by JavaScript in the browser, not sitting in the
    markup for harvesters."""
    return f'<span class="{cls}" data-u="{escape(user)}" data-d="{escape(domain)}"></span>'


def lab_email(cls: str = "eml") -> str:
    return email_span(*SITE["email"].split("@"), cls=cls)


def person_link(depth: int, slug: str, label: str | None = None) -> str:
    member = ALL_MEMBERS.get(slug)
    label = label or (member["name"] if member else slug)
    if member and member.get("bio"):
        return f'<a href="{rel(depth, "people/" + slug + ".html")}">{escape(label)}</a>'
    return escape(label)


def initials(name: str) -> str:
    parts = [p for p in name.replace("-", " ").split() if p and p[0].isalpha()]
    if not parts:
        return "?"
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


def bullets(items: list[str]) -> str:
    lis = "\n".join(f"      <li>{i}</li>" for i in items)
    return f'    <ul class="bullets">\n{lis}\n    </ul>'


def plain(html_text: str) -> str:
    """Text content of a snippet of HTML (for excerpts and descriptions)."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html_text or "")).strip()


def excerpt(html_text: str, n: int = 200) -> str:
    t = plain(html_text)
    if len(t) <= n:
        return t
    cut = t[:n].rsplit(" ", 1)[0].rstrip(",;:—–-")
    return cut + "…"


def fill(text: str) -> str:
    """Content placeholders: {email} becomes the lab's (JS-assembled) address."""
    return (text or "").replace("{email}", lab_email())


_HREF = re.compile(r'(\b(?:href|src)=")([^"]*)(")')


def fix_links(html_text: str, depth: int, lang: str = "en") -> str:
    """Content files write links as seen from the site's root ("services.html",
    "people/x.html"). On a page nested `depth` folders down they need "../"; on
    a French page, links to pages that exist in French stay in fr/."""
    if not html_text or depth <= 0:
        return html_text

    def sub(m: re.Match) -> str:
        url = m.group(2)
        if not url or re.match(r"^([a-z][a-z0-9+.-]*:|#|/|\.\./)", url, re.I):
            return m.group(0)
        page = url.split("#", 1)[0].split("?", 1)[0]
        if lang == "fr" and depth == 1 and page in FR_PAGES:
            return m.group(0)
        return m.group(1) + ("../" * depth) + url + m.group(3)

    return _HREF.sub(sub, html_text)


# --------------------------------------------------------------------------
# images: sizes (for width/height, so nothing jumps while loading) and the
# lighter WebP copies made by optimise_images.py
# --------------------------------------------------------------------------

_SIZE_CACHE: dict[str, tuple[int, int] | None] = {}


def image_size(path: pathlib.Path) -> tuple[int, int] | None:
    """Pixel size of a PNG, JPEG, GIF, WebP or SVG file, read from its header."""
    key = str(path)
    if key in _SIZE_CACHE:
        return _SIZE_CACHE[key]
    size = None
    try:
        data = path.read_bytes()
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            size = struct.unpack(">II", data[16:24])
        elif data[:6] in (b"GIF87a", b"GIF89a"):
            size = struct.unpack("<HH", data[6:10])
        elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            chunk = data[12:16]
            if chunk == b"VP8 ":
                w, h = struct.unpack("<HH", data[26:30])
                size = (w & 0x3FFF, h & 0x3FFF)
            elif chunk == b"VP8L":
                b = data[21:25]
                size = (1 + (((b[1] & 0x3F) << 8) | b[0]), 1 + (((b[3] & 0xF) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6)))
            elif chunk == b"VP8X":
                size = (1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little"))
        elif data[:2] == b"\xff\xd8":
            i = 2
            while i < len(data) - 9:
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    h, w = struct.unpack(">HH", data[i + 5:i + 9])
                    size = (w, h)
                    break
                if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                    i += 2
                    continue
                i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
        elif path.suffix == ".svg":
            m = re.search(rb'viewBox="[\d.\s-]*?([\d.]+)\s+([\d.]+)"', data)
            if m:
                size = (round(float(m.group(1))), round(float(m.group(2))))
    except (OSError, struct.error, IndexError):
        size = None
    _SIZE_CACHE[key] = size
    return size


VARIANT_DIR = IMG / "w"
_VARIANT_RE = re.compile(r"^(?P<stem>.+)-(?P<w>\d+)\.webp$")
VARIANTS: dict[str, list[tuple[int, str]]] = {}
if VARIANT_DIR.is_dir():
    for f in VARIANT_DIR.iterdir():
        m = _VARIANT_RE.match(f.name)
        if m:
            VARIANTS.setdefault(m.group("stem"), []).append((int(m.group("w")), f.name))
    for v in VARIANTS.values():
        v.sort()


def picture(depth: int, filename: str, alt: str, sizes: str = "100vw", cls: str = "",
            lazy: bool = True, priority: bool = False) -> str:
    """An <img> with its intrinsic size, wrapped in a <picture> offering the WebP
    copies when they exist; the original file is the fallback."""
    filename = img_name(filename)
    src = asset(depth, filename)
    dims = image_size(IMG / filename)
    wh = f' width="{dims[0]}" height="{dims[1]}"' if dims else ""
    attrs = f'{wh}{" loading=\"lazy\"" if lazy and not priority else ""} decoding="async"'
    if priority:
        attrs += ' fetchpriority="high"'
    c = f' class="{cls}"' if cls else ""
    img = f'<img src="{src}" alt="{escape(alt)}"{attrs}{c}>'
    stem = pathlib.Path(filename).stem
    vs = VARIANTS.get(stem)
    if not vs or filename.endswith(".svg"):
        return img
    srcset = ", ".join(f'{rel(depth, "assets/img/w/" + name)} {w}w' for w, name in vs)
    return f'<picture><source type="image/webp" srcset="{srcset}" sizes="{escape(sizes)}">{img}</picture>'


# --------------------------------------------------------------------------
# page chrome
# --------------------------------------------------------------------------

def jsonld_org() -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "ResearchOrganization",
        "name": SITE["name"],
        "alternateName": SITE["tagline"],
        "description": SITE["description"],
        "url": absurl(""),
        "logo": absurl("assets/img/favicon.png"),
        "address": {
            "@type": "PostalAddress",
            "streetAddress": "Technopôle de l'Arbois-Méditerranée, Avenue Louis Philibert, BP 80",
            "postalCode": "13545",
            "addressLocality": "Aix-en-Provence",
            "addressCountry": "FR",
        },
        "parentOrganization": {"@type": "ResearchOrganization", "name": "CEREGE", "url": "https://www.cerege.fr/"},
        "sameAs": [SITE["bluesky"]],
    }
    if SITE.get("geo"):
        data["location"] = {"@type": "Place", "geo": {"@type": "GeoCoordinates",
                                                       "latitude": SITE["geo"]["lat"], "longitude": SITE["geo"]["lon"]}}
    return json.dumps(data, ensure_ascii=False)


def nav_label(item: dict, lang: str) -> str:
    return UI[lang]["nav"].get(item["href"], item["label"])


def nav_href(depth: int, href: str, lang: str) -> str:
    if lang == "fr" and href in FR_PAGES:
        return href if depth == 1 else rel(depth, "fr/" + href)
    return rel(depth, href)


def head(depth: int, title: str, description: str, active: str, path: str, *,
         lang: str = "en", alt_path: str | None = None, image: str | None = None,
         jsonld: str | None = None, body_class: str = "") -> str:
    ui = UI[lang]
    if path == "index.html":
        full_title = f'{SITE["name"]} — {SITE["tagline"]}, CEREGE'
    elif lang == "fr":
        full_title = f'{title} — laboratoire {SITE["name"]}'
    else:
        full_title = f'{title} — {SITE["name"]}'
    items = []
    for item in SITE["nav"]:
        current = ' aria-current="page"' if item["href"] == active else ""
        items.append(f'          <li><a href="{nav_href(depth, item["href"], lang)}"{current}>{escape(nav_label(item, lang))}</a></li>')
    cta = SITE.get("nav_cta") or {"label": "Contact", "href": "contact.html"}
    cta_current = ' aria-current="page"' if cta["href"] == active else ""
    cta_html = (f'<a class="nav-cta" href="{nav_href(depth, cta["href"], lang)}"{cta_current}>'
                f'{escape(ui["cta"] or cta["label"])}</a>')
    switch = ""
    if alt_path:
        other = "fr" if lang == "en" else "en"
        switch = (f'\n        <a class="lang-switch" href="{rel(depth, alt_path)}" hreflang="{other}" lang="{other}" '
                  f'title="{escape(ui["switch_title"])}">{escape(ui["switch"])}</a>')

    page_url = absurl("" if path == "index.html" else path)
    canonical = ""
    if BASE and path != "404.html":
        canonical = f'<link rel="canonical" href="{escape(page_url)}">\n<meta property="og:url" content="{escape(page_url)}">\n'
        if alt_path:
            en_path, fr_path = (path, alt_path) if lang == "en" else (alt_path, path)
            canonical += (f'<link rel="alternate" hreflang="en" href="{escape(absurl(en_path))}">\n'
                          f'<link rel="alternate" hreflang="fr" href="{escape(absurl(fr_path))}">\n'
                          f'<link rel="alternate" hreflang="x-default" href="{escape(absurl(en_path))}">\n')
    share_file = img_name(image) if image else "share.jpg"
    dims = image_size(IMG / share_file)
    og_dims = f'<meta property="og:image:width" content="{dims[0]}">\n<meta property="og:image:height" content="{dims[1]}">\n' if dims else ""
    ld = f'<script type="application/ld+json">{jsonld}</script>\n' if jsonld else ""
    logo_dims = image_size(IMG / "logo.svg") or (694, 213)
    body_cls = f' class="{body_class}"' if body_class else ""
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(full_title)}</title>
<meta name="description" content="{escape(description)}">
{canonical}<meta property="og:site_name" content="{escape(SITE['name'])}">
<meta property="og:title" content="{escape(full_title)}">
<meta property="og:description" content="{escape(description)}">
<meta property="og:type" content="{'article' if path.startswith('news/') else 'website'}">
<meta property="og:locale" content="{'fr_FR' if lang == 'fr' else 'en_GB'}">
<meta property="og:image" content="{escape(absurl('assets/img/' + share_file))}">
{og_dims}<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#0a0e1a">
<link rel="icon" href="{asset(depth, 'mark.svg')}" type="image/svg+xml">
<link rel="icon" href="{asset(depth, 'favicon-48.png')}" sizes="48x48" type="image/png">
<link rel="apple-touch-icon" href="{asset(depth, 'apple-touch-icon.png')}">
<link rel="preload" href="{rel(depth, 'assets/fonts/cabin-latin.woff2')}" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{rel(depth, 'assets/css/style.css')}?v={CSS_V}">
<script>document.documentElement.classList.add("js")</script>
{ld}</head>
<body{body_cls}>
<a class="skip" href="#main">{escape(ui['skip'])}</a>

<header class="site-header">
  <div class="wrap header-inner">
    <a class="brand" href="{rel(depth, 'index.html') if lang == 'en' else rel(depth, 'index.html')}">
      <img src="{asset(depth, 'logo.svg')}" alt="{escape(SITE['name'])} — {escape(ui['home'])}" width="{logo_dims[0]}" height="{logo_dims[1]}">
    </a>
    <button class="menu-toggle" type="button" aria-expanded="false" aria-controls="site-nav"><span class="bars" aria-hidden="true"></span>{escape(ui['menu'])}</button>
    <nav id="site-nav" class="site-nav" aria-label="{'Menu principal' if lang == 'fr' else 'Main'}">
      <ul>
{chr(10).join(items)}
      </ul>
      {cta_html}{switch}
    </nav>
  </div>
</header>

<main id="main">
"""


FOOT_LOGO = image_size(IMG / "logo-white.svg") or (694, 213)


def foot(depth: int, lang: str = "en") -> str:
    ui = UI[lang]
    f = SITE["footer"]
    nav = SITE["nav"]
    explore = [i for i in nav if i["href"] in ("projects.html", "services.html", "data.html", "publications.html")]
    lab = [i for i in nav if i not in explore]
    cta = SITE.get("nav_cta") or {"label": "Contact", "href": "contact.html"}

    def li(i):
        return f'<li><a href="{nav_href(depth, i["href"], lang)}">{escape(nav_label(i, lang))}</a></li>'

    lab_items = "".join(li(i) for i in lab) + li({"label": ui["cta"] or cta["label"], "href": cta["href"]})
    if lang == "en":
        other = "".join(f'<li><a href="{rel(depth, "fr/" + p)}" lang="fr" hreflang="fr">{escape(l)}</a></li>' for p, l in ui["f_french_pages"])
    else:
        other = "".join(f'<li><a href="{rel(depth, p)}" lang="en" hreflang="en">{escape(l)}</a></li>' for p, l in ui["f_french_pages"])
    status = SITE.get("legal", {}).get("status_fr" if lang == "fr" else "status", "")
    legal_href = rel(depth, "legal.html") + ("#fr" if lang == "fr" else "")
    access_href = rel(depth, "legal.html") + ("#accessibilite" if lang == "fr" else "#accessibility")
    partners = picture(depth, f["partners_image"], f["partners_alt"], sizes="(max-width: 660px) 92vw, 620px")
    return f"""</main>

<div class="partners-band"><div class="wrap">{partners}</div></div>
<footer class="site-footer">
  <div class="wrap footer-main">
    <div class="footer-brand">
      <img src="{asset(depth, 'logo-white.svg')}" alt="{escape(SITE['name'])}" width="{FOOT_LOGO[0]}" height="{FOOT_LOGO[1]}" loading="lazy">
      <p>{escape(ui['tagline'] or SITE['tagline'])}<br><a href="{escape(f['cerege_url'])}">CEREGE</a> · Aix-en-Provence, France</p>
    </div>
    <nav aria-label="{escape(ui['f_explore'])}">
      <h2>{escape(ui['f_explore'])}</h2>
      <ul>{''.join(li(i) for i in explore)}</ul>
    </nav>
    <nav aria-label="{escape(ui['f_lab'])}">
      <h2>{escape(ui['f_lab'])}</h2>
      <ul>{lab_items}</ul>
    </nav>
    <div>
      <h2>{escape(ui['f_follow'])}</h2>
      <ul><li><a href="{escape(SITE['bluesky'])}">Bluesky</a></li></ul>
      <h2 style="margin-top:1.2rem">{escape(ui['f_french'])}</h2>
      <ul>{other}</ul>
    </div>
  </div>
  <div class="wrap footer-bottom">
    <span>{escape(SITE['name'])} · {escape(ui['f_place'])}</span>
    <span><a href="{legal_href}">{escape(ui['f_legal'])}</a> · <a href="{access_href}">{escape(ui['f_access'])}{ui['colon'] + escape(status) if status else ''}</a></span>
  </div>
</footer>
<script src="{rel(depth, 'assets/js/main.js')}?v={JS_V}"></script>
{analytics()}</body>
</html>
"""


def analytics() -> str:
    """GoatCounter visitor counting — privacy-friendly, no cookies, no banner
    needed. Off until "goatcounter" in site.json holds the site code."""
    code = (SITE.get("goatcounter") or "").strip()
    if not code:
        return ""
    return (f'<script data-goatcounter="https://{escape(code)}.goatcounter.com/count" '
            f'async src="//gc.zgo.at/count.js"></script>\n')


def page_head(title: str, lede: str = "", kicker: str = "", extra: str = "", wide: bool = False) -> str:
    k = f'\n      <span class="kicker">{kicker}</span>' if kicker else ""
    l = f'\n      <p class="lede">{lede}</p>' if lede else ""
    cls = "page-head wide" if wide else "page-head"
    return f"""  <div class="{cls}">
    <div class="wrap">{k}
      <h1>{escape(title)}</h1>{l}
      <span class="rule" aria-hidden="true"></span>{extra}
    </div>
  </div>
"""


NOWRAP = ("Skłodowska-Curie", "Suárez-Ibarra", "Aix-en-Provence", "Garidel-Thoron", "Wall-Palmer",
          "HPT-100", "LA-ICP-MS", "ICP-MS", "ICP-OES", "Deep-C", "eCO₂-MorpH", "e-mail")
_NOWRAP_RE = re.compile("|".join(re.escape(x) for x in sorted(NOWRAP, key=len, reverse=True)))
_UNIT_RE = re.compile(r"(\d) (mL|µL|L|m|km|mm|µm|cm|bar|°C|K|%|kg|g|h|min|ans|years|Ma|ka)(?=[\s.,;:)!?/]|$)")
_FR_PUNCT_RE = re.compile(r" ([:;!?»])")
_FR_THOUSANDS_RE = re.compile(r"(\d) (\d{3})(?!\d)")
_SPLIT_RE = re.compile(r"(<[^>]+>)")


def typo(html_doc: str, lang: str) -> str:
    """Small typographic touches on the visible text: no line break between a
    number and its unit, inside hyphenated names ("Aix-en-Provence"), or — in
    French — before : ; ! ? and inside numbers ("5 000")."""
    head, sep, body = html_doc.partition("<body")
    if not sep:
        return html_doc
    out, skip = [], False
    for part in _SPLIT_RE.split(body):
        if part.startswith("<"):
            low = part[:8].lower()
            if low.startswith(("<script", "<style", "<title")):
                skip = True
            elif low.startswith(("</script", "</style", "</title")):
                skip = False
            out.append(part)
            continue
        if skip or not part.strip():
            out.append(part)
            continue
        part = _UNIT_RE.sub("\\1\u00a0\\2", part)
        if lang == "fr":
            part = _FR_PUNCT_RE.sub("\u00a0\\1", part)
            part = _FR_THOUSANDS_RE.sub("\\1\u00a0\\2", part)
        part = _NOWRAP_RE.sub(lambda m: f'<span class="nw">{m.group(0)}</span>', part)
        out.append(part)
    return head + sep + "".join(out)


WRITTEN: set[str] = set()


def write(path: str, depth: int, title: str, description: str, active: str, body: str, **kw) -> None:
    lang = kw.get("lang", "en")
    target = OUT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    page = head(depth, title, description, active, path, **kw) + body + foot(depth, lang)
    target.write_text(typo(page, lang), encoding="utf-8")
    WRITTEN.add(path)
    print(f"  {path}")


def prune() -> None:
    """Delete generated pages whose person, project or news item no longer
    exists in content/, so the site never keeps serving a page for them."""
    for folder in ("people", "projects", "news", "fr"):
        for page in sorted((OUT / folder).glob("*.html")):
            rel_path = f"{folder}/{page.name}"
            if rel_path not in WRITTEN:
                page.unlink()
                print(f"  removed stale {rel_path}")


# --------------------------------------------------------------------------
# shared blocks
# --------------------------------------------------------------------------

def _smooth(points: list[tuple[float, float]]) -> str:
    """A smooth SVG path through the points (Catmull-Rom turned into Béziers)."""
    d = f"M{points[0][0]},{points[0][1]}"
    for i in range(len(points) - 1):
        p0 = points[i - 1] if i else points[i]
        p1, p2 = points[i], points[i + 1]
        p3 = points[i + 2] if i + 2 < len(points) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]},{p2[1]}"
    return d


SEAFLOOR = [(0, 36), (38, 38), (64, 46), (96, 58), (140, 70), (178, 84), (214, 150), (246, 250), (280, 318),
            (330, 352), (400, 362), (480, 366), (560, 362), (640, 358), (712, 364), (756, 374), (792, 424),
            (826, 474), (860, 476), (894, 414), (930, 376), (1000, 370)]


def ocean_svg() -> str:
    """The lab's signature drawing: a cross-section of the ocean from a mangrove
    coast to a deep trench, with the sediment archive below (not to scale)."""
    floor = _smooth(SEAFLOOR)
    water = floor + " L1000,44 L0,44 Z"
    sediment = floor + " L1000,500 L0,500 Z"
    strata = "".join(
        f'<path d="{_smooth([(x, y + off) for x, y in SEAFLOOR])}" fill="none" stroke="rgba(92,64,38,{a})" stroke-width="{w}"/>'
        for off, a, w in ((14, .22, 2), (30, .16, 3), (50, .2, 2), (74, .14, 4), (100, .18, 2), (128, .12, 3)))
    waves = "M0,44 " + " ".join(f"Q{x + 12.5},{40 if (x // 25) % 2 == 0 else 48} {x + 25},44" for x in range(0, 1000, 25))
    rays = "".join(
        f'<path d="M{x0},44 L{x0 + w0},44 L{x1 + w1},{y1} L{x1},{y1} Z" fill="url(#ray)" opacity="{o}"/>'
        for x0, w0, x1, w1, y1, o in ((150, 40, 110, 120, 300, .55), (330, 30, 320, 110, 330, .45),
                                      (560, 45, 600, 140, 340, .5), (760, 30, 790, 110, 300, .4)))
    snow = "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#fff" opacity="{o}"/>' for x, y, r, o in (
        (205, 120, 1.6, .5), (262, 160, 1.2, .4), (318, 205, 1.5, .35), (372, 140, 1.1, .45), (410, 250, 1.6, .3),
        (455, 185, 1.3, .35), (508, 128, 1.7, .5), (546, 230, 1.2, .3), (590, 290, 1.5, .3), (640, 175, 1.3, .4),
        (688, 238, 1.6, .3), (730, 145, 1.2, .45), (775, 205, 1.4, .35), (820, 275, 1.2, .3), (868, 180, 1.5, .35),
        (915, 240, 1.3, .3), (955, 150, 1.6, .4), (500, 310, 1.2, .25), (660, 320, 1.4, .25), (840, 330, 1.2, .25)))
    # plankton near the surface: foraminifera (chambered spheres) and pteropods (coiled shells)
    forams = "".join(
        f'<g transform="translate({x},{y}) scale({s})" opacity=".9"><circle r="5" fill="#f3e6cf"/><circle cx="6" cy="-3" r="4" fill="#efdcbc"/>'
        f'<circle cx="10" cy="3" r="3.2" fill="#f3e6cf"/><circle cx="-1" cy="-1" r="1.4" fill="#d9b98a"/></g>'
        for x, y, s in ((612, 70, 1), (660, 104, .8), (718, 78, .9), (772, 112, 1.1), (826, 70, .8)))
    pteropods = "".join(
        f'<g transform="translate({x},{y}) scale({s})" opacity=".92"><path d="M0,0 c6,-8 16,-6 16,2 c0,7 -9,9 -12,3 c-2,-4 3,-7 6,-4" fill="none" stroke="#fdf3e8" stroke-width="2.4" stroke-linecap="round"/>'
        f'<path d="M14,-2 c6,-8 12,-9 16,-6 M14,2 c7,2 12,6 14,10" stroke="#fdf3e8" stroke-width="1.6" fill="none" stroke-linecap="round" opacity=".8"/></g>'
        for x, y, s in ((690, 128, 1), (744, 58, .8), (800, 94, .75)))
    shells_floor = "".join(f'<ellipse cx="{x}" cy="{y}" rx="{r}" ry="{r * .55}" fill="#fbf4e6" opacity=".85"/>' for x, y, r in (
        (572, 356, 3), (586, 357.5, 2.4), (603, 356.5, 3.2), (621, 355.5, 2.6), (640, 356, 2.2), (656, 357, 2.8)))
    mangroves = "".join(
        f'<g transform="translate({x},37)"><path d="M0,0 L0,-14 M-6,2 Q-3,-6 0,-9 M6,2 Q3,-6 0,-9" stroke="#4c3a24" stroke-width="1.6" fill="none"/>'
        f'<circle cy="-20" r="9" fill="#2f6b3a"/><circle cx="-7" cy="-15" r="6.5" fill="#3d8a4a"/><circle cx="7" cy="-15" r="6.5" fill="#3d8a4a"/></g>'
        for x in (8, 25, 42))
    ship = ('<g transform="translate(445,30)"><path d="M0,10 L52,10 L46,18 L6,18 Z" fill="#f4f6f9"/>'
            '<path d="M14,10 L14,2 L32,2 L32,10 Z" fill="#f4f6f9"/><path d="M20,2 L20,-7" stroke="#f4f6f9" stroke-width="2"/>'
            '<path d="M5,14 L48,14" stroke="#f07e1c" stroke-width="2"/></g>'
            '<path d="M470,48 L470,362" stroke="#fdf3e8" stroke-width="1.2" stroke-dasharray="4 5" opacity=".6"/>')
    core = ('<g><rect x="461" y="366" width="18" height="122" rx="3" fill="#a8885f" stroke="#fdf3e8" stroke-width="1.6"/>'
            + "".join(f'<rect x="462" y="{y}" width="16" height="{h}" fill="{c}"/>' for y, h, c in (
                (374, 9, "#c4a77c"), (389, 6, "#8f704c"), (400, 12, "#d0b68e"), (418, 7, "#94744f"),
                (431, 13, "#c9ae84"), (450, 6, "#8a6a47"), (462, 14, "#c2a378"), (480, 6, "#8f704c")))
            + "</g>")
    zone_labels = "".join(
        f'<text class="zone-label" x="{x}" y="{y}" text-anchor="{a}" fill="{c}" opacity="{o}">{escape(t)}</text>'
        for x, y, a, t, c, o in ((985, 84, "end", "Sunlit surface", "#fff", .9), (985, 196, "end", "Water column", "#fff", .8),
                                 (985, 300, "end", "Deep sea", "#fff", .75), (985, 356, "end", "Seafloor", "#fff", .75),
                                 (18, 488, "start", "Sediment archive", "#3a2a18", .8)))
    return f"""<svg viewBox="0 0 1000 500" role="img" aria-labelledby="ocean-title" xmlns="http://www.w3.org/2000/svg">
  <title id="ocean-title">Cross-section of the ocean, not to scale: a mangrove coast on the left, the sunlit surface with plankton, the water column, the abyssal plain and a deep trench, and layers of sediment below with a sediment core.</title>
  <defs>
    <linearGradient id="water" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#5d9de0"/><stop offset=".16" stop-color="#2f6db5"/><stop offset=".45" stop-color="#1b467f"/>
      <stop offset=".75" stop-color="#0f2a52"/><stop offset="1" stop-color="#0a1a36"/>
    </linearGradient>
    <linearGradient id="sediment" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#d6bd94"/><stop offset=".55" stop-color="#b8996d"/><stop offset="1" stop-color="#8f6f4b"/>
    </linearGradient>
    <linearGradient id="ray" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#fff" stop-opacity=".35"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#e9f1fa"/><stop offset="1" stop-color="#d4e4f5"/>
    </linearGradient>
  </defs>
  <rect width="1000" height="500" fill="url(#sky)"/>
  <path d="{water}" fill="url(#water)"/>
  {rays}
  <path d="{waves}" fill="none" stroke="#e9f1fa" stroke-width="3"/>
  {snow}{forams}{pteropods}
  <path d="{sediment}" fill="url(#sediment)"/>
  <path d="M0,0 L1000,0" stroke="none"/>
  <g clip-path="url(#sedclip)">{strata}</g>
  <clipPath id="sedclip"><path d="{sediment}"/></clipPath>
  <path d="{floor}" fill="none" stroke="#e6d3b0" stroke-width="2"/>
  {shells_floor}{mangroves}{ship}{core}
  {zone_labels}
</svg>"""


def ocean_block(depth: int, legend: bool = True, zones: bool = False) -> str:
    R = SITE.get("research") or {}
    pins = R.get("pins") or []
    links, items = [], []
    for n, pin in enumerate(pins, 1):
        p = PROJECT_BY_SLUG.get(pin["project"])
        if not p:
            continue
        href = rel(depth, f"projects/{p['slug']}.html")
        side = f' {pin["label"]}' if pin.get("label") in ("left", "below", "above") else ""
        links.append(f'<a class="pin{side}" href="{href}" style="left:{pin["x"]}%;top:{pin["y"]}%" aria-label="{escape(p["name"])}: {escape(pin["where"])}">'
                     f'<span class="num" aria-hidden="true">{n}</span><span class="label"><strong>{escape(p["name"])}</strong>'
                     f'<span>{escape(pin["where"])}</span></span></a>')
        items.append(f'<li><span class="num" aria-hidden="true">{n}</span><span><a href="{href}">{escape(p["name"])}</a> — {escape(pin["where"])}</span></li>')
    leg = f'\n      <ol class="ocean-legend">{"".join(items)}</ol>' if legend and items else ""
    zon = ""
    if zones and R.get("zones"):
        zon = '\n      <ul class="ocean-zones">' + "".join(
            f'<li><strong>{escape(z["name"])}</strong>{escape(z["text"])}</li>' for z in R["zones"]) + "</ul>"
    return f"""    <div class="ocean">
      <figure class="ocean-figure">
        {ocean_svg()}
        {''.join(links)}
      </figure>{leg}{zon}
    </div>
"""


def format_authors(names: list[str]) -> str:
    """Author list with the lab's people in bold; long consortium lists are
    cut after 12 names, keeping any team member that came later."""
    def mark(n: str) -> str:
        return f"<strong>{escape(n)}</strong>" if _name_key(n) in TEAM_KEYS else escape(n)
    if len(names) <= 12:
        return ", ".join(mark(n) for n in names)
    shown = [mark(n) for n in names[:12]]
    late = [mark(n) for n in names[12:] if _name_key(n) in TEAM_KEYS]
    tail = " et al." + (f" (incl. {', '.join(late)})" if late else "")
    return ", ".join(shown) + tail


_SAFE_TAGS = re.compile(r"&lt;(/?)(sub|sup|i|em|b|strong|scp)&gt;", re.I)


def safe_title(title: str) -> str:
    """Paper titles come from HAL and may hold <sub>, <i>…: keep those few
    formatting tags, escape everything else."""
    out = _SAFE_TAGS.sub(lambda m: f"<{m.group(1)}{'span' if m.group(2).lower() == 'scp' else m.group(2).lower()}>", escape(title or ""))
    return out


def pub_items() -> list[dict]:
    return (PUBLICATIONS or {}).get("items") or []


def pub_people(it: dict) -> list[str]:
    return sorted({TEAM_KEYS[_name_key(n)] for n in it.get("authors", []) if _name_key(n) in TEAM_KEYS})


def pub_entry(it: dict, with_id: bool = True) -> str:
    journal = f'<em>{escape(it["journal"])}</em>' if it.get("journal") else ""
    if it.get("volume"):
        journal += f' {escape(it["volume"])}'
    links = []
    if it.get("doi"):
        links.append(f'<a href="https://doi.org/{escape(it["doi"])}">DOI</a>')
    if it.get("hal"):
        links.append(f'<a href="https://hal.science/{escape(it["hal"])}">HAL</a>')
    if it.get("pdf"):
        links.append(f'<a href="{escape(it["pdf"])}">PDF</a>')
    year = it.get("year") or ""
    ident = f' id="{escape(it["hal"])}"' if with_id and it.get("hal") else ""
    people = " ".join(pub_people(it))
    return (f'<li{ident} data-people="{escape(people)}">'
            f'<span class="pub-title">{safe_title(it["title"])}</span>'
            f'<span class="pub-authors">{format_authors(it["authors"])}</span>'
            f'<span class="pub-where">{journal}{" · " if journal else ""}{year}{" · " if links else ""}{" · ".join(links)}</span></li>')


def paper_list(depth: int, items: list[dict]) -> str:
    rows = []
    for it in items:
        href = f"https://doi.org/{it['doi']}" if it.get("doi") else f"https://hal.science/{it['hal']}"
        where = escape(it.get("journal") or "")
        rows.append(f"""          <li>
            <a class="p-title" href="{escape(href)}">{safe_title(it['title'])}</a>
            <span class="p-meta">{format_authors(it['authors'])}</span>
            <span class="p-where"><em>{where}</em>{' · ' if where else ''}{it.get('year') or ''}</span>
          </li>""")
    return '        <ul class="paper-list">\n' + "\n".join(rows) + "\n        </ul>"


def newest_papers(n: int) -> list[dict]:
    return sorted(pub_items(), key=lambda x: (x.get("date") or "", x.get("year") or 0), reverse=True)[:n]


def news_entries() -> list[dict]:
    """News items for the lists: the hand-written ones (each with its own page)
    and Bluesky posts tagged #exoceannews, newest first."""
    out = []
    for n in NEWS["items"]:
        first = next((b["text"] for b in n["body"] if b["type"] == "p"), "")
        out.append({"kind": "page", "date": n.get("date", ""), "title": n["headline"], "image": n.get("image"),
                    "alt": n.get("image_alt", ""), "text": excerpt(first, 190), "href": f"news/{n['id']}.html",
                    "position": n.get("thumb_position", "")})
    for p in (BLUESKY or {}).get("news", []):
        img = (p.get("images") or [{}])[0]
        out.append({"kind": "bluesky", "date": p["date"], "title": p["title"], "image": img.get("file"),
                    "alt": img.get("alt", ""), "text": excerpt(p.get("text", ""), 190), "href": p["url"]})
    out.sort(key=lambda x: x["date"], reverse=True)
    return out


def news_card(depth: int, e: dict, lang: str = "en") -> str:
    ui = UI[lang]
    when = month_name(e["date"], lang) if len(e["date"]) == 7 else day_name(e["date"], lang) if e["date"] else ""
    href = rel(depth, e["href"]) if e["kind"] == "page" else e["href"]
    thumb = ""
    if e.get("image"):
        pos = f' style="--pos:{escape(e["position"])}"' if e.get("position") else ""
        thumb = f'<div class="thumb"{pos}>{picture(depth, e["image"], e.get("alt", ""), sizes="(max-width: 700px) 92vw, 540px")}</div>'
    src = f'<span class="source">{escape(ui["on_bluesky"])}</span>' if e["kind"] == "bluesky" else ""
    return f"""          <a class="card news-card" href="{escape(href)}">
            {thumb}
            <div class="body">
              {src}<span class="date">{escape(when)}</span>
              <p class="name">{escape(e['title'])}</p>
              <p class="blurb">{escape(e['text'])}</p>
              <span class="more">{escape(ui['read_more'])} →</span>
            </div>
          </a>"""


def project_card(depth: int, p: dict) -> str:
    done = p.get("completed")
    status = '<span class="status done">Completed</span>' if done else '<span class="status">Running</span>'
    lead = ""
    if p.get("lead"):
        lead = f' · {escape(p["lead"]["label"].replace("Principal Investigator", "PI"))} {escape(p["lead"]["name"])}'
    img = picture(depth, p["card_image"], "", sizes="(max-width: 700px) 92vw, 360px")
    contain = " contain" if p.get("card_contain") else ""
    return f"""          <a class="card" href="{rel(depth, 'projects/' + p['slug'] + '.html')}">
            <div class="thumb{contain}">{img}</div>
            <div class="body">
              {status}
              <p class="name">{escape(p['name'])}</p>
              <p class="blurb">{escape(p['card_text'])}</p>
              <p class="meta-line">{escape(p.get('programme', ''))} · {escape(p.get('years', ''))}{lead}</p>
            </div>
          </a>"""


ICONS = {
    "flask": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 3h6M10 3v6l-5.5 9.5A2 2 0 0 0 6.2 21h11.6a2 2 0 0 0 1.7-2.5L14 9V3"/><path d="M7.5 15h9"/></svg>',
    "data": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><ellipse cx="12" cy="5.5" rx="7.5" ry="2.8"/><path d="M4.5 5.5v6.5c0 1.6 3.4 2.8 7.5 2.8s7.5-1.2 7.5-2.8V5.5"/><path d="M4.5 12v6.5c0 1.6 3.4 2.8 7.5 2.8s7.5-1.2 7.5-2.8V12"/></svg>',
    "people": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="9" cy="8" r="3.2"/><path d="M3 20c.6-3.4 3-5.4 6-5.4s5.4 2 6 5.4"/><circle cx="17" cy="9" r="2.6"/><path d="M15.8 14.6c2.6.1 4.5 1.9 5.2 5.4"/></svg>',
}


# --------------------------------------------------------------------------
# pages
# --------------------------------------------------------------------------

def build_home() -> None:
    h = SITE["home"]
    d = 0
    buttons = "".join(
        f'<a class="btn {"primary" if b.get("primary") else "ghost"}" href="{escape(b["href"])}">{escape(b["label"])}</a>'
        for b in h["hero_buttons"])
    hero_img = picture(d, h["hero_image"], "", sizes="100vw", lazy=False, priority=True)
    founders = "\n".join(
        f'          <li><span class="who">{person_link(d, f["slug"], f["name"])}</span><p>{f["blurb"]}</p></li>'
        for f in h["founders"])
    doors = "\n".join(
        f"""          <a class="tile" href="{escape(x['href'])}">
            <span class="icon">{ICONS[icon]}</span>
            <h3>{escape(x['title'])}</h3>
            <p>{escape(x['text'])}</p>
            <span class="more">{escape(x['cta'])}</span>
          </a>""" for x, icon in zip(h["doors"], ("flask", "data", "people")))
    news = "\n".join(news_card(d, e) for e in news_entries()[:2])
    papers = paper_list(d, newest_papers(3)) if pub_items() else ""
    R = SITE.get("research") or {}
    body = f"""  <section class="hero" aria-labelledby="hero-title">
    <div class="hero-media">{hero_img}</div>
    <div class="wrap hero-inner">
      <span class="kicker">{escape(SITE['tagline'])} · CEREGE</span>
      <h1 id="hero-title">{escape(h['hero_title'])}</h1>
      <p>{escape(h['hero_text'])}</p>
      <div class="btn-row">{buttons}</div>
    </div>
  </section>

  <section class="band" aria-labelledby="column-title">
    <div class="wrap">
      <div class="section-head">
        <h2 id="column-title">{escape(R.get('column_title', 'From surface to seafloor'))}</h2>
        <a class="more" href="projects.html">Our research</a>
      </div>
      <p class="measure">{escape(R.get('column_text', ''))}</p>
{ocean_block(d)}
    </div>
  </section>

  <section class="band alt" aria-labelledby="founders-title">
    <div class="wrap split">
      <figure>
        {picture(d, h['founders_photo'], h['founders_alt'], sizes="(max-width: 900px) 92vw, 560px")}
        <figcaption>{escape(h['founders_caption'])}<span class="credit">{escape(h['founders_credit'])}</span></figcaption>
      </figure>
      <div>
        <h2 id="founders-title" style="margin-top:0">{escape(h['founders_title'])}</h2>
        <p>{escape(h['founders_intro'])}</p>
        <ul class="founders-list">
{founders}
        </ul>
        <div class="btn-row"><a class="btn" href="team.html">Meet the whole team</a></div>
      </div>
    </div>
  </section>

  <section class="band" aria-labelledby="doors-title">
    <div class="wrap">
      <h2 id="doors-title">{escape(h['doors_title'])}</h2>
      <div class="grid three">
{doors}
      </div>
    </div>
  </section>

  <section class="band alt" aria-labelledby="latest-title">
    <div class="wrap">
      <div class="section-head">
        <h2 id="latest-title">{escape(h['latest_title'])}</h2>
        <a class="more" href="news.html">All news</a>
      </div>
      <div class="split">
        <div class="news-cards compact">
{news}
        </div>
        <div>
          <h3 style="margin-top:0">Latest papers</h3>
{papers}
          <p style="margin-top:1rem"><a class="btn" href="publications.html">All publications</a></p>
        </div>
      </div>
    </div>
  </section>

  <section class="band" aria-labelledby="where-title">
    <div class="wrap split media-right">
      <figure>
        {picture(d, h['where_photo'], h['where_alt'], sizes="(max-width: 900px) 92vw, 560px")}
        <figcaption>{escape(h['where_caption'])}<span class="credit">{escape(h['where_credit'])}</span></figcaption>
      </figure>
      <div>
        <h2 id="where-title" style="margin-top:0">{escape(h['where_title'])}</h2>
        {"".join(f"<p>{p}</p>" for p in h["where"])}
        <div class="btn-row"><a class="btn" href="contact.html#visit">How to get here</a><a class="btn" href="{escape(SITE['footer']['cerege_url'])}">CEREGE website</a></div>
      </div>
    </div>
  </section>
"""
    write("index.html", d, SITE["name"], SITE["description"], "index.html", body,
          jsonld=jsonld_org(), body_class="home")


def build_research() -> None:
    d = 0
    R = SITE.get("research") or {}
    current = [p for p in PROJECTS["projects"] if not p.get("completed")]
    done = [p for p in PROJECTS["projects"] if p.get("completed")]
    qs = "".join(f"<li>{q}</li>" for q in R.get("questions", []))
    completed = ""
    if done:
        completed = f"""
      <h2>{escape(R.get('completed_title', 'Completed projects'))}</h2>
      <div class="grid three">
{chr(10).join(project_card(d, p) for p in done)}
      </div>"""
    body = page_head(PROJECTS["title"], escape(PROJECTS["lede"])) + f"""
  <section class="band" aria-labelledby="column-title">
    <div class="wrap">
      <h2 id="column-title">{escape(R.get('column_title', ''))}</h2>
      <p class="measure">{escape(R.get('column_text', ''))}</p>
{ocean_block(d, legend=True, zones=True)}
    </div>
  </section>

  <section class="band alt" aria-labelledby="questions-title">
    <div class="wrap">
      <h2 id="questions-title">{escape(R.get('questions_title', 'Our key questions'))}</h2>
      <ol class="questions">{qs}</ol>
    </div>
  </section>

  <section class="band" aria-labelledby="projects-title">
    <div class="wrap">
      <h2 id="projects-title">{escape(R.get('current_title', 'Current projects'))}</h2>
      <div class="grid three">
{chr(10).join(project_card(d, p) for p in current)}
      </div>{completed}
      <p class="measure" style="margin-top:2.4rem">{R.get('outro', '')}</p>
    </div>
  </section>
"""
    names = ", ".join(p["name"] for p in PROJECTS["projects"])
    write("projects.html", d, PROJECTS["title"],
          f"The research of the exocean laboratory at CEREGE, from surface plankton to deep-sea sediments: {names}.",
          "projects.html", body)
    for p in PROJECTS["projects"]:
        build_project(p)


def _acronym(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def project_outputs(p: dict) -> list[dict]:
    """Papers linked to a project: those HAL tags with the project's acronym
    (from the funding declared on deposit), plus any DOIs listed by hand in
    projects.json under "outputs"."""
    key = _acronym(p["name"])
    manual = {d.lower() for d in p.get("outputs", [])}
    found = [it for it in pub_items()
             if key in {_acronym(a) for a in it.get("projects", [])} or (it.get("doi") or "") in manual]
    return sorted(found, key=lambda x: (x.get("date") or "", x.get("year") or 0), reverse=True)


def build_project(p: dict) -> None:
    d = 1
    names = SITE.get("funders", {})
    parts = []
    if p.get("hero_image"):
        dims = image_size(IMG / img_name(p["hero_image"]))
        natural = f' style="max-width:{dims[0]}px"' if dims and dims[0] < 700 else ""
        parts.append(f"""        <figure{natural}>
          {picture(d, p['hero_image'], p.get('hero_alt') or p['subtitle'], sizes="(max-width: 980px) 92vw, 720px", lazy=False)}
        </figure>""")
    parts += [f"        <p>{fix_links(t, d)}</p>" for t in p["intro"]]
    for s in p["sections"]:
        parts.append(f'        <h2>{escape(s["heading"])}</h2>')
        for key in ("intro", "body"):
            if s.get(key):
                parts.append(f"        <p>{fix_links(s[key], d)}</p>")
        if s.get("items"):
            parts.append(bullets([fix_links(i, d) for i in s["items"]]))
        if s.get("outro"):
            parts.append(f"        <p>{fix_links(s['outro'], d)}</p>")

    outputs = project_outputs(p)
    if outputs:
        parts.append(f"""        <section class="outputs" aria-labelledby="outputs-title">
          <h2 id="outputs-title">Outputs so far</h2>
          <p class="muted small">Papers that declare {escape(p['name'])} funding in the HAL open archive.</p>
{paper_list(d, outputs)}
        </section>""")
    if p.get("note"):
        parts.append(f'        <p class="muted small" style="margin-top:1.6rem">{escape(p["note"])}</p>')

    # -- the facts box --------------------------------------------------------
    def credit(entry: dict) -> str:
        if entry.get("slug"):
            txt = person_link(d, entry["slug"], entry["name"])
        elif entry.get("url"):
            txt = f'<a href="{escape(entry["url"])}">{escape(entry["name"])}</a>'
        else:
            txt = escape(entry["name"])
        return txt

    facts = [f'<div><dt>Status</dt><dd>{"Completed" if p.get("completed") else "Running"}</dd></div>']
    if p.get("programme") or p.get("years"):
        facts.append(f'<div><dt>Funding</dt><dd>{escape(p.get("programme", ""))}{", " if p.get("years") else ""}{escape(p.get("years", ""))}</dd></div>')
    for key in ("lead", "colead"):
        if p.get(key):
            e = p[key]
            mail = f'<br>{email_span(e["email_user"], e["email_domain"])}' if e.get("email_user") else ""
            facts.append(f'<div><dt>{escape(e["label"])}</dt><dd>{credit(e)}{mail}</dd></div>')
    if p.get("participants"):
        facts.append(f'<div><dt>CEREGE team</dt><dd>{", ".join(credit(x) for x in p["participants"])}</dd></div>')
    if p.get("external"):
        facts.append(f'<div><dt>Partners</dt><dd><ul>{"".join(f"<li>{x}</li>" for x in p["external"])}</ul></dd></div>')
    if p.get("former"):
        facts.append(f'<div><dt>Former team members</dt><dd>{escape(", ".join(p["former"]))}</dd></div>')
    if p.get("keywords"):
        facts.append(f'<div><dt>Keywords</dt><dd>{escape(p["keywords"])}</dd></div>')
    if p.get("funders"):
        logos = "".join(picture(d, f, names.get(f, ""), sizes="160px") for f in p["funders"])
        facts.append(f'<div><dt>Funded and hosted by</dt><dd><div class="funders">{logos}</div></dd></div>')

    kicker = escape(" · ".join(x for x in (p.get("programme"), p.get("years")) if x))
    who = ""
    if p.get("lead"):
        who = f'<span>{escape(p["lead"]["label"])}: {person_link(d, p["lead"]["slug"], p["lead"]["name"]) if p["lead"].get("slug") else escape(p["lead"]["name"])}</span>'
    status = "Completed" if p.get("completed") else "Running"
    head_meta = f'\n      <p class="head-meta"><span class="status{" done" if p.get("completed") else ""}">{status}</span>{who}</p>'
    body = page_head(p["name"], escape(p["subtitle"]), kicker=kicker, extra=head_meta) + f"""
  <section class="band">
    <div class="wrap proj-layout">
      <div class="article">
{chr(10).join(parts)}
        <div class="btn-row"><a class="btn primary" href="{rel(d, 'contact.html')}">Contact us about {escape(p['name'])}</a></div>
        <a class="back-link" href="{rel(d, 'projects.html')}">All research projects</a>
      </div>
      <aside class="facts" aria-labelledby="facts-title">
        <h2 id="facts-title">The project</h2>
        <dl>
          {chr(10).join('          ' + f for f in facts).strip()}
        </dl>
      </aside>
    </div>
  </section>
"""
    write(f"projects/{p['slug']}.html", d, p["name"], f"{p['name']}: {p['subtitle']}.", "projects.html", body,
          image=p.get("hero_image") if p.get("hero_image", "").endswith((".jpg", ".png")) else None)


def build_data() -> None:
    """Data & Models page: the models, datasets and tools the lab shares, one
    entry per resource, each with its links grouped by kind."""
    D = SITE.get("data")
    if not D:
        return
    d = 0
    sections = []
    for sec in D.get("sections", []):
        entries = []
        for it in sec["items"]:
            who = ""
            if it.get("people"):
                names = [person_link(d, slug) for slug in it["people"]]
                joined = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
                who = f'\n            <p class="res-who">From the team: {joined}</p>'
            rows = []
            for grp in it.get("links", []):
                pills = "".join(f'<li><a href="{escape(l["url"])}">{escape(l["label"])}</a></li>' for l in grp["items"])
                rows.append(f'              <div class="res-links"><span class="res-kind">{escape(grp["kind"])}</span>'
                            f'<ul class="pills">{pills}</ul></div>')
            links = ("\n            <div class=\"res-link-rows\">\n" + "\n".join(rows) + "\n            </div>") if rows else ""
            sub = f'\n            <p class="res-sub">{escape(it["sub"])}</p>' if it.get("sub") else ""
            entries.append(f"""          <article class="res">
            <h3>{escape(it['name'])}</h3>{sub}
            <p>{it['body']}</p>{who}{links}
          </article>""")
        sections.append(f"""        <h2>{escape(sec['title'])}</h2>
{chr(10).join(entries)}""")

    body = page_head(D["title"], escape(D["lede"])) + f"""
  <section class="band">
    <div class="wrap">
      <div class="measure">
        <p>{D.get('intro', '')}</p>
{chr(10).join(sections)}
        <p style="margin-top:1.6rem">{D.get('outro', '')}</p>
        <div class="btn-row">
          <a class="btn" href="services.html">Services &amp; instruments</a>
          <a class="btn primary" href="contact.html">Contact us</a>
        </div>
      </div>
    </div>
  </section>
"""
    write("data.html", d, D["title"],
          "Models, datasets and tools shared by the exocean laboratory at CEREGE: the RADI sediment model, the FORCIS "
          "planktonic foraminifera census, the Cenozoic CO2 synthesis and micro-CT images of foraminifera.",
          "data.html", body)


REDIRECTS = {"expertise.html": "services.html"}   # retired pages -> where their content went


def build_redirects() -> None:
    """Keep old addresses working (bookmarks, search engines, other sites): each
    retired page becomes a tiny page that forwards to its replacement."""
    for old, new in REDIRECTS.items():
        target = rel(0, new)
        canon = f'<link rel="canonical" href="{escape(absurl(new))}">\n' if BASE else ""
        (OUT / old).write_text(f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{escape(SITE['name'])} — moved</title>
<meta name="robots" content="noindex">
{canon}<meta http-equiv="refresh" content="0; url={escape(target)}">
</head>
<body>
<p>This page has moved: <a href="{escape(target)}">{escape(absurl(new) if BASE else new)}</a>.</p>
</body>
</html>
""", encoding="utf-8")
        print(f"  {old} -> {new}")


# -- services (English and French) ------------------------------------------

def services_block(lang: str) -> dict:
    return SITE.get("services") if lang == "en" else (FR.get("services") or {})


SVC_UI = {
    "en": {"jump": "On this page", "platforms": "Other CEREGE platforms", "here": "exocean’s centre",
           "data_btn": "Data & models we share", "contact_btn": "Contact us", "centres_label": "CEREGE technical centres",
           "inst_label": "Instruments", "desc": "Analyses and experiments the exocean laboratory at CEREGE runs for academic and private partners — carbonate chemistry, nutrients, microsensor profiling, cultures, high-pressure incubations — and its instruments."},
    "fr": {"jump": "Sur cette page", "platforms": "Autres plateformes du CEREGE", "here": "Le pôle d’exocean",
           "data_btn": "Données et modèles partagés", "contact_btn": "Nous contacter", "centres_label": "Pôles techniques du CEREGE",
           "inst_label": "Instruments", "desc": "Analyses et expériences que le laboratoire exocean du CEREGE réalise pour des partenaires académiques et privés — chimie des carbonates, nutriments, profils par microcapteurs, cultures, incubations à haute pression — et ses instruments."},
}


def cerege_block(c: dict | None, lang: str, depth: int) -> str:
    if not c:
        return ""
    ui = SVC_UI[lang]
    body = "\n".join(f"        <p>{fix_links(t, depth, lang)}</p>" for t in c.get("body", []))
    tiles = []
    for ctr in c.get("centres", []):
        here = ctr.get("here")
        labs = " · ".join(f"<strong>{escape(l)}</strong>" if l == here else escape(l) for l in ctr["labs"])
        cls = "centre here" if here else "centre"
        tag = f'<span class="centre-tag">{escape(ui["here"])}</span>' if here else ""
        tiles.append(f'          <li class="{cls}">{tag}<span class="centre-name">{escape(ctr["name"])}</span>'
                     f'<span class="centre-labs">{labs}</span></li>')
    plats = []
    for pf in c.get("platforms", []):
        plats.append(f"""            <li class="svc">
              <h3>{escape(pf['what'])} · <a href="{escape(pf['url'])}">{escape(pf['name'])}</a></h3>
              <p>{pf['desc']}</p>
            </li>""")
    platforms = ""
    if plats:
        platforms = f"""
      <h2 id="platforms">{escape(c.get('platforms_title', ui['platforms']))}</h2>
      <p class="measure">{escape(c.get('platforms_intro', ''))}</p>
      <ul class="svc-list platforms">
{chr(10).join(plats)}
      </ul>"""
    return f"""
  <section class="band alt" aria-labelledby="cerege">
    <div class="wrap">
      <h2 id="cerege">{escape(c['title'])}</h2>
      <div class="measure">
{body}
      </div>
      <ul class="centres" aria-label="{escape(ui['centres_label'])}">
{chr(10).join(tiles)}
      </ul>
{platforms}
    </div>
  </section>
"""


def build_services(lang: str = "en") -> None:
    """Services & Instruments: how a request works, the services in themes, the
    instruments by type, and where exocean sits within CEREGE. Prices, purchase
    dates and funding sources are deliberately never published here."""
    s = services_block(lang)
    if not s:
        return
    ui = SVC_UI[lang]
    path = "services.html" if lang == "en" else "fr/services.html"
    d = 0 if lang == "en" else 1
    instruments = {i["id"]: i for g in s.get("groups", []) for i in g["items"] if i.get("id")}

    def pill(ref: str) -> str:
        inst = instruments.get(ref)
        if not inst:                      # a typo in the content must not break the build
            print(f"  warning: services ({lang}) kit names unknown instrument '{ref}'")
            return f"<li><span>{escape(ref)}</span></li>"
        return f'<li><a href="#i-{escape(ref)}">{escape(inst.get("short") or inst["name"])}</a></li>'

    hero = ""
    if s.get("hero"):
        credit = f'<span class="credit">{escape(s["hero_credit"])}</span>' if s.get("hero_credit") else ""
        hero = f"""      <figure>
        {picture(d, s['hero'], s.get('hero_alt', ''), sizes="(max-width: 900px) 92vw, 560px", lazy=False)}
        <figcaption>{escape(s.get('hero_caption', ''))}{credit}</figcaption>
      </figure>"""
    intro = "\n".join(f"        <p>{fix_links(p, d, lang)}</p>" for p in s.get("intro", []))
    sheet = ""
    if s.get("sheet") and (OUT / "assets" / s["sheet"]["file"]).exists():
        sheet = f'\n        <p><a class="sheet-link" href="{rel(d, "assets/" + s["sheet"]["file"])}">↓ {escape(s["sheet"]["label"])}</a></p>'

    steps = "".join(f"<li><h3>{escape(st['title'])}</h3><p>{fix_links(fill(st['text']), d, lang)}</p></li>" for st in s.get("how", []))
    how = f"""
  <section class="band alt" aria-labelledby="how">
    <div class="wrap">
      <h2 id="how">{escape(s.get('how_title', 'How it works'))}</h2>
      <ol class="steps">{steps}</ol>
    </div>
  </section>
""" if steps else ""

    theme_html = []
    for t in s.get("themes", []):
        items = []
        for o in t["offers"]:
            kit = o.get("kit") or []
            pills = (f'\n              <ul class="pills" aria-label="{escape(ui["inst_label"])}">{"".join(pill(k) for k in kit)}</ul>'
                     if kit else "")
            note = f'\n              <p class="svc-note">{fix_links(o["note"], d, lang)}</p>' if o.get("note") else ""
            items.append(f"""            <li class="svc">
              <h4>{escape(o['title'])}</h4>
              <p>{fix_links(o['body'], d, lang)}</p>{note}{pills}
            </li>""")
        theme_html.append(f"""      <section class="theme">
        <h3>{escape(t['title'])}</h3>
        <ul class="svc-list">
{chr(10).join(items)}
        </ul>
      </section>""")

    groups = []
    for g in s.get("groups", []):
        rows = "\n".join(
            f"""            <div class="inst"{f' id="i-{escape(i["id"])}"' if i.get("id") else ""}><dt>{escape(i['name'])}</dt><dd>{fix_links(i['desc'], d, lang)}</dd></div>"""
            for i in g["items"])
        note = f'\n        <p class="note">{fix_links(g["note"], d, lang)}</p>' if g.get("note") else ""
        cls = "inst-group reserved" if g.get("reserved") else "inst-group"
        groups.append(f"""      <section class="{cls}">
        <h3>{escape(g['heading'])}</h3>{note}
        <dl class="inst-list">
{rows}
        </dl>
      </section>""")

    visit = ""
    if s.get("visit"):
        visit = f"""
      <h2 id="visit">{escape(s.get('visit_title', 'Planning a visit'))}</h2>
      <div class="measure">
        {"".join(f"<p>{fix_links(p, d, lang)}</p>" for p in s["visit"])}
      </div>"""

    jump = [f'<a href="#how">{escape(s.get("how_title", "How it works"))}</a>' if steps else "",
            f'<a href="#offers">{escape(s["offers_title"])}</a>',
            f'<a href="#instruments">{escape(s["instruments_title"])}</a>',
            f'<a href="#visit">{escape(s.get("visit_title", ""))}</a>' if s.get("visit") else "",
            f'<a href="#platforms">{escape(ui["platforms"])}</a>' if s.get("cerege", {}).get("platforms") else ""]
    jump_html = f'<nav class="jump" aria-label="{escape(ui["jump"])}">{"".join(j for j in jump if j)}</nav>'

    contact_href = "contact.html" if lang == "fr" else "contact.html"
    body = page_head(s["title"], escape(s["lede"]), extra="\n      " + jump_html) + f"""
  <section class="band">
    <div class="wrap split">
      <div>
{intro}{sheet}
      </div>
{hero}
    </div>
  </section>
{how}
  <section class="band" aria-labelledby="offers">
    <div class="wrap">
      <h2 id="offers">{escape(s['offers_title'])}</h2>
{chr(10).join(theme_html)}
    </div>
  </section>

  <section class="band alt" aria-labelledby="instruments">
    <div class="wrap">
      <h2 id="instruments">{escape(s['instruments_title'])}</h2>
      <p class="measure">{escape(s.get('instruments_intro', ''))}</p>
{chr(10).join(groups)}
    </div>
  </section>

  <section class="band">
    <div class="wrap">{visit}
    </div>
  </section>
{cerege_block(s.get('cerege'), lang, d)}
  <section class="band tight">
    <div class="wrap"><div class="btn-row" style="margin-top:0">
      <a class="btn primary" href="{contact_href if lang == 'fr' else rel(d, 'contact.html')}">{escape(ui['contact_btn'])}</a>
      <a class="btn" href="{rel(d, 'data.html')}">{escape(ui['data_btn'])}</a>
    </div></div>
  </section>
"""
    alt = "fr/services.html" if lang == "en" else "services.html"
    if lang == "fr" and not FR.get("services"):
        alt = None
    write(path, d, s["title"], ui["desc"], "services.html", body, lang=lang,
          alt_path=alt if (lang == "fr" or FR.get("services")) else None)


def build_capabilities() -> None:
    """A one-page, print-ready summary of the services (A4), from the same
    content as the Services page. The GitHub Action prints it to
    assets/exocean-services.pdf."""
    s = SITE.get("services")
    if not s:
        return
    instruments = [i for g in s.get("groups", []) if not g.get("reserved") for i in g["items"]]
    themes = "".join(
        f'<section><h2>{escape(t["title"])}</h2>' + "".join(
            f'<p><strong>{escape(o["title"])}.</strong> {plain(o["body"])}</p>' for o in t["offers"]) + "</section>"
        for t in s.get("themes", []))
    inst = " · ".join(escape(i["name"]) for i in instruments)
    plats = ", ".join(f'{escape(p["name"])} ({escape(p["what"][0].lower() + p["what"][1:])})' for p in s.get("cerege", {}).get("platforms", []))
    url = absurl("services.html") if BASE else "services.html"
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>exocean — analyses and experiments for partners</title>
<meta name="robots" content="noindex">
<style>
@font-face {{ font-family: Cabin; font-weight: 400 700; src: url("assets/fonts/cabin-latin.woff2") format("woff2"); }}
@page {{ size: A4; margin: 13mm 14mm 12mm; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: Cabin, system-ui, sans-serif; color: #1f2124; font-size: 10.2pt; line-height: 1.45; }}
.top {{ display: grid; grid-template-columns: 1.15fr 1fr; gap: 16px; align-items: center; margin-bottom: 12px; }}
.top img {{ width: 100%; border-radius: 6px; display: block; }}
.top p {{ font-size: 11pt; }}
header {{ display: flex; align-items: center; gap: 14px; border-bottom: 3px solid #f07e1c; padding-bottom: 8px; margin-bottom: 10px; }}
header img {{ height: 44px; }}
header h1 {{ font-size: 15pt; margin: 0; line-height: 1.15; }}
header p {{ margin: 2px 0 0; color: #4a4f57; }}
.cols {{ columns: 2; column-gap: 18px; }}
section {{ break-inside: avoid; margin-bottom: 6px; }}
h2 {{ font-size: 9.5pt; text-transform: uppercase; letter-spacing: .06em; color: #c9640c; margin: 0 0 4px; }}
p {{ margin: 0 0 5px; }}
.box {{ break-inside: avoid; background: #fdf3e8; border-left: 3px solid #f07e1c; padding: 7px 9px; margin: 8px 0; }}
footer {{ margin-top: 8px; border-top: 1px solid #e3e5e8; padding-top: 6px; color: #4a4f57; font-size: 8.6pt; display: flex; justify-content: space-between; }}
</style>
</head>
<body>
<header>
  <img src="assets/img/logo-stacked.svg" alt="exocean">
  <div><h1>Analyses and experiments for partners</h1>
  <p>{escape(SITE['tagline'])} · CEREGE, Aix-en-Provence, France</p></div>
</header>
<div class="top"><p>{plain(s['intro'][0])}</p><img src="assets/img/{escape(s.get('hero', 'news-julie.jpg'))}" alt=""></div>
<div class="cols">
{themes}
<section><h2>Instruments</h2><p>{inst}</p></section>
<section><h2>Other CEREGE platforms</h2><p>A visit can be combined with {plats}.</p></section>
</div>
<div class="box"><strong>How to ask:</strong> write to {escape(SITE['email'])} with a few lines on your samples (type, number, volume) and what you need. We reply with what is feasible, how to prepare your samples and how long it will take — with a quote for paid services. Visitors pay a small lab occupation fee.</div>
<footer><span>{escape(url)}</span><span>{escape(SITE['email'])}</span></footer>
</body>
</html>
"""
    (OUT / "capabilities.html").write_text(html, encoding="utf-8")
    WRITTEN.add("capabilities.html")
    print("  capabilities.html")


# -- people -----------------------------------------------------------------

def collaborators_block(depth: int, g: dict) -> str:
    """Collaborators from outside CEREGE, as a compact list grouped by project:
    no photos and no pages of their own; each institution links to its website.
    They are kept out of TEAM_KEYS, so they are not bolded on the Publications page."""
    parts = []
    for sub in g["external"]:
        label = escape(sub["label"])
        if sub.get("project"):
            label = f'<a href="{rel(depth, "projects/" + sub["project"] + ".html")}">{label}</a>'
        items = []
        for p in sub["people"]:
            insts = " &amp; ".join(
                f'<a href="{escape(i["url"])}">{escape(i["name"])}</a>' if i.get("url") else escape(i["name"])
                for i in p.get("institutions", []))
            where = ", ".join(x for x in (insts, escape(p.get("country", ""))) if x)
            role = f'<span class="crole">{escape(p["role"])}</span>' if p.get("role") else ""
            items.append(f'              <li><span class="cname">{escape(p["name"])}</span>{role}'
                         f'<span class="cinst">{where}</span></li>')
        parts.append(f"""          <div class="collab-proj">
            <h3>{label}</h3>
            <ul class="collab-list">
{chr(10).join(items)}
            </ul>
          </div>""")
    return f"""        <section class="team-group collab">
          <h2>{escape(g['heading'])}</h2>
{chr(10).join(parts)}
        </section>"""


def avatar(depth: int, m: dict, sizes: str, lazy: bool = True) -> str:
    if m.get("photo"):
        return f'<div class="avatar">{picture(depth, m["photo"], m["name"], sizes=sizes, lazy=lazy)}</div>'
    return f'<div class="avatar placeholder" aria-hidden="true">{escape(initials(m["name"]))}</div>'


def build_team() -> None:
    d = 0
    groups = []
    first = True                        # the first row of photos is visible at once: load it eagerly
    for g in TEAM["groups"]:
        if g.get("external"):
            groups.append(collaborators_block(d, g))
            continue
        if not g.get("members"):        # e.g. "Former members" while still empty
            continue
        cards = []
        eager, first = first, False
        for m in g["members"]:
            role = f' · <span class="prole">{escape(m["role"])}</span>' if m.get("role") else ""
            focus = f'<span class="focus">{escape(m["focus"])}</span>' if m.get("focus") else ""
            inner = f"""{avatar(d, m, "(max-width: 480px) 46vw, 220px", lazy=not eager)}
              <span class="pname">{escape(m['name'])}</span>
              <span class="position">{escape(m.get('position') or m['affiliation'])}{role}</span>
              {focus}"""
            if m.get("bio"):
                cards.append(f'            <a class="person" href="people/{m["slug"]}.html">\n              {inner}\n            </a>')
            else:
                cards.append(f'            <div class="person">\n              {inner}\n            </div>')
        groups.append(f"""        <section class="team-group">
          <h2>{escape(g['heading'])}</h2>
          <div class="people">
{chr(10).join(cards)}
          </div>
        </section>""")

    body = page_head(TEAM["title"], escape(TEAM["lede"])) + f"""
  <section class="band">
    <div class="wrap">
{chr(10).join(groups)}
    </div>
  </section>
  <section class="band alt tight">
    <div class="wrap">
      <h2 style="margin-top:0">Want to work with us?</h2>
      <p class="measure">Internships, PhD and postdoctoral positions, fellowships and visits: see how to join the lab.</p>
      <div class="btn-row"><a class="btn primary" href="join.html">Join us</a><a class="btn" href="contact.html">Contact</a></div>
    </div>
  </section>
"""
    write("team.html", d, TEAM["title"],
          "The founders, scientific team and collaborators of the exocean laboratory at CEREGE, Aix-en-Provence.",
          "team.html", body)

    for g in TEAM["groups"]:
        for m in g.get("members", []):
            if m.get("bio"):
                build_person(m)


def member_projects(slug: str) -> list[dict]:
    out = []
    for p in PROJECTS["projects"]:
        roles = [p.get("lead"), p.get("colead")] + list(p.get("participants") or [])
        if any(r and r.get("slug") == slug for r in roles):
            out.append(p)
    return out


def member_papers(m: dict, n: int = 5) -> list[dict]:
    key = _name_key(m["name"])
    mine = [it for it in pub_items() if any(_name_key(a) == key for a in it.get("authors", []))]
    return sorted(mine, key=lambda x: (x.get("date") or "", x.get("year") or 0), reverse=True)[:n]


def build_person(m: dict) -> None:
    d = 1
    role = f' · <span class="prole">{escape(m["role"])}</span>' if m.get("role") else ""
    greeting = f'<p class="greeting">{escape(m["greeting"])}</p>' if m.get("greeting") else ""
    paras = "\n".join(f"        <p>{escape(t)}</p>" for t in m["bio"])
    contact = ""
    if m.get("email_user"):
        contact = f'        <p>You can contact me directly at {email_span(m["email_user"], m["email_domain"])}.</p>'
    link_list = list(m.get("links") or [])
    if m.get("idhal"):
        link_list.insert(0, {"label": "Publications (HAL)",
                             "url": f"https://hal.science/search/index/?q=*&authIdHal_s={m['idhal']}"})
    if m.get("orcid"):
        link_list.insert(0, {"label": f"ORCID {m['orcid']}", "url": f"https://orcid.org/{m['orcid']}"})
    links = ""
    if link_list:
        items = "".join(f'<li><a href="{escape(l["url"])}">{escape(l["label"])}</a></li>' for l in link_list)
        links = f'        <div class="side-block"><h2>Find more about my work</h2><ul class="links-list">{items}</ul></div>'
    projs = member_projects(m["slug"])
    projects = ""
    if projs:
        chips = "".join(f'<li><a href="{rel(d, "projects/" + p["slug"] + ".html")}">{escape(p["name"])}</a></li>' for p in projs)
        projects = f'        <div class="side-block"><h2>Projects</h2><ul class="links-list">{chips}</ul></div>'
    papers = member_papers(m)
    recent = ""
    if papers:
        recent = f"""        <div class="side-block">
          <h2>Recent papers</h2>
{paper_list(d, papers)}
          <p style="margin-top:.8rem"><a href="{rel(d, 'publications.html')}">All the lab's publications</a></p>
        </div>"""
    focus = f'<p class="focus">{escape(m["focus"])}</p>' if m.get("focus") else ""
    head_html = f"""  <div class="page-head">
    <div class="wrap bio-head">
      {avatar(d, m, "200px", lazy=False)}
      <div>
        <h1>{escape(m['name'])}</h1>
        <p class="position">{escape(m.get('position') or m['affiliation'])}{role}</p>
        {focus}
      </div>
    </div>
  </div>
"""
    body = head_html + f"""
  <section class="band">
    <div class="wrap">
      <div class="measure">
{greeting}
{paras}
{contact}
{projects}
{links}
{recent}
        <a class="back-link" href="{rel(d, 'team.html')}">All people</a>
      </div>
    </div>
  </section>
"""
    write(f"people/{m['slug']}.html", d, m["name"],
          f"{m['name']} — {m['affiliation']}. Member of the exocean laboratory at CEREGE.",
          "team.html", body, image=m.get("photo") if (m.get("photo") or "").endswith((".jpg", ".png")) else None)


# -- publications -------------------------------------------------------------

def build_publications() -> None:
    d = 0
    P = SITE.get("publications") or {}
    items = pub_items()
    idhal_people = [m for m in ALL_MEMBERS.values() if m.get("idhal")]
    who = ", ".join(person_link(d, m["slug"], m["name"]) for m in idhal_people) or "the team"
    by_doi = {(it.get("doi") or "").lower(): it for it in items if it.get("doi")}

    selected = ""
    picks = [by_doi[x.lower()] for x in P.get("selected", []) if x.lower() in by_doi]
    missing = [x for x in P.get("selected", []) if x.lower() not in by_doi]
    for x in missing:
        print(f"  warning: selected paper {x} is not in publications.json")
    if picks:
        selected = f"""
  <section class="band alt selected" aria-labelledby="selected-title">
    <div class="wrap">
      <h2 id="selected-title">{escape(P.get('selected_title', 'Selected papers'))}</h2>
      <ol class="pubs">
{chr(10).join('        ' + pub_entry(it, with_id=False) for it in picks)}
      </ol>
    </div>
  </section>
"""
    if not items:
        listing = ('        <p>The publication list could not be generated yet — it is built automatically '
                   'from <a href="https://hal.science">HAL</a> and will appear after the next refresh.</p>')
        tools = ""
    else:
        by_year: dict[int, list[dict]] = {}
        for it in items:
            by_year.setdefault(it.get("year") or 0, []).append(it)
        years = sorted(by_year, reverse=True)
        open_years = set(years[:P.get("open_years", 3)])
        sections = []
        for year in years:
            entries = "\n".join("            " + pub_entry(it) for it in by_year[year])
            label = str(year) if year else "Undated"
            if year in open_years:
                sections.append(f"""        <section class="pub-year">
          <h2 id="y{label}">{label} <span class="pub-count" data-total="{len(by_year[year])}">{len(by_year[year])}</span></h2>
          <ol class="pubs">
{entries}
          </ol>
        </section>""")
            else:
                sections.append(f"""        <details class="pub-year" id="y{label}">
          <summary>{label} <span class="pub-count" data-total="{len(by_year[year])}">{len(by_year[year])}</span></summary>
          <ol class="pubs">
{entries}
          </ol>
        </details>""")
        listing = "\n".join(sections)
        counts = {}
        for it in items:
            for slug in pub_people(it):
                counts[slug] = counts.get(slug, 0) + 1
        people = [s for s in ALL_MEMBERS if counts.get(s)]
        chips = ['<button type="button" class="chip" data-person="" aria-pressed="true">Everyone</button>'] + [
            f'<button type="button" class="chip" data-person="{escape(s)}" aria-pressed="false">{escape(ALL_MEMBERS[s]["name"])}</button>'
            for s in people]
        tools = f"""        <div class="pub-tools" id="pub-tools" hidden>
          <label for="pub-search">Search the list</label>
          <input class="pub-search" id="pub-search" type="search" placeholder="Title, author, journal…" autocomplete="off">
          <div class="chips" role="group" aria-label="Show the papers of">{''.join(chips)}</div>
          <p class="pub-status" id="pub-status" aria-live="polite"></p>
        </div>"""

    updated = (PUBLICATIONS or {}).get("updated", "")
    count = (PUBLICATIONS or {}).get("count", len(items))
    jump = (f'\n      <nav class="jump" aria-label="On this page"><a href="#selected-title">{escape(P.get("selected_title", "Selected papers"))}</a>'
            f'<a href="#all-title">Search all {len(items)} publications</a></nav>') if items else ""
    body = page_head(P.get("title", "Publications"), escape(P.get("lede", "")), extra=jump) + selected + f"""
  <section class="band" aria-labelledby="all-title">
    <div class="wrap">
      <div class="measure" id="pub-all">
        <h2 id="all-title" style="margin-top:0">{escape(P.get('all_title', 'All publications'))}</h2>
        <p class="small muted">Drawn automatically every week from <a href="https://hal.science">HAL</a>, the French national open archive, for {who} — names of team members are in bold, and open-access PDFs are linked whenever HAL holds one.{f' {count} publications, last refreshed {escape(updated)}.' if updated else ''}</p>
{tools}
{listing}
      </div>
    </div>
  </section>
"""
    write("publications.html", d, P.get("title", "Publications"),
          "Peer-reviewed publications of the exocean laboratory at CEREGE, drawn automatically from the HAL open archive.",
          "publications.html", body)


# -- news ---------------------------------------------------------------------

def bluesky_strip(depth: int) -> str:
    """'Latest from Bluesky' — the lab's own recent posts, refreshed weekly by
    fetch_bluesky.py. Silently absent if content/bluesky.json is missing."""
    posts = (BLUESKY or {}).get("posts") or []
    if not posts:
        return ""
    cards = []
    for post in posts[:3]:
        extra = ""
        if post.get("quote"):
            q = post["quote"]
            snippet = q["text"] if len(q["text"]) <= 140 else q["text"][:139].rstrip() + "…"
            extra += (f'<p class="bsky-quote"><a href="{escape(q["url"])}">@{escape(q["handle"])}</a>'
                      f' — {escape(snippet)}</p>')
        if post.get("link_url"):
            extra += f'<p class="bsky-link"><a href="{escape(post["link_url"])}">{escape(post["link_title"])}</a></p>'
        elif post.get("images"):
            n = post["images"]
            extra += f'<p class="bsky-link"><a href="{escape(post["url"])}">{n} photo{"s" if n > 1 else ""} on Bluesky</a></p>'
        cards.append(f"""          <article class="bsky-post">
            <p class="bsky-date"><a href="{escape(post['url'])}"><time datetime="{escape(post['date'])}">{day_name(post['date'])}</time></a></p>
            <p class="bsky-text">{post['html']}</p>
            {extra}
          </article>""")
    handle = escape((BLUESKY or {}).get("handle", ""))
    return f"""  <section class="band alt" aria-labelledby="bsky-title">
    <div class="wrap">
      <div class="section-head">
        <h2 id="bsky-title">Latest from Bluesky</h2>
        <a class="more" href="{escape(SITE['bluesky'])}">Follow @{handle}</a>
      </div>
      <div class="bsky-grid">
{chr(10).join(cards)}
      </div>
    </div>
  </section>
"""


def build_news() -> None:
    d = 0
    cards = "\n".join(news_card(d, e) for e in news_entries())
    media = NEWS["media"]
    groups = []
    for g in media["groups"]:
        lis = "".join(f'<li><a href="{escape(l["url"])}">{escape(l["label"])}</a></li>' for l in g["links"])
        groups.append(f"""          <div class="media-group">
            <h3>{escape(g['heading'])}</h3>
            <ul class="media-links">{lis}</ul>
          </div>""")
    body = page_head(NEWS["title"], escape(NEWS["lede"])) + f"""
  <section class="band" aria-labelledby="list-title">
    <div class="wrap">
      <h2 id="list-title" style="margin-top:0">{escape(NEWS.get('list_title', 'Highlights'))}</h2>
      <div class="news-cards">
{cards}
      </div>
    </div>
  </section>
{bluesky_strip(d)}
  <section class="band" aria-labelledby="media-title">
    <div class="wrap">
      <h2 id="media-title">{escape(media['title'])}</h2>
      <div class="split">
        <div class="media-groups">
{chr(10).join(groups)}
        </div>
        <figure>
          {picture(d, media['image'], media.get('image_alt', 'A pteropod, a planktonic snail with an aragonite shell'), sizes="(max-width: 900px) 92vw, 520px")}
          <figcaption>{escape(media['image_caption'])}</figcaption>
        </figure>
      </div>
    </div>
  </section>
"""
    write("news.html", d, NEWS["title"],
          "Awards, fellowships, reports and media coverage from the exocean laboratory at CEREGE.",
          "news.html", body)
    for n in NEWS["items"]:
        build_news_item(n)


def build_news_item(n: dict) -> None:
    d = 1
    blocks = []
    for b in n["body"]:
        text = fix_links(b["text"], d)
        if b["type"] == "q":
            blocks.append(f'        <p class="qa">{escape(b["text"])}</p>')
        elif b["type"] == "callout":
            blocks.append(f'        <div class="callout"><p>{text}</p></div>')
        else:
            blocks.append(f"        <p>{text}</p>")
    rm = ""
    if n.get("readmore"):
        lis = "".join(f'<li><a href="{escape(l["url"])}">{escape(l["label"])}</a></li>' for l in n["readmore"])
        rm = f"""        <div class="readmore">
          <p class="rm-label">{escape(n['readmore_label'])}</p>
          <ul>{lis}</ul>
        </div>"""
    when = month_name(n.get("date", ""))
    figure = ""
    if n.get("image"):
        figure = f"""        <figure>
          {picture(d, n['image'], n.get('image_alt', ''), sizes="(max-width: 780px) 92vw, 720px", lazy=False)}
          <figcaption>{fix_links(n['image_caption'], d)}<span class="credit">{escape(n.get('image_credit', ''))}</span></figcaption>
        </figure>"""
    others = [e for e in news_entries() if e["href"] != f"news/{n['id']}.html"][:3]
    more = ""
    if others:
        more = f"""
  <section class="band alt" aria-labelledby="more-news">
    <div class="wrap">
      <div class="section-head"><h2 id="more-news">More news</h2><a class="more" href="{rel(d, 'news.html')}">All news</a></div>
      <div class="news-cards">
{chr(10).join(news_card(d, e) for e in others)}
      </div>
    </div>
  </section>
"""
    body = page_head(n["headline"], "", kicker=f'<time datetime="{escape(n.get("date", ""))}">{escape(when)}</time>') + f"""
  <section class="band">
    <div class="wrap">
      <article class="article">
{figure}
{chr(10).join(blocks)}
{rm}
        <a class="back-link" href="{rel(d, 'news.html')}">All news</a>
      </article>
    </div>
  </section>
{more}"""
    first = next((b["text"] for b in n["body"] if b["type"] == "p"), n["headline"])
    write(f"news/{n['id']}.html", d, n["headline"], excerpt(first, 180), "news.html", body,
          image=n.get("image") if (n.get("image") or "").endswith((".jpg", ".png")) else None)


# -- join, contact, legal (English and French) ---------------------------------

def join_block(lang: str) -> dict:
    return SITE.get("join") if lang == "en" else (FR.get("join") or {})


def build_join(lang: str = "en") -> None:
    j = join_block(lang)
    if not j:
        return
    d = 0 if lang == "en" else 1
    path = "join.html" if lang == "en" else "fr/join.html"
    openings = ""
    for o in (j.get("openings") or (SITE.get("join") or {}).get("openings") or []):
        meta = " · ".join(x for x in (o.get("type"), o.get("start"), o.get("deadline")) if x)
        link = f' <a href="{escape(o["url"])}">{escape(o.get("link_label", "Details"))}</a>' if o.get("url") else ""
        openings += f"""        <article class="opening">
          <h3>{escape(o['title'])}</h3>
          <p class="meta-line">{escape(meta)}</p>
          <p>{fix_links(fill(o.get('body', '')), d, lang)}{link}</p>
        </article>
"""
    if not openings:
        openings = f'        <p class="notice">{fix_links(j.get("no_openings", ""), d, lang)}</p>\n'
    items = "\n".join(f"""        <article class="join-item">
          <h3>{escape(i['title'])}</h3>
          <p>{fix_links(fill(i['body']), d, lang)}</p>
        </article>""" for i in j["items"])
    body = page_head(j["title"], escape(j["lede"])) + f"""
  <section class="band" aria-labelledby="open-title">
    <div class="wrap"><div class="measure">
      <h2 id="open-title" style="margin-top:0">{escape(j.get('openings_title', 'Open positions'))}</h2>
{openings}
{items}
    </div></div>
  </section>
  <section class="band alt" aria-labelledby="apply-title">
    <div class="wrap split">
      <div>
        <h2 id="apply-title" style="margin-top:0">{escape(j.get('apply_title', 'How to apply'))}</h2>
        <p>{fix_links(fill(j.get('apply', '')), d, lang)}</p>
      </div>
      <div>
        <h2 style="margin-top:0">{escape(j.get('life_title', ''))}</h2>
        <p>{fix_links(fill(j.get('life', '')), d, lang)}</p>
      </div>
    </div>
  </section>
"""
    desc = plain(j["lede"])
    write(path, d, j["title"], desc, "join.html", body, lang=lang,
          alt_path=("fr/join.html" if lang == "en" else "join.html") if FR.get("join") else None)


def contact_block(lang: str) -> dict:
    return SITE.get("contact") if lang == "en" else (FR.get("contact") or {})


def build_contact(lang: str = "en") -> None:
    c = contact_block(lang)
    if not c:
        return
    d = 0 if lang == "en" else 1
    path = "contact.html" if lang == "en" else "fr/contact.html"
    geo = SITE.get("geo") or {}
    lat, lon = geo.get("lat"), geo.get("lon")
    maps = ""
    if lat and lon:
        maps = (f'<div class="map-links"><a class="btn" href="https://www.openstreetmap.org/?mlat={lat}&amp;mlon={lon}#map=15/{lat}/{lon}">OpenStreetMap</a>'
                f'<a class="btn" href="https://www.google.com/maps/search/?api=1&amp;query={lat}%2C{lon}">Google Maps</a></div>')
    visit_addr = "<br>".join(escape(x) for x in SITE.get("visit_address", []))
    post_addr = "<br>".join(escape(x) for x in SITE["address"])
    rows = []
    for t in c.get("topics", []):
        if t.get("slug"):
            m = ALL_MEMBERS.get(t["slug"], {})
            mail = f', {email_span(m["email_user"], m["email_domain"])}' if m.get("email_user") else ""
            who = person_link(d, t["slug"], t["who"]) + mail
        else:
            who = f'{escape(t["who"])}, {lab_email()}'
        if t.get("link"):
            href = t["link"]["href"]
            href = href if (lang == "fr" and href in FR_PAGES) else rel(d, href)
            who += f' · <a href="{href}">{escape(t["link"]["label"])}</a>'
        rows.append(f'<li><span class="what">{escape(t["what"])}</span><span class="who">{who}</span></li>')
    body = page_head(c["title"], escape(c["lede"])) + f"""
  <section class="band">
    <div class="wrap contact-cards">
      <div class="contact-card">
        <h2>{escape(c['write_title'])}</h2>
        <p>{escape(c['write_text'])}</p>
        <p>{lab_email('eml big')}</p>
        <p class="small muted">{fix_links(c.get('bluesky_text', ''), d, lang)}</p>
      </div>
      <div class="contact-card" id="visit">
        <h2>{escape(c['visit_title'])}</h2>
        <address>{visit_addr}</address>
        <p class="small" style="margin-top:.8rem">{escape(c['visit_text'])}</p>
        {maps}
      </div>
    </div>
  </section>
  <section class="band alt" aria-labelledby="who-title">
    <div class="wrap split">
      <div>
        <h2 id="who-title" style="margin-top:0">{escape(c['topics_title'])}</h2>
        <ul class="who-list">{''.join(rows)}</ul>
      </div>
      <div>
        <h2 style="margin-top:0">{escape(c['post_title'])}</h2>
        <address class="muted" style="font-style:normal">{post_addr}</address>
      </div>
    </div>
  </section>
"""
    write(path, d, c["title"], plain(c["lede"]), "contact.html", body, lang=lang,
          alt_path=("fr/contact.html" if lang == "en" else "contact.html") if FR.get("contact") else None)


def build_legal() -> None:
    L = SITE.get("legal") or {}
    if not L:
        return
    d = 0
    stats_en = ("Visits are counted with GoatCounter, which sets no cookie and keeps no personal data."
                if (SITE.get("goatcounter") or "").strip() else "No visitor statistics are collected.")
    stats_fr = ("Les visites sont comptées avec GoatCounter, sans cookie ni donnée personnelle."
                if (SITE.get("goatcounter") or "").strip() else "Aucune statistique de visite n'est collectée.")
    email = lab_email()
    body = page_head(L["title"], escape(L["lede"])) + f"""
  <section class="band">
    <div class="wrap"><div class="prose">
      <h2>Publisher</h2>
      <p>This website is published by {escape(L['publisher'])}. Contact: {email}.</p>
      <p>Publication director: {escape(L['director'])}. Editors: {escape(L['editors'])}.</p>
      <h2>Hosting</h2>
      <p>{escape(L['host'])}.</p>
      <h2>Personal data and cookies</h2>
      <p>This site sets no cookies, has no forms and collects no personal data. {stats_en} It loads no fonts, scripts or images from other websites; links to other sites (Bluesky, publishers, HAL…) lead to services with their own privacy policies. E-mail addresses are assembled in your browser so that robots cannot harvest them.</p>
      <h2>Credits</h2>
      <p>{escape(L['credits'])} The ocean cross-section is a drawing made for this site; it is not to scale.</p>
      <h2 id="accessibility">Accessibility</h2>
      <p><strong>Accessibility: {escape(L['status'])}.</strong> This site has not been audited against the RGAA, the French accessibility standard, so French rules require it to be declared non-compliant until it is.</p>
      <p>We build it to follow WCAG 2.1 level AA: text alternatives for images, a logical heading structure, keyboard navigation with visible focus, a link to skip to the content, and pages that work without JavaScript. Known limitations: some orange text has less contrast than the guidelines recommend, and the publication list reproduces titles as they are stored in HAL.</p>
      <p>If you cannot access a piece of content, write to {email} and we will send it to you in another form. If you do not get a satisfactory answer, you can contact the <a href="https://www.defenseurdesdroits.fr/">Défenseur des droits</a>.</p>

      <div class="lang-block" id="fr" lang="fr">
        <h2>Mentions légales</h2>
        <p>Ce site est édité par le laboratoire exocean du CEREGE (Centre de recherche et d'enseignement de géosciences de l'environnement : Aix-Marseille Université, CNRS, IRD, INRAE, Collège de France), Technopôle de l'Environnement Arbois-Méditerranée, avenue Louis Philibert, BP 80, 13545 Aix-en-Provence cedex 04. Contact : {email}.</p>
        <p>Directeur de la publication : {escape(L['director'])}. Rédaction : {escape(L['editors'].replace(' and ', ' et '))}.</p>
        <p>Hébergement : GitHub Pages — GitHub, Inc., 88 Colin P. Kelly Jr. Street, San Francisco, CA 94107, États-Unis.</p>
        <h2>Données personnelles et cookies</h2>
        <p>Ce site ne dépose aucun cookie, ne comporte aucun formulaire et ne collecte aucune donnée personnelle. {stats_fr} Il ne charge ni police, ni script, ni image depuis d'autres sites ; les liens externes (Bluesky, éditeurs, HAL…) mènent vers des services qui ont leur propre politique de confidentialité.</p>
        <h2 id="accessibilite">Accessibilité</h2>
        <p><strong>Accessibilité : {escape(L['status_fr'])}.</strong> Ce site n'a pas encore fait l'objet d'un audit de conformité au RGAA. Si vous ne pouvez pas accéder à un contenu, écrivez-nous à {email} : nous vous le transmettrons sous une autre forme. Sans réponse satisfaisante de notre part, vous pouvez saisir le <a href="https://www.defenseurdesdroits.fr/">Défenseur des droits</a>.</p>
      </div>
    </div></div>
  </section>
"""
    write("legal.html", d, L["title"], "Legal notice, personal data and accessibility statement of the exocean website.",
          "", body)


def build_404() -> None:
    # GitHub Pages serves this page for any missing address, at any depth
    # (…/projects/typo), so every link and asset on it must be absolute.
    d = ABS if BASE else 0
    body = page_head("Page not found", "That page has drifted off into the abyss.") + f"""
  <section class="band">
    <div class="wrap">
      <p>The page you were looking for doesn't exist, or it has moved.</p>
      <div class="btn-row">
        <a class="btn primary" href="{rel(d, 'index.html')}">Back to the lab</a>
        <a class="btn" href="{rel(d, 'projects.html')}">Our research</a>
        <a class="btn" href="{rel(d, 'contact.html')}">Contact us</a>
      </div>
    </div>
  </section>
"""
    write("404.html", d, "Page not found", "Page not found.", "", body)


def build_extras() -> None:
    """robots.txt and a sitemap (with the French alternates), so the site is findable."""
    pages = ["index.html", "projects.html", "services.html", "data.html", "publications.html", "team.html",
             "news.html", "join.html", "contact.html", "legal.html"]
    pages += [f"projects/{p['slug']}.html" for p in PROJECTS["projects"]]
    pages += [f"people/{m['slug']}.html" for m in ALL_MEMBERS.values() if m.get("bio")]
    pages += [f"news/{n['id']}.html" for n in NEWS["items"]]
    pages += [f"fr/{p}" for p in FR_PAGES if f"fr/{p}" in WRITTEN]
    base = SITE.get("baseurl") or ""
    rows = []
    for p in pages:
        loc = f"{base}/{'' if p == 'index.html' else p}"
        alts = ""
        name = p[3:] if p.startswith("fr/") else p
        if name in FR_PAGES and f"fr/{name}" in WRITTEN:
            alts = (f'<xhtml:link rel="alternate" hreflang="en" href="{base}/{name}"/>'
                    f'<xhtml:link rel="alternate" hreflang="fr" href="{base}/fr/{name}"/>')
        rows.append(f"  <url><loc>{loc}</loc>{alts}</url>")
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        + "\n".join(rows) + "\n</urlset>\n", encoding="utf-8")
    (OUT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nDisallow: /capabilities.html\nSitemap: {base}/sitemap.xml\n", encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    print("  sitemap.xml, robots.txt, .nojekyll")


def check_french() -> None:
    """Warn when the French pages lag behind the English content (an instrument
    or a service added in site.json but not yet in fr.json)."""
    en, fr = SITE.get("services") or {}, FR.get("services") or {}
    if not fr:
        return
    ids = lambda s: {i["id"] for g in s.get("groups", []) for i in g["items"] if i.get("id")}
    for x in sorted(ids(en) - ids(fr)):
        print(f"  warning: instrument '{x}' is on the English Services page but not in fr.json")
    n_en = sum(len(t["offers"]) for t in en.get("themes", []))
    n_fr = sum(len(t["offers"]) for t in fr.get("themes", []))
    if n_en != n_fr:
        print(f"  warning: {n_en} services in English but {n_fr} in fr.json")


if __name__ == "__main__":
    print("Building exocean…")
    build_home()
    build_research()
    build_services("en")
    build_services("fr")
    build_capabilities()
    build_data()
    build_publications()
    build_team()
    build_news()
    build_join("en")
    build_join("fr")
    build_contact("en")
    build_contact("fr")
    build_legal()
    build_404()
    build_redirects()
    build_extras()
    check_french()
    prune()
    print("Done.")
