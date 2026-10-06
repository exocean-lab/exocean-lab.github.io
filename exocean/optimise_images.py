#!/usr/bin/env python3
"""
exocean — make lighter copies of the site's photos.

For every photo in assets/img/ this writes WebP copies at a few widths into
assets/img/w/ (e.g. assets/img/w/founders-960.webp). build.py notices them and
lets each browser download the smallest copy that is sharp enough for its
screen; the original file stays as the fallback.

Needs Pillow (`pip install pillow`). The GitHub Action installs it and runs this
script before every build, so nobody has to run it by hand. The copies are not
committed (see .gitignore). A small manifest (w/manifest.json) remembers which
version of each photo the copies were made from, so only new or changed photos
are processed.

    python3 optimise_images.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).parent
IMG = ROOT / "assets" / "img"
OUT = IMG / "w"
MANIFEST = OUT / "manifest.json"

WIDTHS = (480, 960, 1600)
SKIP = {"favicon.png", "favicon-48.png", "apple-touch-icon.png", "share.jpg"}
MIN_WIDTH = 400                    # small logos are left alone
QUALITY = 80


def targets(width: int) -> list[int]:
    """Widths to make for an image `width` pixels wide: the standard steps
    below it, plus the full width itself (capped at the largest step)."""
    return sorted({min(w, width) for w in WIDTHS})


def main() -> int:
    try:
        from PIL import Image
    except ImportError:
        print("Pillow is not installed — skipping (the site still works with the original images).")
        return 0
    OUT.mkdir(exist_ok=True)
    try:
        manifest = json.loads(MANIFEST.read_text())
    except (OSError, ValueError):
        manifest = {}
    made, sources = 0, set()
    for src in sorted(IMG.iterdir()):
        if src.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp") or src.name in SKIP:
            continue
        digest = hashlib.sha1(src.read_bytes()).hexdigest()
        with Image.open(src) as im:
            w, h = im.size
            if w < MIN_WIDTH:
                continue
            sources.add(src.name)
            wanted = [OUT / f"{src.stem}-{t}.webp" for t in targets(w)]
            if manifest.get(src.name) == digest and all(d.exists() for d in wanted):
                continue
            mine = re.compile(re.escape(src.stem) + r"-\d+\.webp")
            for old in OUT.glob(f"{src.stem}-*.webp"):     # the photo changed: start afresh
                if mine.fullmatch(old.name):
                    old.unlink()
            mode = "RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB"
            base = im.convert(mode)
            for t, dest in zip(targets(w), wanted):
                copy = base if t == w else base.resize((t, round(h * t / w)), Image.LANCZOS)
                copy.save(dest, "WEBP", quality=QUALITY, method=6)
                made += 1
        manifest[src.name] = digest
    # forget photos that were deleted, and their copies
    for name in sorted(set(manifest) - sources):
        stem = pathlib.Path(name).stem
        mine = re.compile(re.escape(stem) + r"-\d+\.webp")
        for old in OUT.glob(f"{stem}-*.webp"):
            if mine.fullmatch(old.name):
                old.unlink()
        del manifest[name]
    MANIFEST.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print(f"optimise_images: {made} new WebP cop{'y' if made == 1 else 'ies'} in assets/img/w/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
