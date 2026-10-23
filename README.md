# Site Clairfolio

Site statique en HTML, CSS et JavaScript, sans étape de construction, hébergé sur Netlify. Seul le dossier `site/` est publié (voir `netlify.toml`).

- **Adresse** : https://clairfolio.me (domaine obtenu le 23 octobre 2026). Toutes les adresses absolues du site (`canonical`, `og:*`, données structurées, `sitemap.xml`, `robots.txt`) l'utilisent déjà. Tant que le domaine n'est pas relié au site Netlify (Domain management, puis les enregistrements DNS indiqués par Netlify), il ne répond pas encore.
- **Langue** : français seul (`lang="fr"`).
- **Contraintes de conception** : chemins relatifs partout (seule exception : `404.html`), aucune couleur en dur hors de `site/styles/tokens.css`, aucun domaine externe appelé au chargement des pages (les liens vers Instagram et les sites de Clara sont de simples liens).
- **Journal du projet** : `PROGRESSION.md` (décisions, paliers, mesures, ce qui reste). Le contenu vient du dossier `branding/` de l'espace de travail, qui n'est pas dans ce dépôt.

## État au 23 octobre 2026

Le site est **fermé aux moteurs de recherche** (mode développement) jusqu'à ce que `tools/go_live.py` soit lancé. Voir « Mettre en ligne ».

## Structure du projet

```
netlify.toml            Dossier publié : site/
PROGRESSION.md          Journal de bord
site/                   Seul dossier publié
  *.html                11 pages (voir ci-dessous) + 404.html
  commencer/merci.html  Confirmation du formulaire (noindex)
  _headers              En-têtes HTTP : sécurité, cache des polices, bloc « développement » (noindex)
  _redirects            Les adresses en .html redirigent (301) vers l'adresse sans extension
  robots.txt            Mode développement : tout interdit
  sitemap.xml           11 adresses, les mêmes que les balises canonical
  site.webmanifest, favicon.*, apple-touch-icon.png, icon-*.png
  fonts/                Manrope et Inter, WOFF2 variables, avec leurs licences
  icons/                Symbole (couleur, marine, ivoire) et sprite.svg
  images/cas-clara/     Captures de téléphone (avant, après) en 300, 400, 600 et 1175 px de large
  images/cas-clara/rapports/   Les 4 rapports PageSpeed (WebP)
  images/og/clairfolio.jpg     Image de partage, 1200 x 630
  js/nav.js             Menu « Menu » / « Fermer » sur téléphone, retour d'appui des boutons-liens
  js/commencer.js       Formulaire : pré-remplissage, validation, envoi
  js/merci.js           Place le focus sur le titre de la confirmation
  styles/               Voir « Feuilles de style »
tools/
  audit_site.py         Audit statique du site
  go_live.py            Passage en production (voir plus bas)
  make_og_image.py      Génère l'image de partage depuis og-image.html
  og-image.html         Source de l'image de partage
  make_responsive.py    Génère des variantes WebP (voir « Images »)
  banc-d-essai/         Page de test des jetons (palette, boutons, messages), hors du dossier publié
```

Les 11 pages : `index` (accueil), `cas-clara`, `tarifs`, `forfait-essentiel`, `forfait-recommande`, `forfait-complet`, `a-propos`, `commencer`, `conditions-de-vente`, `mentions-legales`, `accessibilite`.

## Fonctionnement

### Couleurs et thème

Tout passe par des jetons dans `site/styles/tokens.css`. Le thème suit le navigateur (clair ou sombre), sans bouton de bascule. **Piège** : les valeurs du thème sombre existent à deux endroits dans ce fichier (`@media (prefers-color-scheme: dark)` et la classe `.on-dark`, utilisée par le pied de page et l'appel final). Toute modification se fait aux deux endroits.

### Feuilles de style

Chargées dans cet ordre sur toutes les pages : `tokens`, `fonts`, `base`, `button`, `site-header`, puis les feuilles propres à la page, puis `site-footer`. `no-js.css` est chargée dans un `<noscript>`. Feuilles propres : `hero` et `home` (accueil), `sections` (blocs communs, presque toutes les pages), `case` (cas Clara), `tarifs`, `plan` (pages forfait), `legal` (conditions de vente, mentions légales, accessibilité), `form`, `notice` et `commencer` (formulaire). Une feuille d'effets doit rester avant les composants qu'elle surcharge.

### Navigation

`js/nav.js` gère le bouton « Menu » et le retour d'appui des boutons-liens (classe `.is-pressed` posée au clic, retirée au retour par l'historique : sur téléphone, le `:active` du navigateur arrive trop tard pour un tap rapide). Sans JavaScript, la navigation reste visible et `:active` reste le retour d'appui. Le lien « Aller au contenu » est le premier élément atteint au clavier. Sur téléphone, la liste se déroule sous la barre en panneau par-dessus la page (hauteur animée, `visibility: hidden` quand elle est fermée, un appui ailleurs ou Échap la ferme) ; l'en-tête ne change pas de hauteur. Sans JavaScript, la liste reste visible dans le flux (`no-js.css`).

### Questions fréquentes

Accueil et Tarifs : un `<details>` par question, la question est un `h3` dans le `<summary>` (styles dans `sections.css`). Fonctionne sans JavaScript. Le déroulé animé utilise `::details-content` et `interpolate-size` (navigateurs récents) ; ailleurs, ou avec « réduire les animations », la réponse apparaît d'un coup. Pour ajouter une question, copier un bloc `<details>`.

### Formulaire « Commencer »

Netlify Forms : le formulaire `demande` est écrit dans le HTML (`data-netlify`, champ-piège `champ-piege`). Avec JavaScript, `js/commencer.js` envoie les réponses par `fetch` vers `/`, puis redirige vers `/commencer/merci`. Sans JavaScript, le navigateur envoie le formulaire de lui-même. Pré-remplissage par l'adresse : `commencer?site=non` ou `site=oui`, `forfait=essentiel`, `recommande` ou `complet`.

### En-têtes de sécurité

`site/_headers` envoie une politique de contenu stricte (`default-src 'self'`) : le site n'appelle aucun domaine externe. **Si un outil externe est ajouté un jour** (mesure d'audience, vidéo), son domaine doit être ajouté dans la ligne `Content-Security-Policy`, sinon le navigateur le bloque.

## Recettes

### Ajouter une page

1. Copier une page proche (par exemple `a-propos.html`), nom du fichier en tirets, sans accent. Le nom devient l'adresse : `ma-page.html` donne `/ma-page`.
2. Dans le `<head>` : `<title>` (60 caractères au plus), `description` (155 au plus), `canonical` absolu et sans extension, et les balises `og:*` avec les mêmes valeurs (copier le bloc d'une autre page).
3. Un seul `<h1>`, des titres sans saut de niveau.
4. Ajouter l'adresse dans `site/sitemap.xml`, et la ligne `/ma-page.html  /ma-page  301!` dans `site/_redirects`.
5. Ajouter le lien dans la navigation ou le pied de page des autres pages.
6. Lancer `python3 tools/audit_site.py --root site --platform netlify` : 0 FAIL attendu.

### Ajouter une image

1. Garder l'original (WebP ou JPEG de bonne qualité) comme repli `src`.
2. Créer des variantes plus étroites. Les captures de téléphone existantes suivent la convention `nom-300.webp`, `nom-400.webp`, `nom-600.webp` et `nom.webp` (1175 px), rangées à côté de l'original.
3. Dans le HTML : `srcset` avec les largeurs (`300w`, `400w`...), `sizes` renseigné, `width` et `height` (ou `aspect-ratio`), un texte alternatif de 150 caractères au plus (vide seulement si l'image est décorative), `loading="lazy"` sauf pour les images du premier écran.

Le script `tools/make_responsive.py` produit d'autres noms (`responsive/nom-400w.webp`) : à n'utiliser que pour de nouvelles images, avec la convention qu'il impose.

### Régénérer l'image de partage

`python3 tools/make_og_image.py` (nécessite Playwright et Pillow ; `--chromium <chemin>` pour utiliser un navigateur déjà installé). Source : `tools/og-image.html`. Résultat : `site/images/og/clairfolio.jpg`, 1200 x 630, moins de 300 Ko.

### Mettre en ligne (sortir du mode développement)

Deux réglages ferment le site aux moteurs de recherche : `Disallow: /` dans `robots.txt` et le bloc « développement » de `_headers`. Le script les retire :

```
python3 tools/go_live.py --check                       # montre ce qui change, n'écrit rien
python3 tools/go_live.py                               # mise en ligne
python3 tools/go_live.py --domain https://exemple.fr   # mise en ligne et changement d'adresse
python3 tools/go_live.py --domain https://exemple.fr --keep-dev   # change seulement l'adresse, le site reste fermé
python3 tools/audit_site.py --root site --platform netlify
```

Ensuite : déployer, puis lancer les commandes `curl` ci-dessous, puis déclarer le site dans la Search Console (propriété `https://<domaine>/`, envoyer `sitemap.xml`).

### Changer de domaine

`python3 tools/go_live.py --domain https://nouveau-domaine` remplace l'ancienne adresse dans toutes les pages (`canonical`, `og:url`, `og:image`, données structurées), `sitemap.xml` et `robots.txt`. Ensuite : nouvelle propriété dans la Search Console, et relire `PROGRESSION.md` (la section « Décisions verrouillées » mentionne l'adresse).

## Adresses et déploiement

- Netlify publie `site/` à chaque envoi sur la branche de production (`netlify.toml`).
- Les adresses sont **sans extension** (`/tarifs`). Le fichier `_redirects` redirige chaque adresse en `.html` vers la forme sans extension (301). **Non vérifié sur Netlify** : voir les commandes ci-dessous.
- `404.html` est servi par Netlify pour toute adresse inconnue. C'est la seule page qui utilise des chemins commençant par `/`, parce qu'elle s'affiche à l'adresse demandée, à n'importe quelle profondeur.
- Test en local : `file://` et `python3 -m http.server` ne connaissent pas les adresses sans extension. Utiliser `npx serve site` ou `npx netlify-cli dev`.

### Commandes de vérification en ligne (à lancer par la personne)

Remplacer `<domaine>`. Résultats attendus :

```
curl -sI https://<domaine>/                       200
curl -sI https://<domaine>/tarifs                 200
curl -sI https://<domaine>/commencer/merci        200
curl -sI https://<domaine>/tarifs.html            301, Location: /tarifs
curl -sI https://<domaine>/index.html             301, Location: /
curl -sI https://<domaine>/commencer/merci.html   301, Location: /commencer/merci
curl -sI https://<domaine>/robots.txt             200
curl -sI https://<domaine>/sitemap.xml            200
curl -sI https://<domaine>/page-inexistante       404 (et le corps est la page 404, pas l'accueil)
```

Deux points à regarder dans les en-têtes de `/` : la présence de `content-security-policy`, et `x-robots-tag: noindex` tant que le mode développement dure (absent après `go_live.py`).

## Référencement et partage

- Titre : « Sujet précis · Clairfolio » ; table des titres et descriptions dans le guide « Voix, UX et microtexte ».
- Chaque page indexable a `canonical`, `og:*` et `twitter:card`. Toutes utilisent la même image de partage (`images/og/clairfolio.jpg`) et le même texte alternatif.
- L'accueil porte des données structurées de type `Organization` (pas de `Person`, aucune adresse e-mail).
- `/commencer/merci` et `404.html` portent un `noindex` dans la page et ne figurent pas dans le plan du site.
- Search Console : à faire par la personne après la mise en ligne (voir plus haut). Si une balise `google-site-verification` est ajoutée à l'accueil, **ne jamais la supprimer**.

## Images et performances

Mesures Lighthouse mobile (émulation par défaut de Lighthouse 12 : téléphone Moto G, connexion 4G lente simulée, processeur ralenti), faites en local le 22 octobre 2026 sur un serveur qui imite Netlify, pas sur le site publié :

| Page | Performance | Accessibilité | Bonnes pratiques | Référencement | Contenu principal affiché |
|---|---|---|---|---|---|
| Accueil | 98 | 100 | 100 | 69 puis 100 après `go_live.py` (mesuré sur l'accueil) | 2,3 à 2,4 s |
| Tarifs | 99 | 100 | 100 | 69 (même cause) | 1,9 à 2,0 s |

Le 69 en référencement vient uniquement du `noindex` du mode développement (audit « page non explorable »). Zéro décalage de mise en page (0), temps de blocage 0 ms. À refaire sur le site publié : le serveur local n'applique pas la compression de Netlify.

## Accessibilité

La page `/accessibilite` dit ce qui a été contrôlé (axe-core, clavier, contrastes, zoom, texte agrandi) et ce qui ne l'a pas été (lecteur d'écran, Firefox, Safari, téléphone réel). Elle n'emploie pas la formule « Vérifié selon WCAG 2.2 AA ». Voir `PROGRESSION.md` pour la décision en attente.

## À ne jamais supprimer

- `site/_redirects` et `site/_headers` : sans eux, les adresses en `.html` restent accessibles et les en-têtes de sécurité disparaissent.
- `site/404.html`.
- Les fichiers `LICENSE.txt` dans `site/fonts/` (licence SIL Open Font).
- Les noms de fichiers des rapports PageSpeed (`images/cas-clara/rapports/`) : l'accueil et le cas Clara les citent.
- Le formulaire `demande` (nom, `data-netlify`, champ-piège) : Netlify le détecte au déploiement.

## Crédits et licences

- Polices Manrope et Inter, installées depuis `@fontsource-variable` (sous-ensemble latin), licence SIL Open Font 1.1.
- Captures de téléphone du cas Clara : avec l'accord de Clara.
