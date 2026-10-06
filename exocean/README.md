# exocean — lab website

The website of **exocean**, the Experimental Oceanology Laboratory at CEREGE,
Aix-en-Provence. Plain static HTML, no paid hosting, no subscription.

**Live site:** https://osulpis.github.io/exocean/

---

## The short version

All the words and people live in four text files inside `content/`.
Everything else is generated.

| File | What's in it |
|---|---|
| `content/site.json` | Home page, Services & Instruments page, Data & Models page, "Join us" text, contact details, menu, site address |
| `content/team.json` | Every person, their photo, bio and links (plus an empty "Former members" group) |
| `content/projects.json` | Deep-C, MANGO, DYNAMITE, ForCry, ASPERGE |
| `content/news.json` | News items (with a month/year date) and the press/media lists |

Change one of those, and the site rebuilds itself. You never have to touch HTML.

Two more files in `content/` are **not** edited by hand — the site refreshes
them itself every Monday (see below):

| File | Comes from |
|---|---|
| `content/publications.json` | HAL, for every person with an `"idhal"` in `team.json` |
| `content/bluesky.json` | The lab's Bluesky account (its own posts, not reposts) |

---

## How a change actually happens

**Automatically.** Every push to `main` runs `.github/workflows/static.yml`,
which regenerates the HTML and publishes it to GitHub Pages. Edit a JSON file
in GitHub's web editor, click *Commit*, and the live site updates about a
minute later.

**Every Monday morning**, the same workflow runs on its own: it asks HAL for
new publications and Bluesky for new posts, commits them if anything changed,
and republishes. If nothing changes for 45 days it leaves a one-line
"check-in" commit, because GitHub switches off scheduled jobs in repositories
with no commits for 60 days.

**On the 1st of each month**, `.github/workflows/linkcheck.yml` follows every
outside link on the site and opens an issue listing the ones that have died.

**Or locally**, if you have the folder on your machine:

```bash
python3 build.py            # regenerate the HTML
python3 fetch_hal.py        # optional: refresh the publication list
python3 fetch_bluesky.py    # optional: refresh the Bluesky strip
```

No installation, no dependencies — just Python 3, which macOS already has.

---

## Adding things

**A new team member** — open `content/team.json`, copy an existing block inside
the right group, change the fields. Drop their photo in `assets/img/` (square
works best, 640×640 or larger) and put the filename in `"photo"`.
Set `"photo": null` and they get a neat initials tile instead.

Anyone with a non-empty `"bio"` automatically gets their own page.
Anyone with `"bio": []` appears as a card only.

**An outside collaborator** — in `team.json`, the "Collaborators on current
projects" group lists them by project (`"external"`), without photos or pages
of their own: a name, an optional `"role"`, their `"institutions"` (each with
the `"url"` of its website, which becomes the link) and a `"country"`. They
are not bolded on the Publications page, which is kept for team members.

Add `"idhal": "firstname-lastname"` (their HAL author identifier) and their
papers join the Publications page at the next refresh, with a "Publications
(HAL)" link on their own page. Add `"orcid": "0000-0000-0000-0000"` and an
ORCID link appears first in their links.

**Someone leaves** — move their block into the `"Former members"` group at the
bottom of `team.json` (it is invisible while empty). Put the years in `"role"`,
e.g. `"PhD student, 2022–2025"`.

**A news item** — open `content/news.json` and copy an existing item to the top
of the `items` list. Give it a `"date"` as `"YYYY-MM"`; it is shown as
"February 2026". Body blocks come in three flavours:
`{"type": "p"}` for a paragraph, `{"type": "q"}` for an interview question, and
`{"type": "callout"}` for a highlighted box.

**A project** — copy a block in `content/projects.json`. Add
`"completed": true` to get the *Completed* tag.

**A model or a dataset** — open `content/site.json` and find `"data"` (the
Data & Models page). Each resource is one entry: a name, a one-line `"sub"`,
a short text, the team members involved (`"people"`, by their slug in
`team.json`), and its links grouped by kind (`"Papers"`, `"Code"`,
`"Archived releases"`, `"Data"`…). Prefer DOIs, and for Zenodo the *concept*
DOI, which always opens the latest version. Models and datasets only — not
the scripts behind individual papers.

**An instrument or a service** — open `content/site.json` and find `"services"`.
Each instrument is a line in one of the `"groups"`, with a short `"id"`
(e.g. `"cary60"`) and optionally a `"short"` name for its tag. Each service
sits in one of the three `"themes"`: a title, a text, and in `"kit"` the ids
of the instruments it uses — they become small tags that jump to the
instrument's line. The last group is marked `"reserved": true` (grey box) for
equipment that is not available to outside users. The `"cerege"` block holds
the "exocean within CEREGE" text, the six technical-centre tiles and the
other CEREGE platforms worth combining with a visit (each linked to its page
on cerege.fr). This page is public: keep prices, purchase dates and funding
sources out of it — quotes go by e-mail.

The stylesheet link carries a version tag (`style.css?v=…`) that `build.py`
derives from the file's content, so after a design change browsers fetch the
new stylesheet instead of reusing a cached one.

HTML is allowed inside any text field (`<strong>`, `<em>`, `<a href="…">`),
which is how the bold phrases and inline links are done.

---

## E-mail addresses

Addresses are never written into the HTML. They're stored as
`"email_user"` + `"email_domain"` and assembled in the browser, so address
harvesters don't pick them up. This mirrors how the old Owlstown site did it.

---

## Visitor statistics (optional)

The site is ready for [GoatCounter](https://www.goatcounter.com) — free,
no cookies, no consent banner. Create an account there, pick a site code
(say `exocean`), put it in `"goatcounter"` in `content/site.json`, and the
counting script is added to every page at the next build. Leave it empty
and nothing is loaded.

---

## What's in the repo

```
content/          the content files — this is what you edit
build.py          the generator; turns content/ into HTML
fetch_hal.py      refreshes content/publications.json from HAL
fetch_bluesky.py  refreshes content/bluesky.json from Bluesky
assets/css/       one stylesheet
assets/fonts/     the Cabin typeface, served from here (no Google Fonts call)
assets/js/        one small script (e-mail assembly)
assets/img/       every photo, logo and figure (share.jpg = link-preview image)
index.html        ┐
services.html     │
data.html         │
projects.html     │
publications.html │  generated — don't edit these by hand,
team.html         │  build.py will overwrite them
news.html         │
contact.html      │
projects/*.html   │
people/*.html     ┘
expertise.html    generated — forwards the retired Expertise page to Services
sitemap.xml       generated
robots.txt        generated
404.html          generated
```

---

## Hosting and the site address

Static files, served free by GitHub Pages through the workflow in
`.github/workflows/`. The site's public address is the `"baseurl"` in
`content/site.json`; it is used for link previews, the sitemap and the
"page not found" page.

To move to a custom domain later — `exocean.fr`, say — add a file called
`CNAME` inside `exocean/` containing just the domain, point the domain's DNS
at GitHub Pages, and change `"baseurl"` to the new address. The domain costs
around €10–15 a year; the hosting stays free.

---

## Known difference from the old site

The old Owlstown site had a **contact form**. A static site can't process a form
on its own. The Contact page gives the lab's address as a clickable
`mailto:` link instead. If a real form is wanted, Formspree or Web3Forms both
have free tiers and need one line of HTML.

---

## Credits

Photography © Elodie Gazquez, © SEMEPA / CEREGE, © Jaime Suárez-Ibarra,
as credited on each image. Logo and brand: exocean. Typeface: Cabin
(SIL Open Font License).
