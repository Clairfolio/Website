#!/usr/bin/env python3
"""
make_og_image.py : génère l'image de partage du site (1200 x 630, JPEG, moins de 300 Ko).

Source : tools/og-image.html (texte, symbole et captures de téléphone).
Sortie : site/images/og/clairfolio.jpg

Dépendances : Playwright pour Python avec Chromium (pip install playwright, puis
playwright install chromium) et Pillow (pip install pillow).

Usage :
    python3 tools/make_og_image.py
    python3 tools/make_og_image.py --chromium /chemin/vers/chrome   # navigateur déjà installé
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

try:
    from PIL import Image
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("Playwright et Pillow sont requis : pip install playwright pillow")

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "tools" / "og-image.html"
DEST = ROOT / "site" / "images" / "og" / "clairfolio.jpg"
MAX_BYTES = 300 * 1024


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chromium", help="chemin d'un exécutable Chromium ou Chrome")
    args = ap.parse_args()

    with sync_playwright() as p:
        kwargs = {"args": ["--no-sandbox"]}
        if args.chromium:
            kwargs["executable_path"] = args.chromium
        browser = p.chromium.launch(**kwargs)
        page = browser.new_page(viewport={"width": 1200, "height": 630})
        page.goto(SOURCE.as_uri())
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(300)
        png = page.screenshot(clip={"x": 0, "y": 0, "width": 1200, "height": 630})
        browser.close()

    im = Image.open(io.BytesIO(png)).convert("RGB")
    DEST.parent.mkdir(parents=True, exist_ok=True)
    for quality in (90, 85, 80, 75, 70):
        im.save(DEST, "JPEG", quality=quality, optimize=True, progressive=True)
        if DEST.stat().st_size <= MAX_BYTES:
            break
    size = DEST.stat().st_size
    print(f"{DEST.relative_to(ROOT)} : {im.size[0]} x {im.size[1]}, {size / 1024:.0f} Ko (qualité {quality})")
    return 0 if size <= MAX_BYTES else 1


if __name__ == "__main__":
    sys.exit(main())
