# exocean — lab website

The website of **exocean**, the Experimental Oceanology Laboratory at CEREGE,
Aix-en-Provence. Plain static HTML, no paid hosting, no subscription.

**Live site:** https://exocean-lab.github.io/  
**Repository:** https://github.com/exocean-lab/exocean-lab.github.io (organisation
`exocean-lab`; moved from `osulpis/exocean` on 6 October 2026 — the old
address osulpis.github.io/exocean forwards here)

---

## The short version

All the words and people live in a few text files inside `content/`.
Everything else is generated.

| File | What's in it |
|---|---|
| `content/site.json` | Home page, Research page (the ocean drawing, key questions), Services & Instruments, Data & Models, Join us (incl. open positions), Contact, legal notice, selected papers, menu, site address |
| `content/team.json` | Every person: position, one-line research focus, photo, bio, links (plus an empty "Former members" group) |
| `content/projects.json` | Deep-C, MANGO, DYNAMITE, ForCry, ASPERGE |
| `content/news.json` | News items (each gets its own page) and the press/media lists |
| `content/fr.json` | The French versions of Services, Join us and Contact |

Change one of those, and the site rebuilds itself. You never have to touch HTML.

Two more files in `content/` are **not** edited by hand — the site refreshes
them itself every Monday (see below):

| File | Comes from |
|---|---|
| `content/publications.json` | HAL: everything by members with an `"idhal"` in `team.json`, plus papers HAL links to the ORCID of the others |
| `content/bluesky.json` | The lab's Bluesky account: its latest posts, and the posts tagged **#exoceannews** |

---

## Three ways to edit

1. **With forms (easiest).** Go to https://app.pagescms.org, sign in with a
   GitHub account that belongs to the `exocean-lab` organisation, and open this
   repository. News, open positions, people, projects and the selected papers
   are there as forms (set up in `.pages.yml` at the top of the repository).
   *Save* makes a commit and the site updates about a minute later.
2. **On GitHub.** Open a file in `content/`, click the pencil, edit, *Commit*.
3. **Post on Bluesky.** A post from the lab's account that contains
   **#exoceannews** becomes a news item on the site at the next Monday refresh
   (first sentence = title; its photos are copied into the site). Run the
   workflow by hand (Actions → *Build and deploy exocean* → *Run workflow*) to
   see it at once.

---

## How a change actually happens

**Automatically.** Every push to `main` runs `.github/workflows/static.yml`,
which makes light copies of the photos, regenerates the HTML, prints the
one-page Services summary to PDF and publishes everything to GitHub Pages.

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
python3 fetch_bluesky.py    # optional: refresh Bluesky posts and #exoceannews items
python3 optimise_images.py  # optional, needs `pip install pillow`: lighter photos
```

Only Python 3 is needed for the first three (macOS has it).

---

## Adding things

**A news item** — in `content/news.json`, copy an existing item to the top of
`items`. Give it a short `"id"` (lower case and dashes: it becomes the address
`news/<id>.html`) and a `"date"` as `"YYYY-MM"`. Body blocks come in three
flavours: `{"type": "p"}` paragraph, `{"type": "q"}` interview question,
`{"type": "callout"}` highlighted box. Add an `"image_alt"` describing the
photo for people who cannot see it. The two newest items also appear on the
home page. (Or just post on Bluesky with #exoceannews.)

**An open position** — in `content/site.json`, under `"join"`, add it to
`"openings"`: `"title"`, `"type"` (e.g. "PhD, 3 years"), `"start"`,
`"deadline"`, `"body"`, and optionally `"url"` + `"link_label"` for the full
offer. It shows on the Join us page in both languages; remove it once filled.

**A team member** — in `content/team.json`, copy a block inside the right
group. Fill `"position"` (e.g. "PhD student") and `"focus"` (one line on what
they work on — it is what visitors read to know whom to write to). Drop the
photo in `assets/img/` (square, 640×640 or larger). Anyone with a non-empty
`"bio"` gets their own page, listing their projects and recent papers.

Add `"idhal": "firstname-lastname"` (their HAL author identifier) and their
papers join the Publications page at the next refresh. Without one, papers
that HAL links to their `"orcid"` are picked up instead — an idHAL is better
(create one at https://hal.science → *My space* → *My idHAL*).

**Someone leaves** — move their block into `"Former members"` at the bottom
of `team.json` (invisible while empty). Put the years in `"position"`.

**An outside collaborator** — in `team.json`, the "Collaborators on current
projects" group lists them by project (`"external"`): name, `"institutions"`
(each with the `"url"` of its website) and `"country"`. They are not bolded
on the Publications page.

**A project** — copy a block in `content/projects.json`. `"programme"` and
`"years"` show on its card; `"completed": true` moves it to *Completed
projects*. To place it on the ocean drawing, add a pin in `site.json` →
`"research"` → `"pins"` (`"x"` and `"y"` are percentages across and down the
drawing). Its page lists, under *Outputs so far*, the papers whose HAL record
declares the project's funding (same acronym as the project name); add
others by DOI in `"outputs"`.

**Selected papers** — `site.json` → `"publications"` → `"selected"`: a list
of DOIs shown first on the Publications page. Each must be in HAL under a team
member's name (the build warns otherwise).

**A model or a dataset** — `site.json` → `"data"` (the Data & Models page).
One entry per resource, with its links grouped by kind (`"Papers"`,
`"Code"`, `"Archived releases"`, `"Data"`…). Prefer DOIs, and for Zenodo the
*concept* DOI. Models and datasets only — not the scripts behind single papers.

**An instrument or a service** — `site.json` → `"services"`. Each instrument
is a line in one of the `"groups"` with a short `"id"`; each service sits in
one of the `"themes"` and names its instruments in `"kit"`. The last group is
`"reserved": true` (grey box) for equipment not open to outside users. Then do
the same in `content/fr.json` — the build warns when the French page lags
behind. This page is public: keep prices, purchase dates and funding sources
out of it; quotes go by e-mail.

HTML is allowed inside text fields (`<strong>`, `<em>`, `<a href="…">`). Write
links as seen from the site's root (`services.html`, `people/julie-meilland.html`):
the build adjusts them on pages in sub-folders. `{email}` in a text becomes
the lab's address.

---

## Photos, logos and the PDF

- Photos go in `assets/img/`, at their best quality (up to 1600–2000 px wide).
  `optimise_images.py` makes WebP copies at 480, 960 and 1600 px in
  `assets/img/w/`, and the pages let each browser pick the smallest sharp
  enough one. The Action does this on every deploy; the copies are not
  committed.
- The logos are the official files, vectorised: `logo.svg` (colour, header),
  `logo-white.svg` (footer), `logo-stacked.svg` / `logo-stacked-white.svg`,
  `mark.svg` (the c-and-bubbles symbol, used as the browser icon).
  `share.jpg` is the picture shown when a link is shared.
- `assets/exocean-services.pdf`, the one-page summary of the services, is
  printed from `capabilities.html` by Chrome in the Action (not committed).

---

## E-mail addresses

Addresses are never written into the HTML. They're stored as
`"email_user"` + `"email_domain"` (or `{email}` for the lab's) and assembled
in the browser, so address harvesters don't pick them up.

---

## Visitor statistics (optional)

The site is ready for [GoatCounter](https://www.goatcounter.com) — free for a
site like this, no cookies, no consent banner. Create an account there, pick a
site code (say `exocean`), put it in `"goatcounter"` in `content/site.json`,
and the counting script is added to every page at the next build (the legal
notice updates itself). Leave it empty and nothing is loaded.

Besides visits per page, countries, where visitors came from (Google,
Bluesky, CEREGE…) and devices, the site then counts a few clicks as
*events*: `email-<name>` when someone clicks an e-mail address,
`download-exocean-services.pdf` for the one-page summary, and
`out-<site>` for links to other sites (e.g. `out-zenodo.org`,
`out-github.com`), each with the page it was clicked on.

---

## Search engines

- **Google Search Console** (https://search.google.com/search-console): the
  site is verified with Google's file `google904f6ef6c92cc016.html`, which
  sits next to `index.html`. **Keep it there** — Google checks it again from
  time to time, and the site loses its verification if it disappears. (The
  other method, an HTML tag, would go in `"google_site_verification"` in
  `content/site.json`.) Submit `sitemap.xml` under Sitemaps.
- **Bing Webmaster Tools** (https://www.bing.com/webmasters): the site is
  verified with Bing's file `BingSiteAuth.xml`, next to `index.html`. **Keep it
  there** too. (The other methods: import from Google Search Console, or a
  meta tag whose code would go in `"bing_site_verification"`.)
- The pages carry structured data (schema.org): the lab and the site's name on
  the home page, each person (with their ORCID and other profiles) and each
  project.

---

## What's in the repo

```
.pages.yml           (top of the repository) the Pages CMS forms
content/             the content files — this is what you edit
build.py             the generator; turns content/ into HTML
fetch_hal.py         refreshes content/publications.json from HAL
fetch_bluesky.py     refreshes content/bluesky.json (and #exoceannews items)
optimise_images.py   makes the light WebP copies of the photos
assets/css/          one stylesheet
assets/fonts/        the Cabin typeface, served from here (no Google Fonts call)
assets/js/           one small script (e-mails, phone menu, publication search)
assets/img/          every photo, logo and figure
index.html           ┐
projects.html        │  Research
services.html        │
data.html            │
publications.html    │
team.html            │  People
news.html            │  generated — don't edit these by hand,
join.html            │  build.py overwrites them
contact.html         │
legal.html           │  legal notice and accessibility statement
projects/*.html      │
people/*.html        │
news/*.html          │
fr/*.html            ┘  French Services, Join us, Contact
capabilities.html    generated — the printable one-page summary
expertise.html       generated — forwards the retired Expertise page to Services
sitemap.xml, robots.txt, 404.html   generated
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

## Credits

Photography © Elodie Gazquez, © SEMEPA / CEREGE, © Jaime Suárez-Ibarra,
as credited on each image. Logo and brand: exocean. Typeface: Cabin
(SIL Open Font License). The ocean cross-section on the home and Research
pages is drawn by `build.py` (function `ocean_svg`).
