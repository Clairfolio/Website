#!/usr/bin/env python3
"""
go_live.py : fait passer le site du mode développement au mode production.

Tant que ce script n'a pas été lancé, le site est fermé aux moteurs de recherche :
  - site/robots.txt contient « Disallow: / » ;
  - site/_headers envoie « X-Robots-Tag: noindex » sur toutes les pages.

Ce que fait le script (rien d'autre) :
  1. remplace site/robots.txt par la version de production (tout autorisé, plan du site indiqué) ;
  2. retire de site/_headers le bloc délimité par « DEBUT DU BLOC DEVELOPPEMENT » et « FIN DU BLOC DEVELOPPEMENT » ;
  3. avec --domain, remplace l'adresse du site (celle de la balise canonical de l'accueil) partout
     dans site/ : pages, sitemap.xml, robots.txt.

Il ne touche pas aux pages qui portent leur propre « noindex » (la confirmation /commencer/merci et la page 404).
Il peut être relancé sans risque : une seconde exécution ne change plus rien.

Usage :
    python3 tools/go_live.py --check                                  # montre ce qui changerait, n'écrit rien
    python3 tools/go_live.py                                          # mise en ligne, même adresse
    python3 tools/go_live.py --domain https://exemple.fr              # mise en ligne, nouvelle adresse
    python3 tools/go_live.py --domain https://exemple.fr --check
    python3 tools/go_live.py --domain https://exemple.fr --keep-dev   # change seulement l'adresse, le site reste fermé aux robots

Après l'exécution : python3 tools/audit_site.py --root site --platform netlify (0 FAIL attendu,
plus aucun avertissement sur robots.txt et _headers), puis déployer et lancer les commandes curl du README.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
BEGIN = "# DEBUT DU BLOC DEVELOPPEMENT"
END = "# FIN DU BLOC DEVELOPPEMENT"
TEXT_EXT = {".html", ".xml", ".txt", ".webmanifest", ".json"}


def current_origin() -> str:
    html = (SITE / "index.html").read_text(encoding="utf-8")
    m = re.search(r'<link rel="canonical" href="(https://[^/"]+)/?"', html)
    if not m:
        sys.exit("Balise canonical introuvable dans site/index.html.")
    return m.group(1)


def production_robots(origin: str) -> str:
    return (
        "# Production : tout le site peut être exploré.\n"
        "# La page de confirmation du formulaire et la page 404 portent leur propre « noindex ».\n"
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {origin}/sitemap.xml\n"
    )


def strip_dev_block(text: str) -> tuple[str, bool]:
    if BEGIN not in text:
        return text, False
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END) + r"[^\n]*\n?\n?", re.S)
    return pattern.sub("", text, count=1), True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--domain", help="nouvelle adresse du site, sans barre finale (exemple : https://exemple.fr)")
    ap.add_argument("--check", action="store_true", help="ne rien écrire, seulement lister")
    ap.add_argument("--keep-dev", action="store_true", help="changer seulement l'adresse (--domain) et garder le mode développement (noindex, robots.txt fermé)")
    args = ap.parse_args()

    old = current_origin()
    new = old
    if args.domain:
        new = args.domain.rstrip("/")
        if not re.fullmatch(r"https://[A-Za-z0-9.-]+(:\d+)?", new):
            sys.exit(f"Adresse invalide : {new} (attendu : https://nom-de-domaine, sans chemin).")

    actions: list[tuple[Path, str]] = []  # (fichier, nouveau contenu)

    if args.keep_dev and not args.domain:
        sys.exit("--keep-dev n'a de sens qu'avec --domain.")

    if not args.keep_dev:
        # 1. robots.txt
        robots = SITE / "robots.txt"
        wanted = production_robots(new)
        if not robots.exists() or robots.read_text(encoding="utf-8") != wanted:
            actions.append((robots, wanted))

        # 2. _headers
        headers = SITE / "_headers"
        if headers.exists():
            text = headers.read_text(encoding="utf-8")
            stripped, changed = strip_dev_block(text)
            if changed:
                actions.append((headers, stripped))

    # 3. changement de domaine
    if new != old:
        done = {p for p, _ in actions}
        for p in sorted(SITE.rglob("*")):
            if not p.is_file() or p.suffix not in TEXT_EXT or p in done:
                continue
            t = p.read_text(encoding="utf-8")
            if old in t:
                actions.append((p, t.replace(old, new)))
        # robots.txt a déjà été écrit avec la nouvelle adresse (étape 1)

    if not actions:
        print("Rien à changer.")
        return 0

    for path, content in actions:
        print(("À modifier : " if args.check else "Modifié    : ") + str(path.relative_to(ROOT)))
        if not args.check:
            path.write_text(content, encoding="utf-8", newline="")
    if new != old:
        print(f"Adresse : {old} -> {new}")
    if args.check:
        print("(--check : rien n'a été écrit)")
    else:
        print("Terminé. Lancez : python3 tools/audit_site.py --root site --platform netlify")
    return 0


if __name__ == "__main__":
    sys.exit(main())
