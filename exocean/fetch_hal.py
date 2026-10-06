#!/usr/bin/env python3
"""
exocean — refresh content/publications.json from HAL.

HAL (hal.science) is the French national open archive; CNRS/IRD researchers
deposit their papers there. This script asks HAL for everything written by the
team members who have an "idhal" identifier in content/team.json (and, for
the others, anything HAL links to their ORCID), keeps peer-reviewed articles,
book chapters and books, and writes a tidy list that build.py turns into
publications.html. It also keeps the funding acronyms HAL records for each
paper (ERC, ANR…), so a project page can list the papers it funded.

It is run automatically by the GitHub Action once a week. Running it by hand
also works:

    python3 fetch_hal.py

Nothing is written if HAL cannot be reached or returns nothing, so a network
hiccup never blanks the page. No dependencies beyond the standard library.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request
from datetime import date

ROOT = pathlib.Path(__file__).parent
CONTENT = ROOT / "content"
OUT = CONTENT / "publications.json"

HAL_API = "https://api.archives-ouvertes.fr/search/"
# HAL document types kept on the page (ART = journal article, COUV = book
# chapter, OUV = book). Talks, posters, theses and preprints are left out.
KEEP_TYPES = ("ART", "COUV", "OUV")
# Journals that are really preprint venues; the final paper appears separately.
PREPRINT_VENUES = re.compile(r"(discussions?$|egusphere|research square|biorxiv|earth ?arxiv|essoar|ssrn|preprint)", re.I)
FIELDS = [
    "halId_s", "title_s", "authFullName_s", "journalTitle_s", "bookTitle_s",
    "producedDateY_i", "producedDate_tdate", "doiId_s", "fileMain_s", "docType_s",
    "volume_s", "page_s", "openAccess_bool",
    "europeanProjectAcronym_s", "anrProjectAcronym_s",
]


def members() -> list[dict]:
    team = json.loads((CONTENT / "team.json").read_text(encoding="utf-8"))
    return [m for group in team["groups"] for m in group.get("members", [])]


def idhals() -> list[str]:
    return [m["idhal"] for m in members() if m.get("idhal")]


def orcids() -> list[str]:
    """ORCID iDs of members without a HAL identifier: HAL links some papers to them."""
    return [m["orcid"] for m in members() if m.get("orcid") and not m.get("idhal")]


def fetch(ids: list[str], orcid_ids: list[str] | None = None) -> list[dict]:
    clauses = ["authIdHal_s:(" + " OR ".join(f'"{i}"' for i in ids) + ")"]
    if orcid_ids:
        clauses.append("authORCIDIdExt_id:(" + " OR ".join(f'"{o}"' for o in orcid_ids) + ")")
    query = {
        "q": " OR ".join(clauses),
        "fq": "docType_s:(" + " OR ".join(KEEP_TYPES) + ")",
        "fl": ",".join(FIELDS),
        "rows": 1000,
        "sort": "producedDate_tdate desc",
        "wt": "json",
    }
    url = HAL_API + "?" + urllib.parse.urlencode(query)
    req = urllib.request.Request(url, headers={"User-Agent": "exocean-website (https://github.com/exocean-lab/exocean-lab.github.io)"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    return data["response"]["docs"]


HYPHENS = re.compile("[\u2010\u2011\u2012\u2013\u2212]")
PARTICLES = {"de", "da", "di", "du", "del", "della", "der", "den", "des", "dos", "das", "van", "von", "le", "la", "y", "e"}


def tidy_name(name: str) -> str:
    """Author names as HAL sometimes stores them ("Jaime Y Suárez‐ibarra",
    "Maria a G Pivel"): plain hyphens, capital after a hyphen, capital initials."""
    name = HYPHENS.sub("-", name or "").strip()
    name = re.sub(r"(?<=[\w.])-(\w)", lambda m: "-" + m.group(1).upper(), name)
    words = name.split(" ")
    words = [w.upper() if len(w) == 1 and w.isalpha() and w.lower() not in PARTICLES and i > 0 else w
             for i, w in enumerate(words)]
    return " ".join(words)


def clean(docs: list[dict]) -> list[dict]:
    seen: set[str] = set()
    items = []
    for d in docs:
        journal = d.get("journalTitle_s") or d.get("bookTitle_s") or ""
        if PREPRINT_VENUES.search(journal):
            continue
        doi = (d.get("doiId_s") or "").strip().lower()
        key = "doi:" + doi if doi else "hal:" + d["halId_s"]
        if key in seen:
            continue
        seen.add(key)
        title = d["title_s"][0] if isinstance(d.get("title_s"), list) else d.get("title_s", "")
        items.append({
            "hal": d["halId_s"],
            "title": title.strip().rstrip("."),
            "authors": [tidy_name(a) for a in d.get("authFullName_s", [])],
            "journal": journal,
            "year": d.get("producedDateY_i"),
            "date": (d.get("producedDate_tdate") or "")[:10],
            "doi": doi or None,
            "pdf": d.get("fileMain_s") or None,
            "type": d.get("docType_s"),
            "volume": d.get("volume_s") or None,
            "pages": d.get("page_s") or None,
            "projects": sorted(set(d.get("europeanProjectAcronym_s", []) + d.get("anrProjectAcronym_s", []))),
        })
    items.sort(key=lambda x: (x["year"] or 0, x["date"], x["title"].lower()), reverse=True)
    return items


def main() -> int:
    ids = idhals()
    extra = orcids()
    if not ids:
        print("No member has an \"idhal\" in content/team.json — nothing to fetch.")
        return 1
    try:
        docs = fetch(ids, extra)
    except Exception as exc:  # network down, HAL down, malformed answer
        print(f"HAL could not be queried ({exc}); keeping the existing file.")
        return 1
    items = clean(docs)
    if not items:
        print("HAL returned no publications; keeping the existing file.")
        return 1

    previous = {}
    if OUT.exists():
        try:
            previous = json.loads(OUT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = {}
    if previous.get("items") == items and previous.get("idhals") == ids and previous.get("orcids", []) == extra:
        print(f"publications.json already up to date ({len(items)} items).")
        return 0

    payload = {
        "source": "HAL — https://hal.science",
        "idhals": ids,
        "orcids": extra,
        "updated": date.today().isoformat(),
        "count": len(items),
        "items": items,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} — {len(items)} publications for {', '.join(ids + extra)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
