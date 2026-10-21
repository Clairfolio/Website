#!/usr/bin/env python3
"""
make_responsive.py - génère des variantes WebP à plusieurs largeurs pour chaque image.

Pour `images/projects/x/cover.jpg` (largeur 1600), crée dans `images/projects/x/responsive/` :
    cover-400w.webp, cover-800w.webp, cover-1600w.webp
(les largeurs cibles plus petites que l'original, plus une variante à la largeur native).

Usage :
    python3 make_responsive.py images/                       # tout le dossier
    python3 make_responsive.py images/gallery --widths 320 640 1280 --quality 82
    python3 make_responsive.py images/ --dry-run             # ne rien écrire, juste lister

Dépendance : Pillow (pip install pillow). L'image d'origine n'est jamais modifiée :
elle reste le repli `src` de la balise <img>.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:  # message clair plutôt qu'une trace
    sys.exit("Pillow est requis : pip install pillow")

SOURCE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_SKIP = {"responsive", "og", "favicon", "node_modules", ".git"}


def find_images(root: Path, skip: set[str]):
    for p in sorted(root.rglob("*")):
        if p.suffix.lower() not in SOURCE_EXT or not p.is_file():
            continue
        if any(part in skip for part in p.relative_to(root).parts[:-1]):
            continue
        yield p


def target_widths(orig_w: int, widths: list[int]) -> list[int]:
    smaller = sorted({w for w in widths if w < orig_w})
    return smaller + [orig_w]


def convert(src: Path, widths: list[int], quality: int, force: bool, dry: bool):
    out_dir = src.parent / "responsive"
    results = []
    with Image.open(src) as im:
        if getattr(im, "is_animated", False):
            return None, "animée, ignorée"
        im = ImageOps.exif_transpose(im)
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA" if "A" in im.getbands() or im.mode == "P" else "RGB")
        orig_w, orig_h = im.size
        for w in target_widths(orig_w, widths):
            dest = out_dir / f"{src.stem}-{w}w.webp"
            if dest.exists() and not force and dest.stat().st_mtime >= src.stat().st_mtime:
                results.append((w, dest, dest.stat().st_size, "déjà à jour"))
                continue
            if dry:
                results.append((w, dest, 0, "à créer"))
                continue
            h = round(orig_h * w / orig_w)
            resized = im if w == orig_w else im.resize((w, h), Image.LANCZOS)
            out_dir.mkdir(exist_ok=True)
            resized.save(dest, "WEBP", quality=quality, method=6)
            results.append((w, dest, dest.stat().st_size, "créé"))
    return (orig_w, results), None


def main() -> int:
    ap = argparse.ArgumentParser(description="Génère des variantes WebP responsives.")
    ap.add_argument("folder", help="dossier d'images (parcouru récursivement)")
    ap.add_argument("--widths", type=int, nargs="+", default=[400, 800, 1600, 1920], help="largeurs cibles en pixels (défaut : 400 800 1600 1920)")
    ap.add_argument("--quality", type=int, default=80, help="qualité WebP 1-100 (défaut : 80)")
    ap.add_argument("--force", action="store_true", help="régénérer même si la variante est à jour")
    ap.add_argument("--dry-run", action="store_true", help="ne rien écrire, afficher ce qui serait fait")
    ap.add_argument("--skip-dir", action="append", default=[], help="nom de dossier à ignorer en plus (répétable) ; ignorés d'office : " + ", ".join(sorted(DEFAULT_SKIP)))
    args = ap.parse_args()

    root = Path(args.folder)
    if not root.is_dir():
        sys.exit(f"Dossier introuvable : {root}")
    skip = DEFAULT_SKIP | set(args.skip_dir)

    total_src = total_out = count = 0
    for src in find_images(root, skip):
        data, note = convert(src, args.widths, args.quality, args.force, args.dry_run)
        rel = src.relative_to(root).as_posix()
        if data is None:
            print(f"- {rel} : {note}")
            continue
        orig_w, results = data
        count += 1
        total_src += src.stat().st_size
        srcset = []
        for w, dest, size, state in results:
            total_out += size
            srcset.append(f"{dest.parent.name}/{dest.name} {w}w")
        fresh = sum(1 for *_, state in results if state in ("créé", "à créer"))
        uptodate = len(results) - fresh
        detail = f"{fresh} {'à créer' if args.dry_run else 'créée(s)'}, {uptodate} déjà à jour"
        print(f"- {rel} ({orig_w} px, {src.stat().st_size // 1024} Ko) -> {', '.join(f'{w}w' for w, *_ in results)} [{detail}]")
        print(f"    srcset : {', '.join(srcset)}")
    if count == 0:
        print("Aucune image à traiter.")
        return 0
    verb = "à créer" if args.dry_run else "générées"
    print(f"\n{count} image(s) traitée(s). Poids des originaux : {total_src // 1024} Ko ; variantes {verb} : {total_out // 1024} Ko.")
    print("Rappel : renseigne aussi l'attribut sizes dans le HTML, et garde l'original en src (repli).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
