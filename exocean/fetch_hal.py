#!/usr/bin/env python3
"""
exocean — refresh content/publications.json from HAL.

HAL (hal.science) is the French national open archive; CNRS/IRD researchers
deposit their papers there. This script asks HAL for everything written by the
team members who have an "idhal" identifier in content/team.json, keeps
peer-reviewed articles, book chapters and books, and writes a tidy list that
build.py turns into publications.html.

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
]


def idhals() -> list[str]:
    team = json.loads((CONTENT / "team.json").read_text(encoding="utf-8"))
    ids = []
    for group in team["groups"]:
        for member in group.get("members", []):
            if member.get("idhal"):
                ids.append(member["idhal"])
    return ids


def fetch(ids: list[str]) -> list[dict]:
    query = {
        "q": "authIdHal_s:(" + " OR ".join(f'"{i}"' for i in ids) + ")",
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
            "authors": d.get("authFullName_s", []),
            "journal": journal,
            "year": d.get("producedDateY_i"),
            "date": (d.get("producedDate_tdate") or "")[:10],
            "doi": doi or None,
            "pdf": d.get("fileMain_s") or None,
            "type": d.get("docType_s"),
            "volume": d.get("volume_s") or None,
            "pages": d.get("page_s") or None,
        })
    items.sort(key=lambda x: (x["year"] or 0, x["date"], x["title"].lower()), reverse=True)
    return items


def main() -> int:
    ids = idhals()
    if not ids:
        print("No member has an \"idhal\" in content/team.json — nothing to fetch.")
        return 1
    try:
        docs = fetch(ids)
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
    if previous.get("items") == items and previous.get("idhals") == ids:
        print(f"publications.json already up to date ({len(items)} items).")
        return 0

    payload = {
        "source": "HAL — https://hal.science",
        "idhals": ids,
        "updated": date.today().isoformat(),
        "count": len(items),
        "items": items,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} — {len(items)} publications for {', '.join(ids)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
