#!/usr/bin/env python3
"""
exocean — static site generator.

Reads the JSON files in content/ and writes plain HTML to the repo root.
No dependencies beyond the Python standard library.

    python3 build.py

Everything an editor would ever want to change lives in content/*.json.
Nothing in this file needs touching to add a person, a project or a news item.

Two extra files, content/publications.json and content/bluesky.json, are not
edited by hand: fetch_hal.py and fetch_bluesky.py refresh them (the GitHub
Action runs both once a week). If they are missing the site still builds —
the Publications page and the Bluesky strip simply say so.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import shutil
import unicodedata
from html import escape

ROOT = pathlib.Path(__file__).parent
CONTENT = ROOT / "content"
OUT = ROOT


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
PUBLICATIONS = load("publications", optional=True)
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

# Absolute address of the site, without trailing slash. Used wherever a
# relative link would not do: link previews, the sitemap, the 404 page.
BASE = (SITE.get("baseurl") or "").rstrip("/")
ABS = -1  # pass as `depth` to get absolute URLs

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


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


def month_name(ym: str) -> str:
    """'2026-02' -> 'February 2026'; anything else is returned untouched."""
    m = re.fullmatch(r"(\d{4})-(\d{2})", ym or "")
    if not m:
        return ym or ""
    return f"{MONTHS[int(m.group(2)) - 1]} {m.group(1)}"


def _name_key(name: str) -> tuple[str, str]:
    """('j', 'suarez-ibarra') for 'Jaime Y. SUÁREZ-IBARRA' — first initial and
    last word, accents stripped, so HAL's spelling matches team.json's."""
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    words = [w for w in re.split(r"[\s,]+", plain.strip()) if w]
    if not words:
        return ("", "")
    return (words[0][0].lower(), words[-1].lower().strip("."))


TEAM_KEYS = {_name_key(m["name"]) for m in ALL_MEMBERS.values()}


def asset(depth: int, filename: str) -> str:
    return rel(depth, f"assets/img/{filename}")


def email_span(user: str, domain: str, cls: str = "eml") -> str:
    """Write an address the way the original site does — assembled by JS, not
    sitting in the markup for harvesters."""
    return f'<span class="{cls}" data-u="{escape(user)}" data-d="{escape(domain)}"></span>'


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


# --------------------------------------------------------------------------
# page chrome
# --------------------------------------------------------------------------

def head(depth: int, title: str, description: str, active: str, path: str = "") -> str:
    full_title = SITE["name"] if title == SITE["name"] else f'{SITE["name"]} — {title}'
    nav_items = []
    for item in SITE["nav"]:
        current = ' aria-current="page"' if item["href"] == active else ""
        nav_items.append(
            f'        <li><a href="{rel(depth, item["href"])}"{current}>{escape(item["label"])}</a></li>'
        )
    nav = "\n".join(nav_items)
    hero = asset(depth, "hero-banner.webp")
    # Link previews (Bluesky, WhatsApp, Slack…) and search engines need
    # absolute addresses; everything else on the page stays relative.
    page_url = absurl("" if path == "index.html" else path)
    share = absurl("assets/img/share.jpg")
    canonical = f'<link rel="canonical" href="{escape(page_url)}">\n<meta property="og:url" content="{escape(page_url)}">\n' if BASE and path != "404.html" else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(full_title)}</title>
<meta name="description" content="{escape(description)}">
{canonical}<meta property="og:site_name" content="{escape(SITE['name'])}">
<meta property="og:title" content="{escape(full_title)}">
<meta property="og:description" content="{escape(description)}">
<meta property="og:type" content="website">
<meta property="og:image" content="{escape(share)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#0a0e1a">
<link rel="icon" href="{asset(depth, 'favicon.png')}">
<link rel="apple-touch-icon" href="{asset(depth, 'favicon.png')}">
<link rel="stylesheet" href="{rel(depth, 'assets/css/style.css')}?v={CSS_V}">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<div class="sheet">

  <header class="banner" style="background-image:url('{hero}')">
    <a href="{rel(depth, 'index.html')}" aria-label="{escape(SITE['name'])} — home">
      <span class="visually-hidden">{escape(SITE['name'])}</span>
    </a>
    <p class="tagline">{escape(SITE['tagline'])}</p>
  </header>

  <nav class="nav" aria-label="Main">
    <ul>
{nav}
    </ul>
  </nav>

  <main id="main">
"""


def foot(depth: int) -> str:
    links = "\n".join(
        f'        <li><a href="{rel(depth, i["href"])}">{escape(i["label"])}</a></li>'
        for i in SITE["nav"]
    )
    f = SITE["footer"]
    return f"""  </main>

  <footer class="site-footer">
    <img class="partners" src="{asset(depth, f['partners_image'])}" alt="{escape(f['partners_alt'])}" loading="lazy">
    <nav aria-label="Footer">
      <ul>
{links}
        <li><a href="{escape(SITE['bluesky'])}">Bluesky</a></li>
      </ul>
    </nav>
    <p class="colophon">
      {escape(SITE['name'])} · {escape(SITE['tagline'])} ·
      <a href="{escape(f['cerege_url'])}">CEREGE</a>,
      Technop&ocirc;le de l'Arbois-M&eacute;diterran&eacute;e, Aix-en-Provence, France
    </p>
  </footer>

</div>
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


WRITTEN: set[str] = set()


def write(path: str, depth: int, title: str, description: str, active: str, body: str) -> None:
    target = OUT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(head(depth, title, description, active, path) + body + foot(depth), encoding="utf-8")
    WRITTEN.add(path)
    print(f"  {path}")


def prune() -> None:
    """Delete generated pages whose person or project no longer exists in
    content/ — e.g. someone removed from team.json — so the site never keeps
    serving a page for them. Only people/ and projects/ are touched."""
    for folder in ("people", "projects"):
        for page in sorted((OUT / folder).glob("*.html")):
            rel_path = f"{folder}/{page.name}"
            if rel_path not in WRITTEN:
                page.unlink()
                print(f"  removed stale {rel_path}")


# --------------------------------------------------------------------------
# pages
# --------------------------------------------------------------------------

def latest_papers(depth: int, n: int = 3) -> str:
    """The newest journal articles from content/publications.json, for the home
    page. Refreshes itself with the weekly HAL run; absent if there is no data."""
    items = (PUBLICATIONS or {}).get("items") or []
    if not items:
        return ""
    newest = sorted(items, key=lambda x: (x.get("date") or "", x.get("year") or 0), reverse=True)[:n]
    rows = []
    for it in newest:
        href = f"https://doi.org/{it['doi']}" if it.get("doi") else f"https://hal.science/{it['hal']}"
        where = escape(it.get("journal") or "")
        rows.append(f"""          <li>
            <a class="lp-title" href="{escape(href)}">{escape(it['title'])}</a>
            <span class="lp-meta">{format_authors(it['authors'])}</span>
            <span class="lp-meta"><em>{where}</em>{' · ' if where else ''}{it.get('year') or ''}</span>
          </li>""")
    return f"""
        <section class="latest-papers" aria-label="Latest papers">
          <h2>Latest papers</h2>
          <hr class="rule short">
          <ul>
{chr(10).join(rows)}
          </ul>
          <p class="lp-all"><a href="{rel(depth, 'publications.html')}">All our publications →</a></p>
        </section>
"""


def tools_block() -> str:
    """'Tools and data we share' on the Expertise page (text in site.json)."""
    t = SITE.get("tools")
    if not t:
        return ""
    lis = "\n".join(
        f"""          <li><a href="{escape(i['url'])}">{escape(i['label'])}</a><span>{escape(i['desc'])}</span></li>"""
        for i in t["items"]
    )
    return f"""        <section class="tools" id="tools">
          <h2>{escape(t['title'])}</h2>
          <p>{escape(t['intro'])}</p>
          <ul class="tools-list">
{lis}
          </ul>
        </section>
"""


def build_home() -> None:
    h = SITE["home"]
    d = 0
    founders = "\n".join(
        f'      <li><span class="who">{person_link(d, f["slug"], f["name"])},</span> {f["blurb"]}</li>'
        for f in h["founders"]
    )
    body = f"""    <section class="section">
      <div class="measure">
        <h1>{escape(h['title'])}</h1>
        <p class="lede">{escape(h['lede'])}</p>
        <hr class="rule">
        {"".join(f"<p>{p}</p>" for p in h["intro"])}

        <p class="btn-row"><a class="btn" href="expertise.html">Check our expertise</a></p>

        <figure>
          <img src="{asset(d, h['founders_photo'])}" alt="The three exocean founders in the laboratory" width="1400" height="778">
          <figcaption>{escape(h['founders_caption'])}</figcaption>
        </figure>

        <p>{escape(h['founders_intro'])}</p>
        <ul class="founder-list">
{founders}
        </ul>

        <p class="btn-row"><a class="btn" href="projects.html">Explore all our projects</a></p>

        <div class="callout">
          <p class="callout-title">{escape(h['questions_title'])}</p>
{bullets(h['questions'])}
        </div>

        <div class="btn-row two">
          <a class="btn" href="team.html">Meet the team</a>
          <a class="btn primary" href="contact.html#join">Want to be part of the adventure?</a>
        </div>
{latest_papers(d)}
        <h2>{escape(h['where_title'])}</h2>
        <hr class="rule short">
        {"".join(f"<p>{p}</p>" for p in h["where"])}

        <figure>
          <img src="{asset(d, h['where_photo'])}" alt="Aerial view of the CEREGE campus on the plateau de l'Arbois" loading="lazy" width="1400" height="568">
          <figcaption>{escape(h['where_caption'])}</figcaption>
        </figure>

        <p class="btn-row"><a class="btn" href="{escape(SITE['footer']['cerege_url'])}">More about CEREGE</a></p>
      </div>
    </section>
"""
    write("index.html", d, SITE["name"], SITE["description"], "index.html", body)


def build_expertise() -> None:
    e = SITE["expertise"]
    d = 0
    items = "\n".join(
        f"""        <article class="expertise-item">
          <h2>{escape(i['title'])}</h2>
          <p>{i['body']}</p>
        </article>"""
        for i in e["items"]
    )
    more = ""
    if SITE.get("services"):
        more = ('        <p class="more-link"><a href="services.html">'
                'The analyses we offer and the full list of our instruments →</a></p>\n')
    body = f"""    <section class="section">
      <div class="measure">
        <h1>{escape(e['title'])}</h1>
        <p class="lede">{escape(e['lede'])}</p>
        <hr class="rule">
        <figure>
          <img src="{asset(d, e['hero'])}" alt="Inside the exocean laboratory at CEREGE" width="1400" height="934">
        </figure>
{items}
{more}{tools_block()}
        <div class="btn-row two">
          <a class="btn" href="projects.html">Explore our projects</a>
          <a class="btn" href="news.html">News &amp; Highlights</a>
        </div>
        <p class="btn-row"><a class="btn primary" href="contact.html">Let's connect</a></p>
      </div>
    </section>
"""
    write("expertise.html", d, e["title"],
          "Carbonate system measurements, chemical microprofiling, foraminifera cultures, pressurized and rotating disk reactors at the exocean laboratory, CEREGE.",
          "expertise.html", body)


def build_services() -> None:
    """Services & Instruments page: what the lab runs for partners, grouped in
    themes, then the instrument list by type (all text in the "services" block
    of site.json). Each service names its instruments by "id"; they appear as
    small tags that jump to the instrument's line further down.
    Prices, purchase dates and funding sources are deliberately not kept there."""
    s = SITE.get("services")
    if not s:
        return
    d = 0
    user, domain = SITE["email"].split("@")

    instruments = {i["id"]: i for g in s.get("groups", []) for i in g["items"] if i.get("id")}

    def pill(ref: str) -> str:
        inst = instruments.get(ref)
        if not inst:                      # a typo in site.json must not break the build
            print(f"  warning: services kit names unknown instrument '{ref}'")
            return f"<li><span>{escape(ref)}</span></li>"
        label = inst.get("short") or inst["name"]
        return f'<li><a href="#i-{escape(ref)}">{escape(label)}</a></li>'

    hero = ""
    if s.get("hero"):
        credit = f'<span class="credit">{escape(s["hero_credit"])}</span>' if s.get("hero_credit") else ""
        hero = f"""        <figure>
          <img src="{asset(d, s['hero'])}" alt="{escape(s.get('hero_alt', ''))}" width="1400" height="788">
          <figcaption>{escape(s.get('hero_caption', ''))}{credit}</figcaption>
        </figure>"""

    intro = "\n".join(f"        <p>{p}</p>" for p in s.get("intro", []))

    request = ""
    if s.get("request"):
        r = s["request"]
        text = r["body"].replace("{email}", email_span(user, domain))
        request = f"""        <div class="callout">
          <p class="callout-title">{escape(r['title'])}</p>
          <p>{text}</p>
        </div>"""

    themes = s.get("themes") or [{"title": "", "offers": s.get("offers", [])}]
    theme_html = []
    for t in themes:
        items = []
        for o in t["offers"]:
            kit = o.get("kit") or []
            pills = (f'\n              <ul class="pills" aria-label="Instruments">{"".join(pill(k) for k in kit)}</ul>'
                     if kit else "")
            items.append(f"""            <li class="svc">
              <h4>{escape(o['title'])}</h4>
              <p>{o['body']}</p>{pills}
            </li>""")
        heading = f"\n          <h3>{escape(t['title'])}</h3>" if t.get("title") else ""
        theme_html.append(f"""        <section class="theme">{heading}
          <ul class="svc-list">
{chr(10).join(items)}
          </ul>
        </section>""")

    groups = []
    for g in s.get("groups", []):
        rows = "\n".join(
            f"""            <div class="inst"{f' id="i-{escape(i["id"])}"' if i.get("id") else ""}><dt>{escape(i['name'])}</dt><dd>{i['desc']}</dd></div>"""
            for i in g["items"]
        )
        note = f'\n          <p class="note">{g["note"]}</p>' if g.get("note") else ""
        cls = "inst-group reserved" if g.get("reserved") else "inst-group"
        groups.append(f"""        <section class="{cls}">
          <h3>{escape(g['heading'])}</h3>{note}
          <dl class="inst-list">
{rows}
          </dl>
        </section>""")

    body = f"""    <section class="section">
      <div class="measure">
        <h1>{escape(s['title'])}</h1>
        <p class="lede">{escape(s['lede'])}</p>
        <hr class="rule">
{hero}
{intro}
{request}
        <p class="jump">On this page: <a href="#offers">{escape(s['offers_title'])}</a> · <a href="#instruments">{escape(s['instruments_title'])}</a></p>

        <h2 id="offers">{escape(s['offers_title'])}</h2>
        <hr class="rule short">
{chr(10).join(theme_html)}

        <h2 id="instruments">{escape(s['instruments_title'])}</h2>
        <hr class="rule short">
        <p>{escape(s.get('instruments_intro', ''))}</p>
{chr(10).join(groups)}

        <div class="btn-row two">
          <a class="btn" href="expertise.html">Check our expertise</a>
          <a class="btn primary" href="contact.html">Contact us</a>
        </div>
      </div>
    </section>
"""
    write("services.html", d, s["title"],
          "Analyses and experiments the exocean laboratory at CEREGE runs for academic and private partners — "
          "carbonate chemistry, nutrients, microsensor profiling, cultures, high-pressure incubations — and its instruments.",
          "services.html", body)


def build_projects() -> None:
    d = 0
    cards = []
    for p in PROJECTS["projects"]:
        tag = '<span class="tag">Completed</span>' if p.get("completed") else ""
        name = p.get("short_name", p["name"])
        cards.append(f"""          <a class="card" href="projects/{p['slug']}.html">
            <div class="thumb"><img src="{asset(d, p['card_image'])}" alt="" loading="lazy"></div>
            <div class="body">
              {tag}
              <p class="name">{escape(name)}</p>
              <p class="blurb">{escape(p['card_text'])}</p>
            </div>
          </a>""")
    body = f"""    <section class="section">
      <div class="measure">
        <h1>{escape(PROJECTS['title'])}</h1>
        <p class="lede">{escape(PROJECTS['lede'])}</p>
        <hr class="rule">
        <div class="cards">
{chr(10).join(cards)}
        </div>
      </div>
    </section>
"""
    write("projects.html", d, PROJECTS["title"],
          "Deep-C, MANGO, DYNAMITE, ForCry and ASPERGE — the research projects running at the exocean laboratory, CEREGE.",
          "projects.html", body)

    for p in PROJECTS["projects"]:
        build_project(p)


def build_project(p: dict) -> None:
    d = 1
    parts = []

    if p.get("hero_image"):
        parts.append(f"""        <figure>
          <img src="{asset(d, p['hero_image'])}" alt="{escape(p['name'])}" loading="lazy">
        </figure>""")

    parts += [f"        <p>{t}</p>" for t in p["intro"]]

    for s in p["sections"]:
        parts.append('        <div class="callout">')
        parts.append(f'          <p class="callout-title">{escape(s["heading"])}</p>')
        if s.get("intro"):
            parts.append(f"          <p>{s['intro']}</p>")
        if s.get("body"):
            parts.append(f"          <p>{s['body']}</p>")
        if s.get("items"):
            parts.append(bullets(s["items"]))
        if s.get("outro"):
            parts.append(f"          <p>{s['outro']}</p>")
        parts.append("        </div>")

    # -- metadata block -----------------------------------------------------
    meta = []
    if p.get("keywords"):
        meta.append(f'          <dt>Keywords</dt><dd class="keywords">{escape(p["keywords"])}</dd>')

    def credit(entry: dict) -> str:
        if entry.get("slug"):
            txt = person_link(d, entry["slug"], entry["name"])
        elif entry.get("url"):
            txt = f'<a href="{escape(entry["url"])}">{escape(entry["name"])}</a>'
        else:
            txt = escape(entry["name"])
        if entry.get("email_user"):
            txt += " " + email_span(entry["email_user"], entry["email_domain"])
        return txt

    if p.get("lead"):
        meta.append(f'          <dt>{escape(p["lead"]["label"])}</dt><dd>{credit(p["lead"])}</dd>')
    if p.get("colead"):
        meta.append(f'          <dt>{escape(p["colead"]["label"])}</dt><dd>{credit(p["colead"])}</dd>')
    if p.get("participants"):
        names = ", ".join(credit(x) for x in p["participants"])
        meta.append(f"          <dt>CEREGE team</dt><dd>{names}</dd>")
    if p.get("former"):
        meta.append(f'          <dt>Former team members</dt><dd>{escape(", ".join(p["former"]))}</dd>')
    if p.get("external"):
        ext = "<br>".join(p["external"])
        meta.append(f"          <dt>External collaborators</dt><dd>{ext}</dd>")

    if meta:
        parts.append(f"""        <div class="meta">
          <h3>Who is on it</h3>
          <dl>
{chr(10).join(meta)}
          </dl>
        </div>""")

    if p.get("note"):
        parts.append(f'        <p class="keywords" style="margin-top:1.2rem">{escape(p["note"])}</p>')

    if p.get("funders"):
        imgs = "".join(
            f'<img src="{asset(d, f)}" alt="" loading="lazy">' for f in p["funders"]
        )
        parts.append(f"""        <p class="keywords" style="margin-top:1.6rem"><strong>Funded and hosted by</strong></p>
        <div class="funders">{imgs}</div>""")

    body = f"""    <section class="section">
      <div class="measure">
        <div class="proj-head">
          <span class="funder">{escape(p['funder'])}</span>
          <h1>{escape(p.get('short_name', p['name']))}</h1>
          <p class="subtitle">{escape(p['subtitle'])}</p>
        </div>
        <hr class="rule">
{chr(10).join(parts)}
        <div class="btn-row two">
          <a class="btn primary" href="{rel(d, 'contact.html')}">Contact us</a>
          <a class="btn" href="{rel(d, 'projects.html')}">Explore all our projects</a>
        </div>
        <a class="back-link" href="{rel(d, 'projects.html')}">All projects</a>
      </div>
    </section>
"""
    write(f"projects/{p['slug']}.html", d, p.get("short_name", p["name"]),
          p["subtitle"], "projects.html", body)


def build_team() -> None:
    d = 0
    groups = []
    for g in TEAM["groups"]:
        if not g.get("members"):        # e.g. "Former members" while still empty
            continue
        cards = []
        for m in g["members"]:
            if m.get("photo"):
                avatar = f'<div class="avatar"><img src="{asset(d, m["photo"])}" alt="{escape(m["name"])}" loading="lazy"></div>'
            else:
                avatar = f'<div class="avatar placeholder" aria-hidden="true">{escape(initials(m["name"]))}</div>'
            role = f'<span class="prole">{escape(m["role"])}</span>' if m.get("role") else ""
            inner = f"""{avatar}
              <span class="pname">{escape(m['name'])}</span>
              <span class="aff">{escape(m['affiliation'])}</span>
              {role}"""
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

    body = f"""    <section class="section">
      <div class="measure">
        <h1>{escape(TEAM['title'])}</h1>
        <p class="lede">{escape(TEAM['lede'])}</p>
        <hr class="rule">
{chr(10).join(groups)}
        <p class="btn-row"><a class="btn primary" href="contact.html#join">Want to collaborate? Join the team!</a></p>
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


def build_person(m: dict) -> None:
    d = 1
    if m.get("photo"):
        avatar = f'<div class="avatar"><img src="{asset(d, m["photo"])}" alt="{escape(m["name"])}"></div>'
    else:
        avatar = f'<div class="avatar placeholder" aria-hidden="true">{escape(initials(m["name"]))}</div>'

    role = f'<p class="prole">{escape(m["role"])}</p>' if m.get("role") else ""
    greeting = f'<p class="greeting">{escape(m["greeting"])}</p>' if m.get("greeting") else ""
    paras = "\n".join(f"        <p>{escape(t)}</p>" for t in m["bio"])

    contact = ""
    if m.get("email_user"):
        contact = (f'        <p style="margin-top:1.2rem">You can contact me directly at '
                   f'{email_span(m["email_user"], m["email_domain"])}</p>')

    links = ""
    link_list = list(m.get("links") or [])
    if m.get("idhal"):
        link_list.insert(0, {"label": "Publications (HAL)",
                             "url": f"https://hal.science/search/index/?q=*&authIdHal_s={m['idhal']}"})
    if m.get("orcid"):
        link_list.insert(0, {"label": f"ORCID {m['orcid']}", "url": f"https://orcid.org/{m['orcid']}"})
    if link_list:
        items = "".join(f'<li><a href="{escape(l["url"])}">{escape(l["label"])}</a></li>' for l in link_list)
        links = f'        <p style="margin-top:1.4rem"><strong>Find more about my scientific work:</strong></p>\n        <ul class="links-list">{items}</ul>'

    body = f"""    <section class="section">
      <div class="measure">
        <div class="bio-head">
          {avatar}
          <div>
            <h1>{escape(m['name'])}</h1>
            <p class="aff">{escape(m['affiliation'])}</p>
            {role}
          </div>
        </div>
        <hr class="rule short">
{greeting}
{paras}
{contact}
{links}
        <a class="back-link" href="{rel(d, 'team.html')}">Meet the other team members</a>
      </div>
    </section>
"""
    write(f"people/{m['slug']}.html", d, m["name"],
          f"{m['name']} — {m['affiliation']}. Member of the exocean laboratory at CEREGE.",
          "team.html", body)


def build_news() -> None:
    d = 0
    items = []
    for n in NEWS["items"]:
        blocks = []
        for b in n["body"]:
            if b["type"] == "q":
                blocks.append(f'        <p class="qa">{escape(b["text"])}</p>')
            elif b["type"] == "callout":
                blocks.append(f'        <div class="callout"><p>{b["text"]}</p></div>')
            else:
                blocks.append(f'        <p>{b["text"]}</p>')

        rm = ""
        if n.get("readmore"):
            lis = "".join(f'<li><a href="{escape(l["url"])}">{escape(l["label"])}</a></li>' for l in n["readmore"])
            rm = f"""        <div class="readmore">
          <p class="rm-label">{escape(n['readmore_label'])}</p>
          <ul>{lis}</ul>
        </div>"""

        when = f'<p class="news-date"><time datetime="{escape(n["date"])}">{escape(month_name(n["date"]))}</time></p>' if n.get("date") else ""
        items.append(f"""        <article class="news-item" id="{escape(n['id'])}">
          <h2>{escape(n['headline'])}</h2>
          {when}
          <figure>
            <img src="{asset(d, n['image'])}" alt="" loading="lazy">
            <figcaption>{n['image_caption']}<span class="credit">{escape(n['image_credit'])}</span></figcaption>
          </figure>
{chr(10).join(blocks)}
{rm}
        </article>""")

    media = NEWS["media"]
    groups = []
    for g in media["groups"]:
        lis = "".join(f'<li><a href="{escape(l["url"])}">{escape(l["label"])}</a></li>' for l in g["links"])
        groups.append(f"""          <div class="media-group">
            <h3>{escape(g['heading'])}</h3>
            <ul class="media-links">{lis}</ul>
          </div>""")

    body = f"""    <section class="section">
      <div class="measure">
        <h1>{escape(NEWS['title'])}</h1>
        <p class="lede">{escape(NEWS['lede'])}</p>
        <hr class="rule">
{bluesky_strip(d)}
        <h2 style="margin-top:0">{escape(NEWS['spotlight_label'])}</h2>
{chr(10).join(items)}

        <section class="meta" style="margin-top:3rem">
          <h2 style="margin-top:0">{escape(media['title'])}</h2>
          <figure>
            <img src="{asset(d, media['image'])}" alt="A pteropod" loading="lazy">
            <figcaption>{escape(media['image_caption'])}</figcaption>
          </figure>
{chr(10).join(groups)}
        </section>

        <p class="btn-row"><a class="btn primary" href="contact.html">Want to collaborate?</a></p>
      </div>
    </section>
"""
    write("news.html", d, NEWS["title"],
          "Awards, fellowships, reports and media coverage from the exocean laboratory at CEREGE.",
          "news.html", body)


def join_section() -> str:
    """Evergreen 'Join us' block on the Contact page (text in site.json)."""
    j = SITE.get("join")
    if not j:
        return ""
    blocks = "\n".join(
        f"""        <article class="join-item">
          <h3>{escape(i['title'])}</h3>
          <p>{i['body']}</p>
        </article>"""
        for i in j["items"]
    )
    return f"""
        <section id="join" class="join">
          <h2>{escape(j['title'])}</h2>
          <hr class="rule short">
          <p class="lede">{escape(j['lede'])}</p>
{blocks}
          <p class="join-note">Write to us at {email_span(*SITE['email'].split('@'))} — a short e-mail is all it takes.</p>
        </section>"""


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
        y, m, day = post["date"].split("-")
        nice = f"{int(day)} {MONTHS[int(m) - 1]} {y}"
        cards.append(f"""          <article class="bsky-post">
            <p class="bsky-date"><a href="{escape(post['url'])}"><time datetime="{escape(post['date'])}">{nice}</time></a></p>
            <p class="bsky-text">{post['html']}</p>
            {extra}
          </article>""")
    handle = escape((BLUESKY or {}).get("handle", ""))
    return f"""        <section class="bsky" aria-label="Latest from Bluesky">
          <div class="bsky-head">
            <h2>Latest from Bluesky</h2>
            <a class="bsky-follow" href="{escape(SITE['bluesky'])}">Follow @{handle}</a>
          </div>
          <div class="bsky-grid">
{chr(10).join(cards)}
          </div>
        </section>
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


def build_publications() -> None:
    d = 0
    pubs = PUBLICATIONS or {}
    items = pubs.get("items") or []
    idhal_people = [m for m in ALL_MEMBERS.values() if m.get("idhal")]
    who = ", ".join(person_link(d, m["slug"], m["name"]) for m in idhal_people) or "the team"

    if not items:
        listing = ('        <p>The publication list could not be generated yet — it is built automatically '
                   'from <a href="https://hal.science">HAL</a> and will appear after the next refresh.</p>')
    else:
        by_year: dict[int, list[dict]] = {}
        for it in items:
            by_year.setdefault(it.get("year") or 0, []).append(it)
        sections = []
        for year in sorted(by_year, reverse=True):
            entries = []
            for it in by_year[year]:
                journal = f'<em>{escape(it["journal"])}</em>' if it.get("journal") else ""
                if it.get("volume"):
                    journal += f' {escape(it["volume"])}'
                links = [f'<a href="https://hal.science/{escape(it["hal"])}">HAL</a>']
                if it.get("doi"):
                    links.insert(0, f'<a href="https://doi.org/{escape(it["doi"])}">DOI</a>')
                if it.get("pdf"):
                    links.append(f'<a href="{escape(it["pdf"])}">PDF</a>')
                entries.append(f"""            <li id="{escape(it['hal'])}">
              <span class="pub-title">{escape(it['title'])}</span>
              <span class="pub-authors">{format_authors(it['authors'])}</span>
              <span class="pub-where">{journal}{' · ' if journal else ''}{year or ''} · {' · '.join(links)}</span>
            </li>""")
            label = str(year) if year else "Undated"
            sections.append(f"""        <section class="pub-year">
          <h2 id="y{label}">{label} <span class="pub-count">{len(entries)}</span></h2>
          <ol class="pubs">
{chr(10).join(entries)}
          </ol>
        </section>""")
        listing = "\n".join(sections)

    updated = pubs.get("updated", "")
    count = pubs.get("count", len(items))
    body = f"""    <section class="section">
      <div class="measure">
        <h1>Publications</h1>
        <p class="lede">- Peer-reviewed articles and book chapters by the exocean team.</p>
        <hr class="rule">
        <p>This list is drawn automatically from <a href="https://hal.science">HAL</a>, the French national
        open archive, for {who} — names of team members are shown in bold. It refreshes itself every
        week; open-access PDFs are linked whenever HAL holds one. {f'<span class="pub-updated">{count} publications · last refreshed {escape(updated)}.</span>' if updated else ''}</p>
{listing}
        <div class="btn-row two">
          <a class="btn" href="projects.html">Explore our projects</a>
          <a class="btn" href="team.html">Meet the team</a>
        </div>
      </div>
    </section>
"""
    write("publications.html", d, "Publications",
          "Peer-reviewed publications of the exocean laboratory at CEREGE, drawn automatically from the HAL open archive.",
          "publications.html", body)


def build_contact() -> None:
    c = SITE["contact"]
    d = 0
    user, domain = SITE["email"].split("@")
    address = "<br>".join(escape(line) for line in SITE["address"])
    body = f"""    <section class="section">
      <div class="measure">
        <h1>{escape(c['title'])}</h1>
        <p class="lede">{escape(c['lede'])}</p>
        <hr class="rule">
        <p>{escape(c['body'])}</p>

        <div class="contact-card">
          <p class="brand">{escape(SITE['name'])}<small>{escape(SITE['tagline'])}</small></p>
          <p class="eml-wrap">{email_span(user, domain)}</p>
          <address>{address}</address>
        </div>

        <div class="btn-row two">
          <a class="btn" href="{escape(SITE['bluesky'])}">Follow us on Bluesky</a>
          <a class="btn" href="news.html">News &amp; Highlights</a>
        </div>
{join_section()}
      </div>
    </section>
"""
    write("contact.html", d, c["title"],
          "Get in touch with the exocean laboratory at CEREGE, Aix-en-Provence.",
          "contact.html", body)


def build_404() -> None:
    # GitHub Pages serves this page for any missing address, at any depth
    # (…/projects/typo), so every link and asset on it must be absolute.
    d = ABS if BASE else 0
    body = f"""    <section class="section">
      <div class="measure">
        <h1>Page not found</h1>
        <p class="lede">- That page has drifted off into the abyss.</p>
        <hr class="rule">
        <p>The page you were looking for doesn't exist, or it has moved.</p>
        <div class="btn-row two">
          <a class="btn primary" href="{rel(d, 'index.html')}">Back to the lab</a>
          <a class="btn" href="{rel(d, 'contact.html')}">Contact us</a>
        </div>
      </div>
    </section>
"""
    write("404.html", d, "Page not found", "Page not found.", "", body)


def build_extras() -> None:
    """robots.txt and a sitemap, so the site is findable."""
    pages = ["index.html", "expertise.html", "projects.html", "publications.html", "team.html", "news.html", "contact.html"]
    if SITE.get("services"):
        pages.insert(2, "services.html")
    pages += [f"projects/{p['slug']}.html" for p in PROJECTS["projects"]]
    pages += [f"people/{m['slug']}.html" for m in ALL_MEMBERS.values() if m.get("bio")]
    base = SITE.get("baseurl") or ""
    urls = "\n".join(f"  <url><loc>{base}/{'' if p == 'index.html' else p}</loc></url>" for p in pages)
    (OUT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}\n</urlset>\n',
        encoding="utf-8")
    (OUT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n", encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    print("  sitemap.xml, robots.txt, .nojekyll")


if __name__ == "__main__":
    print("Building exocean…")
    build_home()
    build_expertise()
    build_services()
    build_projects()
    build_team()
    build_publications()
    build_news()
    build_contact()
    build_404()
    build_extras()
    prune()
    print("Done.")
