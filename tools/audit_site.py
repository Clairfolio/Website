#!/usr/bin/env python3
"""
audit_site.py - audit statique d'un portfolio HTML/CSS/JS (sans réseau, sans dépendance).

Usage :
    python3 audit_site.py --root <dossier du site> [--ignore 'images/*'] [--i18n data/i18n.json]

Adaptation Clairfolio (20 octobre 2026) : option --platform netlify.

Contrôle aussi les interdits stylistiques (tirets cadratins, capsule de hero à LED clignotante).

Trois niveaux de résultat :
    FAIL  bloque la porte du palier (à corriger)
    WARN  à examiner et discuter
    INFO  information utile, rien à corriger d'office

Code de sortie : 1 s'il y a au moins un FAIL, 0 sinon.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
from collections import OrderedDict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

EXTERNAL = ("http:", "https:", "mailto:", "tel:", "data:", "javascript:", "sms:", "//")
PLATFORM_PREFIXES = ("/_vercel/",)
SKIP_DIRS = {".git", "node_modules", ".vercel", "__pycache__"}


# --------------------------------------------------------------------------
# Analyse d'une page HTML
# --------------------------------------------------------------------------
class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lang = None
        self.title = ""
        self.title_i18n = None
        self._in_title = False
        self.metas: list[dict] = []
        self.links: list[dict] = []
        self.headings: list[tuple[int, int]] = []  # (niveau, ligne)
        self.imgs: list[tuple[int, dict]] = []
        self.refs: list[tuple[int, str, str, str]] = []  # (ligne, balise, attribut, valeur)
        self.ids: set[str] = set()
        self.i18n: list[tuple[int, str]] = []
        self.jsonld: list[tuple[int, str]] = []
        self._in_jsonld = False
        self._jsonld_line = 0
        self._buf: list[str] = []
        self.has_main = False
        self.first_body_anchor: tuple[int, str] | None = None
        self._in_body = False
        self.blank_links: list[int] = []
        self.iframes_without_title: list[int] = []
        self.analytics = False
        self.classes: list[tuple[int, str]] = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v if v is not None else "") for k, v in attrs}
        line = self.getpos()[0]
        if "id" in a:
            self.ids.add(a["id"])
        if a.get("class"):
            self.classes.append((line, a["class"]))
        if "data-i18n" in a:
            self.i18n.append((line, a["data-i18n"].strip()))
        if "data-i18n-attr" in a:
            for part in a["data-i18n-attr"].split(","):
                if ":" in part:
                    self.i18n.append((line, part.split(":", 1)[1].strip()))
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "body":
            self._in_body = True
        elif tag == "title":
            self._in_title = True
            self.title_i18n = a.get("data-i18n")
        elif tag == "meta":
            self.metas.append(a)
        elif tag == "link":
            self.links.append(a)
            if a.get("href"):
                self.refs.append((line, "link", "href", a["href"]))
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.headings.append((int(tag[1]), line))
        elif tag == "main":
            self.has_main = True
        elif tag == "img":
            self.imgs.append((line, a))
            if a.get("src"):
                self.refs.append((line, "img", "src", a["src"]))
            self._srcset(line, "img", a.get("srcset", ""))
        elif tag == "source":
            if a.get("src"):
                self.refs.append((line, "source", "src", a["src"]))
            self._srcset(line, "source", a.get("srcset", ""))
        elif tag == "a":
            href = a.get("href")
            if href is not None:
                self.refs.append((line, "a", "href", href))
                if self._in_body and self.first_body_anchor is None:
                    self.first_body_anchor = (line, href)
            if a.get("target") == "_blank" and "noopener" not in a.get("rel", ""):
                self.blank_links.append(line)
        elif tag == "script":
            if a.get("src"):
                self.refs.append((line, "script", "src", a["src"]))
                if "insights/script.js" in a["src"]:
                    self.analytics = True
            if a.get("type", "").lower() == "application/ld+json":
                self._in_jsonld = True
                self._jsonld_line = line
                self._buf = []
        elif tag == "iframe":
            if not a.get("title"):
                self.iframes_without_title.append(line)
        elif tag in ("video", "audio", "track") and a.get("src"):
            self.refs.append((line, tag, "src", a["src"]))

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "script" and self._in_jsonld:
            self._in_jsonld = False
            self.jsonld.append((self._jsonld_line, "".join(self._buf)))

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_jsonld:
            self._buf.append(data)

    def _srcset(self, line, tag, value):
        for item in value.split(","):
            url = item.strip().split(" ")[0]
            if url:
                self.refs.append((line, tag, "srcset", url))

    # accès pratiques
    def meta(self, key):
        for m in self.metas:
            if m.get("name") == key or m.get("property") == key:
                return m.get("content", "")
        return None

    def canonical(self):
        for l in self.links:
            if "canonical" in l.get("rel", "").split():
                return l.get("href")
        return None


# --------------------------------------------------------------------------
# Rapport
# --------------------------------------------------------------------------
class Report:
    def __init__(self) -> None:
        self.items: "OrderedDict[str, list[tuple[str, str, str]]]" = OrderedDict()
        self.counts = {"FAIL": 0, "WARN": 0, "INFO": 0}

    def add(self, sev: str, cat: str, where: str, msg: str) -> None:
        self.items.setdefault(cat, []).append((sev, where, msg))
        self.counts[sev] += 1

    def print(self, quiet_info: bool) -> None:
        for cat, rows in self.items.items():
            rows = [r for r in rows if not (quiet_info and r[0] == "INFO")]
            if not rows:
                continue
            print(f"\n== {cat}")
            for sev, where, msg in rows:
                loc = f"{where}  " if where else ""
                print(f"  [{sev}] {loc}{msg}")
        c = self.counts
        print(f"\nRésumé : {c['FAIL']} FAIL, {c['WARN']} WARN, {c['INFO']} INFO")
        if c["FAIL"] == 0:
            print("Porte : aucun FAIL. Examine les WARN avant de valider le palier.")
        else:
            print("Porte : fermée. Corrige les FAIL, puis relance l'audit.")


# --------------------------------------------------------------------------
# Utilitaires
# --------------------------------------------------------------------------
def rel(root: Path, p: Path) -> str:
    return p.relative_to(root).as_posix()


def matches(patterns, relpath: str) -> bool:
    return any(fnmatch.fnmatch(relpath, pat) for pat in patterns)


def kb(path: Path) -> int:
    return path.stat().st_size // 1024


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit statique d'un portfolio HTML/CSS/JS")
    ap.add_argument("--root", default=".", help="dossier du site (défaut : .)")
    ap.add_argument("--ignore", action="append", default=[], help="motif de chemin à ignorer pour l'existence des fichiers et leur poids (ex. 'images/*'), répétable")
    ap.add_argument("--i18n", default="data/i18n.json", help="fichier des traductions (défaut : data/i18n.json)")
    ap.add_argument("--max-title", type=int, default=70, help="longueur maximale du <title> (défaut : 70)")
    ap.add_argument("--no-info", action="store_true", help="masquer les lignes INFO")
    ap.add_argument("--platform", choices=["vercel", "netlify"], default="vercel", help="hébergeur (défaut : vercel). netlify : adresses sans extension supposées actives, pas de contrôle de vercel.json ni de Vercel Analytics")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"Dossier introuvable : {root}")
        return 2
    rep = Report()

    # ---- configuration Vercel
    clean = False
    trailing = None
    vj = root / "vercel.json"
    if args.platform == "netlify":
        clean = True
        rep.add("INFO", "Configuration", "", "Hébergeur Netlify : adresses sans extension supposées actives (à confirmer par curl au palier 9).")
    elif vj.exists():
        try:
            cfg = json.loads(vj.read_text(encoding="utf-8"))
            clean = bool(cfg.get("cleanUrls"))
            trailing = cfg.get("trailingSlash")
            if clean and trailing is not False:
                rep.add("WARN", "Configuration", "vercel.json", "cleanUrls est actif mais trailingSlash n'est pas false : une adresse avec « / » final casserait les chemins relatifs.")
            if not clean:
                rep.add("INFO", "Configuration", "vercel.json", "cleanUrls n'est pas actif : les pages restent en .html.")
        except json.JSONDecodeError as e:
            rep.add("FAIL", "Configuration", "vercel.json", f"JSON invalide : {e}")
    else:
        rep.add("INFO", "Configuration", "", "Pas de vercel.json : adresses en .html uniquement sur Vercel.")

    # ---- pages
    pages: dict[str, PageParser] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.lower().endswith(".html"):
                p = Path(dirpath) / fn
                parser = PageParser()
                parser.feed(p.read_text(encoding="utf-8", errors="replace"))
                pages[rel(root, p)] = parser
    if not pages:
        print("Aucune page .html trouvée.")
        return 2

    # ---- origine du site (depuis l'accueil)
    origin = None
    home = pages.get("index.html")
    if home and home.canonical():
        u = urlparse(home.canonical())
        if u.scheme and u.netloc:
            origin = f"{u.scheme}://{u.netloc}"

    def page_url_path(relpath: str) -> str:
        p = relpath[:-5] if relpath.endswith(".html") else relpath
        if p.endswith("index"):
            p = p[: -len("index")].rstrip("/")
            return "/" + p if p else "/"
        return "/" + p + ("" if clean else ".html")

    canonicals: dict[str, str] = {}
    id_cache = {k: v.ids for k, v in pages.items()}
    uses_clean_link = False

    def target_exists(p: Path):
        """(existe, a_utilisé_la_forme_sans_extension, fichier_html_cible)"""
        if p.is_file():
            return True, False, p if p.suffix == ".html" else None
        if p.is_dir() and (p / "index.html").is_file():
            return True, False, p / "index.html"
        h = p.with_name(p.name + ".html")
        if h.is_file():
            return True, True, h
        return False, False, None

    for name, pg in sorted(pages.items()):
        # --- métadonnées de base
        if not pg.lang:
            rep.add("FAIL", "Structure de page", name, "<html> sans attribut lang.")
        title = pg.title.strip()
        if not title:
            rep.add("FAIL", "Structure de page", name, "<title> absent ou vide.")
        elif len(title) > args.max_title:
            rep.add("WARN", "Structure de page", name, f"<title> de {len(title)} caractères (> {args.max_title}).")
        if pg.meta("viewport") is None:
            rep.add("FAIL", "Structure de page", name, "meta viewport absente.")
        desc = pg.meta("description")
        if not desc and ("noindex" in (pg.meta("robots") or "").lower() or name == "404.html"):
            pass  # le guide prévoit « aucune » description pour la confirmation et la page introuvable
        elif not desc:
            rep.add("WARN", "Référencement", name, "meta description absente.")
        elif len(desc) > 160:
            rep.add("WARN", "Référencement", name, f"meta description de {len(desc)} caractères (> 160).")
        if not pg.has_main:
            rep.add("FAIL", "Structure de page", name, "Pas de balise <main>.")
        h1 = [h for h in pg.headings if h[0] == 1]
        if len(h1) != 1:
            rep.add("FAIL", "Structure de page", name, f"{len(h1)} balises <h1> (il en faut exactement une).")
        prev = 0
        for lvl, line in pg.headings:
            if prev and lvl > prev + 1:
                rep.add("WARN", "Structure de page", f"{name}:{line}", f"Saut de titre h{prev} -> h{lvl}.")
            prev = lvl
        fb = pg.first_body_anchor
        if not fb or not fb[1].startswith("#") or fb[1][1:] not in pg.ids:
            rep.add("FAIL", "Accessibilité", name, "Pas de lien d'évitement en premier dans <body> (vers un id existant).")
        for line in pg.blank_links:
            rep.add("WARN", "Accessibilité", f"{name}:{line}", 'target="_blank" sans rel="noopener".')
        for line in pg.iframes_without_title:
            rep.add("WARN", "Accessibilité", f"{name}:{line}", "<iframe> sans attribut title.")
        if not any("icon" in l.get("rel", "").split() or l.get("rel") == "icon" for l in pg.links):
            rep.add("WARN", "Référencement", name, "Pas de favicon déclarée.")

        # --- canonical / Open Graph
        can = pg.canonical()
        ogu = pg.meta("og:url")
        noindex = "noindex" in (pg.meta("robots") or "").lower() or name == "404.html"
        if noindex:
            # Page hors référencement (confirmation, banc d'essai, 404) : ni canonical ni balises de partage requis.
            can = None
            ogu = None
            rep.add("INFO", "Référencement", name, "Page hors référencement (noindex ou 404) : canonical et balises de partage non contrôlés.")
        elif not can:
            rep.add("FAIL", "Référencement", name, "<link rel=canonical> absent.")
        else:
            cu = urlparse(can)
            if cu.scheme != "https" or not cu.netloc:
                rep.add("FAIL", "Référencement", name, f"canonical non absolu en https : {can}")
            else:
                canonicals[name] = can
                if origin and f"{cu.scheme}://{cu.netloc}" != origin:
                    rep.add("FAIL", "Référencement", name, f"canonical sur un autre domaine que l'accueil : {can}")
                elif origin:
                    expected = origin + page_url_path(name)
                    if can != expected:
                        rep.add("FAIL", "Référencement", name, f"canonical {can} différent de l'adresse attendue {expected}.")
        if noindex:
            pass
        elif ogu is None:
            rep.add("WARN", "Référencement", name, "og:url absent.")
        elif can and ogu != can:
            rep.add("FAIL", "Référencement", name, f"og:url ({ogu}) différent du canonical ({can}).")
        if not noindex:
            for key in ("og:title", "og:description", "og:image", "twitter:card"):
                if pg.meta(key) is None:
                    rep.add("WARN", "Référencement", name, f"{key} absent.")
        ogi = pg.meta("og:image")
        if ogi and not noindex:
            if not ogi.startswith("https://"):
                rep.add("WARN", "Référencement", name, f"og:image non absolue : {ogi}")
            elif origin and ogi.startswith(origin + "/"):
                lp = root / unquote(urlparse(ogi).path.lstrip("/"))
                if not lp.is_file():
                    if not matches(args.ignore, ogi[len(origin) + 1:]):
                        rep.add("WARN", "Référencement", name, f"og:image introuvable en local : {ogi}")
                elif kb(lp) > 300:
                    rep.add("WARN", "Référencement", name, f"og:image de {kb(lp)} Ko (> 300 Ko : risque d'aperçu absent sur certains réseaux).")
        for line, raw in pg.jsonld:
            try:
                json.loads(raw)
            except json.JSONDecodeError as e:
                rep.add("FAIL", "Référencement", f"{name}:{line}", f"JSON-LD invalide : {e}")

        # --- images
        eager = 0
        no_loading = 0
        for line, a in pg.imgs:
            if "alt" not in a:
                rep.add("FAIL", "Images", f"{name}:{line}", f"<img> sans attribut alt ({a.get('src', '?')}).")
            if "srcset" in a and re.search(r"\d+w", a["srcset"]) and "sizes" not in a:
                rep.add("WARN", "Images", f"{name}:{line}", "srcset en largeurs sans attribut sizes.")
            lo = a.get("loading")
            if lo == "eager":
                eager += 1
            elif lo is None:
                no_loading += 1
        if eager > 1:
            rep.add("WARN", "Images", name, f"{eager} images en loading=\"eager\" (une seule devrait l'être : celle du premier écran).")
        if no_loading:
            rep.add("INFO", "Images", name, f"{no_loading} image(s) sans attribut loading (chargées tout de suite).")

        # --- ressources et liens internes
        seen = set()
        for line, tag, attr, value in pg.refs:
            v = value.strip()
            if not v or v.startswith(EXTERNAL) or v.startswith(PLATFORM_PREFIXES):
                continue
            path_part = v.split("#")[0].split("?")[0]
            frag = v.split("#", 1)[1] if "#" in v else ""
            if not path_part:
                if frag and tag == "a" and frag not in pg.ids:
                    rep.add("WARN", "Liens et ressources", f"{name}:{line}", f"Ancre #{frag} introuvable dans la page (peut être créée par JavaScript).")
                continue
            p = Path(os.path.normpath(
                (root / path_part.lstrip("/")) if path_part.startswith("/")
                else (root / Path(name).parent / unquote(path_part))
            ))
            try:
                p.relative_to(root)
            except ValueError:
                rep.add("FAIL", "Liens et ressources", f"{name}:{line}", f"Chemin hors du site : {v}")
                continue
            if path_part.startswith("/") and tag != "a" and name != "404.html":
                rep.add("INFO", "Liens et ressources", f"{name}:{line}", f"Chemin absolu (à éviter hors scripts de plateforme) : {v}")
            ok, via_clean, target_html = target_exists(p)
            rp = rel(root, p) if p != root else ""
            if not ok:
                if matches(args.ignore, rp) or (v, tag) in seen:
                    continue
                seen.add((v, tag))
                sev = "FAIL"
                what = "Lien interne cassé" if tag == "a" else "Fichier manquant"
                rep.add(sev, "Liens et ressources", f"{name}:{line}", f"{what} : {v}")
                continue
            if tag == "a":
                if via_clean:
                    uses_clean_link = True
                if clean and path_part.endswith(".html"):
                    rep.add("WARN", "Adresses", f"{name}:{line}", f"Lien en .html alors que cleanUrls est actif : {v}")
                if frag and target_html is not None:
                    tid = id_cache.get(rel(root, target_html))
                    if tid is not None and frag not in tid:
                        rep.add("WARN", "Liens et ressources", f"{name}:{line}", f"Ancre #{frag} introuvable dans {rel(root, target_html)}.")
    with_an = [n for n, p in pages.items() if p.analytics]
    if args.platform == "netlify":
        if with_an:
            rep.add("WARN", "Mesure", "", "Script Vercel Analytics trouvé alors que l'hébergeur est Netlify : " + ", ".join(sorted(with_an)))
    elif with_an and len(with_an) != len(pages):
        missing = sorted(set(pages) - set(with_an))
        rep.add("WARN", "Mesure", "", "Script Vercel Analytics absent de : " + ", ".join(missing))
    elif not with_an:
        rep.add("INFO", "Mesure", "", "Aucun script Vercel Analytics détecté (normal avant le palier 10).")
    if args.platform == "vercel" and uses_clean_link and not clean:
        rep.add("WARN", "Adresses", "", "Des liens sans extension sont utilisés mais cleanUrls n'est pas actif : ils donneraient une 404 sur Vercel.")

    # ---- sitemap et robots
    sm = root / "sitemap.xml"
    if not sm.exists():
        rep.add("WARN", "Sitemap et robots", "sitemap.xml", "Fichier absent.")
    else:
        locs = [m.strip() for m in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", sm.read_text(encoding="utf-8", errors="replace"))]
        if len(set(locs)) != len(locs):
            rep.add("WARN", "Sitemap et robots", "sitemap.xml", "Adresses en double.")
        for loc in locs:
            if not loc.startswith("https://"):
                rep.add("FAIL", "Sitemap et robots", "sitemap.xml", f"Adresse non absolue en https : {loc}")
            if clean and loc.endswith(".html"):
                rep.add("WARN", "Sitemap et robots", "sitemap.xml", f"Adresse en .html alors que cleanUrls est actif : {loc}")
        canon_set = set(canonicals.values())
        for name, can in sorted(canonicals.items()):
            if can not in locs:
                rep.add("FAIL", "Sitemap et robots", name, f"Canonical absent du sitemap : {can}")
        for loc in locs:
            if loc not in canon_set:
                rep.add("WARN", "Sitemap et robots", "sitemap.xml", f"Adresse qui ne correspond à aucun canonical : {loc}")
        rep.add("INFO", "Sitemap et robots", "sitemap.xml", f"{len(locs)} adresse(s) pour {len(pages)} page(s).")
    rb = root / "robots.txt"
    if not rb.exists():
        rep.add("WARN", "Sitemap et robots", "robots.txt", "Fichier absent.")
    else:
        rtxt = rb.read_text(encoding="utf-8", errors="replace")
        if re.search(r"(?im)^\s*disallow\s*:\s*/\s*$", rtxt):
            rep.add("WARN", "Sitemap et robots", "robots.txt", "Tout le site est interdit aux robots (mode développement). Normal avant la mise en ligne ; à lever avec tools/go_live.py.")
        elif sm.exists() and not re.search(r"(?im)^\s*sitemap\s*:", rtxt):
            rep.add("WARN", "Sitemap et robots", "robots.txt", "Pas de ligne « Sitemap: ».")
    hp = root / "_headers"
    if hp.exists() and re.search(r"(?im)^\s+x-robots-tag\s*:\s*noindex", hp.read_text(encoding="utf-8", errors="replace")):
        rep.add("WARN", "Sitemap et robots", "_headers", "En-tête X-Robots-Tag: noindex actif (mode développement). Normal avant la mise en ligne ; à lever avec tools/go_live.py.")

    # ---- traductions
    ip = root / args.i18n
    if ip.exists():
        try:
            data = json.loads(ip.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            data = None
            rep.add("FAIL", "Traductions", args.i18n, f"JSON invalide : {e}")
        if isinstance(data, dict) and data:
            langs = list(data)
            base = set(data[langs[0]])
            for lg in langs[1:]:
                other = set(data[lg])
                for k in sorted(base - other)[:10]:
                    rep.add("FAIL", "Traductions", args.i18n, f"Clé « {k} » présente en {langs[0]} mais absente en {lg}.")
                for k in sorted(other - base)[:10]:
                    rep.add("FAIL", "Traductions", args.i18n, f"Clé « {k} » présente en {lg} mais absente en {langs[0]}.")
            for lg in langs:
                empty = [k for k, v in data[lg].items() if not str(v).strip()]
                if empty:
                    rep.add("WARN", "Traductions", args.i18n, f"{len(empty)} valeur(s) vide(s) en {lg} (ex. {empty[0]}).")
            used = set()
            missing_use: dict = {}
            for name, pg in pages.items():
                for line, key in pg.i18n:
                    used.add(key)
                    for lg in langs:
                        if key not in data[lg]:
                            missing_use.setdefault((key, lg), []).append(f"{name}:{line}")
                if len(langs) > 1 and pg.title.strip() and not pg.title_i18n:
                    rep.add("WARN", "Traductions", name, "<title> sans data-i18n : il ne suivra pas le changement de langue.")
            for (key, lg), places in sorted(missing_use.items()):
                extra = f" (+ {len(places) - 1} autre(s))" if len(places) > 1 else ""
                rep.add("FAIL", "Traductions", places[0], f"Clé « {key} » utilisée mais absente en {lg}{extra}.")
            unused = sorted(base - used)
            rep.add("INFO", "Traductions", args.i18n, f"{len(langs)} langue(s) ({', '.join(langs)}), {len(base)} clés ; {len(unused)} non utilisée(s) dans le HTML (certaines servent peut-être au JavaScript).")
    else:
        rep.add("INFO", "Traductions", "", f"Pas de {args.i18n} : site monolingue ou fichier ailleurs (--i18n).")

    # ---- poids des images et couleurs en dur
    heavy = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
                p = Path(dirpath) / fn
                if not matches(args.ignore, rel(root, p)) and kb(p) > 500:
                    heavy.append((kb(p), rel(root, p)))
    for size, path in sorted(heavy, reverse=True)[:8]:
        rep.add("WARN", "Poids", path, f"Image de {size} Ko (> 500 Ko).")
    css_dir = root / "styles"
    if css_dir.is_dir():
        hexre = re.compile(r"#[0-9a-fA-F]{3,8}\b")
        per_file = {}
        for css in sorted(css_dir.glob("*.css")):
            if css.name == "tokens.css":
                continue
            text = re.sub(r"/\*.*?\*/", "", css.read_text(encoding="utf-8", errors="replace"), flags=re.S)
            n = len(hexre.findall(text))
            if n:
                per_file[css.name] = n
        if per_file:
            detail = ", ".join(f"{k} ({v})" for k, v in per_file.items())
            rep.add("INFO", "Couleurs", "styles/", f"Couleurs hexadécimales hors tokens.css : {detail}. Légitime pour une illustration qui garde ses couleurs dans les deux thèmes ; sinon à passer en variables.")

    # ---- interdits stylistiques (voir references/interdits.md)
    EM, EN = "\u2014", "\u2013"
    em_hits, en_hits, css_files = [], [], []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.lower().endswith((".html", ".css", ".js", ".json", ".md", ".txt", ".xml", ".svg")):
                continue
            fp = Path(dirpath) / fn
            rp = rel(root, fp)
            if matches(args.ignore, rp):
                continue
            try:
                text = fp.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if EM in line:
                    em_hits.append(f"{rp}:{i}")
                if EN in line:
                    en_hits.append(f"{rp}:{i}")
            if fn.lower().endswith(".css"):
                css_files.append((rp, text))
    for where in em_hits[:15]:
        rep.add("FAIL", "Interdits", where, "Tiret cadratin interdit (remplacer : virgule, deux-points, parenthèses, point ou tiret simple).")
    if len(em_hits) > 15:
        rep.add("FAIL", "Interdits", "", f"... et {len(em_hits) - 15} autre(s) ligne(s) avec un tiret cadratin.")
    for where in en_hits[:10]:
        rep.add("WARN", "Interdits", where, "Demi-cadratin à éviter (pour une plage de dates, préférer un tiret simple ou « de ... à ... »).")
    if len(en_hits) > 10:
        rep.add("WARN", "Interdits", "", f"... et {len(en_hits) - 10} autre(s) ligne(s) avec un demi-cadratin.")

    bad_anim = re.compile(r"pulse|blink|ping|beacon|flash", re.I)
    badge_sel = re.compile(r"(?<![a-z])(dot|led|live|chip|pill)(?![a-z])|status|badge|capsule|indicator|availab|dispo|online", re.I)
    for rp, text in css_files:
        no_comments = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", no_comments):
            sel, body = m.group(1).strip(), m.group(2)
            am = re.search(r"animation(?:-name)?\s*:\s*([^;]+)", body)
            if am and bad_anim.search(am.group(1)) and badge_sel.search(sel):
                rep.add("FAIL", "Interdits", rp, f"Animation de pulsation ou de clignotement sur « {sel[:60]} » : capsule à LED clignotante interdite (voir references/interdits.md). Si c'est un faux positif, justifie-le avec la personne.")
    avail = re.compile(r"disponible (pour|dès|immédiatement)|available for|open to work|ouvert(e)?s? aux opportunités|currently available|now booking|accepting (new )?(projects|clients)|open for (work|opportunities)", re.I)
    scan_files = [root / n for n in pages] + ([ip] if ip.exists() else [])
    for fp in scan_files:
        try:
            lines = fp.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            if avail.search(line):
                rep.add("WARN", "Interdits", f"{rel(root, fp)}:{i}", "Phrase de disponibilité typique d'une capsule de hero : à examiner (interdit si elle accompagne un point lumineux ; sinon, une phrase simple est acceptable).")
    for name, pg in sorted(pages.items()):
        for line, cls in pg.classes:
            if re.search(r"(?<![a-z])(led|blink|blinking|pulse)(?![a-z])|(status|live|online|pulse)[-_]dot|availab", cls, re.I):
                rep.add("WARN", "Interdits", f"{name}:{line}", f"Classe suspecte (« {cls[:50]} ») : vérifier qu'il ne s'agit pas d'une capsule à LED clignotante.")

    rep.add("INFO", "Résumé du site", "", f"{len(pages)} page(s) HTML, origine {origin or 'inconnue'}, cleanUrls {'actif' if clean else 'inactif'}.")
    print(f"Audit de {root}")
    rep.print(args.no_info)
    return 1 if rep.counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
