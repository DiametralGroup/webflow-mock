"""Le jeu de données : le site vitrine de « Boréal Conseil » dans Webflow.

Même monde que les cinq autres mocks de l'écosystème insights360 — ESN
française de 34 personnes, trois agences (Paris, Lyon, Nantes), trois pôles
(Data & Analytics, Cloud & Platform, Cybersécurité), domaine
`boreal-conseil.example`, ancre au 15 juillet 2026, graine 42 — vu cette fois
par le SITE VITRINE : les pages, le blog et les études de cas du CMS, les
offres d'emploi publiées, et les formulaires par lesquels les prospects et les
candidats entrent en contact.

┌─ CE QUI EST PARTAGÉ AVEC LES MOCKS VOISINS, ET CE QUI NE L'EST PAS ─────────┐
│ PARTAGÉ (dupliqué ici, sans dépendance de paquet — aucun des six mocks ne   │
│ dépend d'un autre) : les raisons sociales des clients (les études de cas   │
│ citent Lumina Retail, Banque Hexagone, Voltalis Énergie…), les trois       │
│ agences et les trois pôles (les offres d'emploi les portent en options),   │
│ l'ancre temporelle, la graine.                                              │
│                                                                             │
│ PAS PARTAGÉ : les VOLUMES de trafic. GA4 mesure les visites, Webflow ne     │
│ sert que ce que le site CONTIENT et ce que ses formulaires REÇOIVENT. Un    │
│ test aval qui rapprocherait les deux compare des chemins de pages et des   │
│ jours, pas des compteurs.                                                   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ LES SOUMISSIONS SONT NOMINATIVES, ET C'EST VOULU ──────────────────────────┐
│ `formResponse` porte un prénom, un nom, un e-mail, parfois un téléphone et  │
│ un message libre — comme chez le fournisseur. Ce sont des personnes         │
│ FICTIVES, tirées de la graine, mais la FORME est celle que le consommateur  │
│ rencontrera : c'est à lui de ne retenir que ce qui compte (quand, quel     │
│ formulaire, quelle locale, quel domaine d'e-mail) et de laisser le reste.  │
│ Un mock qui servirait des soumissions déjà anonymisées validerait un        │
│ connecteur qui ne minimise rien.                                            │
└─────────────────────────────────────────────────────────────────────────────┘

Déterminisme : `random.Random(seed)` et une ancre temporelle FIXE. Jamais
`datetime.now()` — deux exécutions produisent le même jeu de données au même
octet, c'est ce qui rend les tests aval reproductibles. Les identifiants sont
des ObjectId de 24 hexadécimaux DÉRIVÉS de la graine, stables d'un reset à
l'autre.
"""

from __future__ import annotations

import hashlib
import random
from datetime import date, datetime, timedelta
from typing import Any

from ..settings import settings

# ── Ancre temporelle ─────────────────────────────────────────────────────────

#: Identique à celle des cinq autres mocks.
AUJOURDHUI = date(2026, 7, 15)
#: Plafond de tous les `lastUpdated` et `dateSubmitted` du jeu de BASE. Les
#: événements d'évolution sont STRICTEMENT postérieurs : un curseur incrémental
#: posé ici doit rendre zéro ligne tant que le monde n'a pas bougé.
DERNIERE_MAJ = date(2026, 7, 12)
#: Mise en ligne du site actuel — rien n'est antérieur.
MISE_EN_LIGNE = date(2024, 3, 18)
#: Première soumission de l'année servie.
DEBUT_SOUMISSIONS = date(2026, 1, 5)


# ── Utilitaires de forme ─────────────────────────────────────────────────────


def oid(seed: int, *parties: object) -> str:
    """Un ObjectId de 24 hexadécimaux, DÉRIVÉ de la graine et d'une clé.

    Stable d'un reset à l'autre pour une même graine : un test qui note un
    identifiant peut le réutiliser. Différent d'une graine à l'autre : deux
    mocks à graines différentes ne partagent aucun identifiant.
    """
    brut = ":".join(str(p) for p in (seed, *parties)).encode()
    return hashlib.sha1(brut, usedforsecurity=False).hexdigest()[:24]


def horodatage(quand: datetime) -> str:
    """`2026-07-12T14:08:08.146Z` — le format du fournisseur.

    UTC avec un `Z` final et TROIS chiffres de millisecondes, jamais un
    décalage `+02:00` ni six chiffres : c'est ce que montrent tous les
    exemples de la référence.
    """
    return quand.strftime("%Y-%m-%dT%H:%M:%S.") + f"{quand.microsecond // 1000:03d}Z"


def _dt(jour: date, h: int = 9, mn: int = 0, s: int = 0, ms: int = 0) -> str:
    return horodatage(datetime(jour.year, jour.month, jour.day, h, mn, s, ms * 1000))


def _instant(rng: random.Random, jour: date, ouvre: bool = True) -> str:
    """Un instant plausible dans la journée — heures ouvrées si demandé."""
    h = rng.randint(8, 18) if ouvre else rng.randint(6, 23)
    return _dt(jour, h, rng.randint(0, 59), rng.randint(0, 59), rng.randrange(1000))


def _maj(rng: random.Random, apres: date) -> str:
    """Un `lastUpdated` plausible : postérieur à la création, jamais après l'ancre."""
    if apres >= DERNIERE_MAJ:
        return _instant(rng, DERNIERE_MAJ)
    jour = apres + timedelta(days=rng.randint(0, (DERNIERE_MAJ - apres).days))
    return _instant(rng, jour)


def slugifier(texte: str) -> str:
    table = str.maketrans("àâäéèêëîïôöùûüç'\u2019 ", "aaaeeeeiioouuuc---")
    propre = texte.lower().translate(table)
    return "".join(c for c in propre if c.isalnum() or c == "-").strip("-")


# ── Catalogues — le même monde que les mocks voisins ─────────────────────────

AGENCES: tuple[str, ...] = ("Paris", "Lyon", "Nantes")
POLES: tuple[str, ...] = ("Data & Analytics", "Cloud & Platform", "Cybersécurité")
CONTRATS: tuple[str, ...] = ("CDI", "CDD", "Stage", "Alternance")
SECTEURS: tuple[str, ...] = (
    "Retail & Distribution",
    "Banque & Assurance",
    "Énergie & Utilities",
    "Transport",
    "Santé & Pharma",
    "Industrie",
    "Télécoms & Médias",
)

#: (raison sociale, secteur, domaine d'e-mail) — les clients de boondmanager-mock.
CLIENTS: tuple[tuple[str, str, str], ...] = (
    ("Lumina Retail", "Retail & Distribution", "lumina-retail.example"),
    ("Banque Hexagone", "Banque & Assurance", "banque-hexagone.example"),
    ("Voltalis Énergie", "Énergie & Utilities", "voltalis-energie.example"),
    ("Mutuelle Armor", "Banque & Assurance", "mutuelle-armor.example"),
    ("TransEuropa Fret", "Transport", "transeuropa-fret.example"),
    ("Pharmadis", "Santé & Pharma", "pharmadis.example"),
    ("Citymob", "Transport", "citymob.example"),
    ("Assurial", "Banque & Assurance", "assurial.example"),
    ("Groupe Ardentes", "Industrie", "groupe-ardentes.example"),
    ("MediaQuartz", "Télécoms & Médias", "mediaquartz.example"),
)

#: Domaines d'e-mail GÉNÉRIQUES — un prospect qui écrit depuis l'un d'eux n'est
#: pas rattachable à une entreprise. La proportion (≈ 45 %) est celle qu'on
#: observe sur un formulaire de contact B2B ouvert.
DOMAINES_GENERIQUES: tuple[str, ...] = (
    "gmail.com",
    "outlook.fr",
    "hotmail.fr",
    "yahoo.fr",
    "icloud.com",
    "orange.fr",
    "free.fr",
    "laposte.net",
    "protonmail.com",
)

#: Domaines d'entreprises PROSPECTS — hors du portefeuille client, pour que les
#: soumissions ne viennent pas toutes de clients existants.
DOMAINES_PROSPECTS: tuple[str, ...] = (
    "nordfret-logistique.example",
    "cliniques-atlantis.example",
    "helvetia-assur.example",
    "arcadie-industrie.example",
    "ville-de-brest.example",
    "groupe-solstice.example",
    "ecole-centrale-lyon.example",
    "opale-telecom.example",
    "banque-des-territoires.example",
    "mairie-de-nantes.example",
    "univ-rennes.example",
    "startup-kairos.example",
)

PRENOMS: tuple[str, ...] = (
    "Camille", "Julien", "Inès", "Thomas", "Léa", "Mehdi", "Chloé", "Antoine",
    "Sarah", "Nicolas", "Manon", "Karim", "Émilie", "Hugo", "Nadia", "Pierre",
    "Aurélie", "Yanis", "Sophie", "Maxime", "Fatou", "Romain", "Claire", "Bastien",
    "Amina", "Vincent", "Élodie", "Lucas", "Marion", "Samir",
)  # fmt: skip
NOMS: tuple[str, ...] = (
    "Martin", "Bernard", "Dubois", "Rousseau", "Lefèvre", "Moreau", "Garcia",
    "Nguyen", "Benali", "Petit", "Roux", "Fournier", "Girard", "Lambert", "Diallo",
    "Mercier", "Blanc", "Guérin", "Chevalier", "Da Silva", "Marchand", "Faure",
    "Legrand", "Haddad", "Perrin", "Robin", "Clément", "Morel", "Gauthier", "Ndiaye",
)  # fmt: skip

FONCTIONS: tuple[str, ...] = (
    "DSI", "Responsable Data", "Head of Data", "CTO", "Chef de projet", "Architecte cloud",
    "RSSI", "Directeur des opérations", "Product Owner", "Data Engineer", "Étudiant",
    "Consultant indépendant", "Responsable marketing", "DRH",
)  # fmt: skip

SUJETS_CONTACT: tuple[str, ...] = (
    "Demande de devis",
    "Renfort d'équipe data",
    "Migration cloud",
    "Audit de sécurité",
    "Partenariat",
    "Presse",
    "Formation Power BI",
    "Autre",
)

POSTES_SOUHAITES: tuple[str, ...] = (
    "Data Engineer",
    "Consultant BI",
    "Architecte cloud",
    "Pentester",
    "Chef de projet",
    "Alternance data",
    "Stage cybersécurité",
)


# ── Les entités ──────────────────────────────────────────────────────────────


def _locales(seed: int) -> dict[str, Any]:
    return {
        "primary": {
            "id": oid(seed, "locale", "fr"),
            "cmsLocaleId": oid(seed, "cmslocale", "fr"),
            "enabled": True,
            "displayName": "French (France)",
            "displayImageId": None,
            "redirect": True,
            "subdirectory": "",
            "tag": "fr-FR",
        },
        "secondary": [
            {
                "id": oid(seed, "locale", "en"),
                "cmsLocaleId": oid(seed, "cmslocale", "en"),
                "enabled": True,
                "displayName": "English (United States)",
                "displayImageId": None,
                "redirect": True,
                "subdirectory": "en",
                "tag": "en-US",
            }
        ],
    }


def _site(seed: int, locales: dict[str, Any]) -> dict[str, Any]:
    site_id = oid(seed, "site")
    return {
        "id": site_id,
        "workspaceId": oid(seed, "workspace"),
        "createdOn": _dt(MISE_EN_LIGNE - timedelta(days=61), 10, 12, 4, 118),
        "displayName": settings.site_name,
        "shortName": settings.site_short_name,
        "lastPublished": _dt(DERNIERE_MAJ - timedelta(days=1), 17, 42, 9, 331),
        "lastUpdated": _dt(DERNIERE_MAJ, 11, 6, 27, 502),
        "previewUrl": (
            f"https://screenshots.webflow.com/sites/{site_id}/"
            "20260712110627_a3f9c1e07d4b8e2f6c5a1b3d9e7f0a2c.png"
        ),
        "timeZone": "Europe/Paris",
        "parentFolderId": None,
        "customDomains": [
            {
                "id": oid(seed, "domain", 1),
                "url": settings.site_domain,
                "lastPublished": _dt(DERNIERE_MAJ - timedelta(days=1), 17, 42, 9, 331),
            },
            {
                "id": oid(seed, "domain", 2),
                "url": settings.site_domain.removeprefix("www."),
                "lastPublished": _dt(DERNIERE_MAJ - timedelta(days=1), 17, 42, 9, 331),
            },
        ],
        "locales": locales,
        "dataCollectionEnabled": True,
        "dataCollectionType": "optOut",
    }


#: (clé, titre fr, titre en, slug, dossier, chemin publié, gabarit de, brouillon, archivée)
_PAGES: tuple[tuple[str, str, str, str, str | None, str, str | None, bool, bool], ...] = (
    ("accueil", "Accueil", "Home", "accueil", None, "/", None, False, False),
    ("expertises", "Nos expertises", "Our expertise", "expertises", None, "/expertises", None, False, False),
    ("data", "Data & Analytics", "Data & Analytics", "data-analytics", "expertises", "/expertises/data-analytics", None, False, False),
    ("cloud", "Cloud & Platform", "Cloud & Platform", "cloud-platform", "expertises", "/expertises/cloud-platform", None, False, False),
    ("cyber", "Cybersécurité", "Cybersecurity", "cybersecurite", "expertises", "/expertises/cybersecurite", None, False, False),
    ("etudes", "Études de cas", "Case studies", "etudes-de-cas", None, "/etudes-de-cas", None, False, False),
    ("etude_gabarit", "Étude de cas — gabarit", "Case study — template", "detail_etude", None, "/etudes-de-cas/detail_etude", "etudes", False, False),
    ("blog", "Blog", "Blog", "blog", None, "/blog", None, False, False),
    ("article_gabarit", "Article — gabarit", "Post — template", "detail_article", None, "/blog/detail_article", "articles", False, False),
    ("carrieres", "Nous rejoindre", "Join us", "carrieres", None, "/carrieres", None, False, False),
    ("offre_gabarit", "Offre d'emploi — gabarit", "Job offer — template", "detail_offre", None, "/offres-emploi/detail_offre", "offres", False, False),
    ("evenements", "Événements", "Events", "evenements", None, "/evenements", None, False, False),
    ("evenement_gabarit", "Événement — gabarit", "Event — template", "detail_evenement", None, "/evenements/detail_evenement", "evenements", False, False),
    ("a_propos", "À propos", "About", "a-propos", None, "/a-propos", None, False, False),
    ("contact", "Contact", "Contact", "contact", None, "/contact", None, False, False),
    ("lb_mlops", "Livre blanc — Industrialiser le ML", "White paper — Industrializing ML", "livre-blanc-mlops", "ressources", "/ressources/livre-blanc-mlops", None, False, False),
    ("lb_cyber", "Livre blanc — Sécuriser le cloud", "White paper — Securing the cloud", "livre-blanc-cybersecurite", "ressources", "/ressources/livre-blanc-cybersecurite", None, False, False),
    ("mentions", "Mentions légales", "Legal notice", "mentions-legales", None, "/mentions-legales", None, False, False),
    ("confidentialite", "Politique de confidentialité", "Privacy policy", "politique-de-confidentialite", None, "/politique-de-confidentialite", None, False, False),
    ("offre_2026", "Offre de rentrée 2026", "Back-to-school offer 2026", "offre-2026", None, "/offre-2026", None, True, False),
    ("ancien_accueil", "Ancien accueil (2023)", "Old home (2023)", "ancien-accueil", None, "/ancien-accueil", None, False, True),
    ("page_404", "Page introuvable", "Not found", "404", None, "/404", None, False, False),
)  # fmt: skip

_DOSSIERS: tuple[str, ...] = ("expertises", "ressources")


def _pages(
    seed: int,
    rng: random.Random,
    site_id: str,
    locales: dict[str, Any],
    collections: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Les pages dans la locale primaire, et leurs variantes anglaises.

    Même identifiant dans les deux : une page est UNE entité localisée, pas
    deux pages. Ce qui change : `title`, `seo`, `openGraph`, `localeId`, et
    `publishedPath` préfixé du sous-répertoire.
    """
    fr = locales["primary"]
    en = locales["secondary"][0]
    dossiers = {nom: oid(seed, "folder", nom) for nom in _DOSSIERS}
    creation = MISE_EN_LIGNE
    primaires: list[dict[str, Any]] = []
    anglaises: list[dict[str, Any]] = []
    for cle, titre_fr, titre_en, slug, dossier, chemin, gabarit, brouillon, archivee in _PAGES:
        page_id = oid(seed, "page", cle)
        cree = creation + timedelta(days=rng.randint(0, 400))
        cree_ts = _instant(rng, cree)
        maj_ts = _maj(rng, cree)
        base = {
            "id": page_id,
            "siteId": site_id,
            "slug": slug,
            "parentId": dossiers[dossier] if dossier else None,
            "collectionId": collections[gabarit] if gabarit else None,
            "createdOn": cree_ts,
            "lastUpdated": maj_ts,
            "archived": archivee,
            "draft": brouillon,
            "canBranch": not gabarit,
            "isBranch": False,
            "branchId": None,
        }
        primaires.append(
            {
                **base,
                "title": titre_fr,
                "seo": {
                    "title": f"{titre_fr} — Boréal Conseil",
                    "description": f"{titre_fr} : Boréal Conseil, ESN data, cloud et cybersécurité.",
                },
                "openGraph": {
                    "title": f"{titre_fr} — Boréal Conseil",
                    "titleCopied": True,
                    "description": f"{titre_fr} : Boréal Conseil, ESN data, cloud et cybersécurité.",
                    "descriptionCopied": True,
                },
                "localeId": fr["id"],
                "publishedPath": chemin,
            }
        )
        anglaises.append(
            {
                **base,
                "title": titre_en,
                "seo": {
                    "title": f"{titre_en} — Boréal Conseil",
                    "description": f"{titre_en}: Boréal Conseil, a data, cloud and security consultancy.",
                },
                "openGraph": {
                    "title": f"{titre_en} — Boréal Conseil",
                    "titleCopied": True,
                    "description": f"{titre_en}: Boréal Conseil, a data, cloud and security consultancy.",
                    "descriptionCopied": True,
                },
                "localeId": en["id"],
                "publishedPath": "/en" + ("" if chemin == "/" else chemin),
            }
        )
    return primaires, anglaises


def _champ(
    seed: int, collection: str, slug: str, nom: str, type_: str, *, requis: bool = False
) -> dict[str, Any]:
    return {
        "id": oid(seed, "field", collection, slug),
        "isRequired": requis,
        "isEditable": True,
        "type": type_,
        "displayName": nom,
        "slug": slug,
        "helpText": None,
        "validations": None,
    }


def _collections(seed: int, rng: random.Random) -> list[dict[str, Any]]:
    """Cinq collections, typées champ par champ. `name` et `slug` en tête,
    requis et non éditables en structure : ce sont les deux champs que Webflow
    impose à toute collection."""

    def base(cle: str) -> list[dict[str, Any]]:
        return [
            {**_champ(seed, cle, "name", "Name", "PlainText", requis=True), "isEditable": True},
            {**_champ(seed, cle, "slug", "Slug", "PlainText", requis=True), "isEditable": True},
        ]

    definitions: list[tuple[str, str, str, str, list[dict[str, Any]]]] = [
        (
            "articles",
            "Articles",
            "Article",
            "article",
            [
                _champ(seed, "articles", "resume", "Résumé", "PlainText", requis=True),
                _champ(seed, "articles", "corps", "Corps", "RichText"),
                _champ(
                    seed,
                    "articles",
                    "date-de-publication",
                    "Date de publication",
                    "DateTime",
                    requis=True,
                ),
                _champ(seed, "articles", "auteur", "Auteur", "Reference"),
                _champ(seed, "articles", "categorie", "Catégorie", "Option"),
                _champ(seed, "articles", "image-principale", "Image principale", "Image"),
                _champ(seed, "articles", "temps-de-lecture", "Temps de lecture (min)", "Number"),
            ],
        ),
        (
            "etudes",
            "Études de cas",
            "Étude de cas",
            "etude-de-cas",
            [
                _champ(seed, "etudes", "client", "Client", "PlainText", requis=True),
                _champ(seed, "etudes", "secteur", "Secteur", "Option"),
                _champ(seed, "etudes", "expertise", "Expertise", "Option"),
                _champ(seed, "etudes", "resume", "Résumé", "PlainText"),
                _champ(seed, "etudes", "resultats", "Résultats", "RichText"),
                _champ(seed, "etudes", "image-principale", "Image principale", "Image"),
            ],
        ),
        (
            "offres",
            "Offres d'emploi",
            "Offre d'emploi",
            "offre-emploi",
            [
                _champ(seed, "offres", "agence", "Agence", "Option", requis=True),
                _champ(seed, "offres", "pole", "Pôle", "Option", requis=True),
                _champ(seed, "offres", "type-de-contrat", "Type de contrat", "Option", requis=True),
                _champ(seed, "offres", "date-de-publication", "Date de publication", "DateTime"),
                _champ(seed, "offres", "description", "Description", "RichText"),
                _champ(seed, "offres", "reference-boond", "Référence BoondManager", "PlainText"),
                _champ(seed, "offres", "teletravail", "Télétravail possible", "Switch"),
            ],
        ),
        (
            "auteurs",
            "Auteurs",
            "Auteur",
            "auteur",
            [
                _champ(seed, "auteurs", "poste", "Poste", "PlainText"),
                _champ(seed, "auteurs", "agence", "Agence", "Option"),
                _champ(seed, "auteurs", "photo", "Photo", "Image"),
            ],
        ),
        (
            "evenements",
            "Événements",
            "Événement",
            "evenement",
            [
                _champ(seed, "evenements", "date", "Date", "DateTime", requis=True),
                _champ(seed, "evenements", "lieu", "Lieu", "PlainText"),
                _champ(seed, "evenements", "format", "Format", "Option"),
                _champ(seed, "evenements", "description", "Description", "RichText"),
                _champ(seed, "evenements", "lien-inscription", "Lien d'inscription", "Link"),
            ],
        ),
    ]
    collections: list[dict[str, Any]] = []
    for cle, nom, singulier, slug, champs in definitions:
        cree = MISE_EN_LIGNE + timedelta(days=rng.randint(0, 200))
        collections.append(
            {
                "id": oid(seed, "collection", cle),
                "displayName": nom,
                "singularName": singulier,
                "slug": slug,
                "createdOn": _instant(rng, cree),
                "lastUpdated": _maj(rng, cree),
                "fields": base(cle) + champs,
                # Clé interne — retirée avant de servir (cf. app._collection_servie).
                "_cle": cle,
            }
        )
    return collections


def _option(seed: int, collection: str, champ: str, valeur: str) -> str:
    """L'ID d'une option : dans `fieldData`, un champ `Option` vaut
    l'identifiant de l'option, pas son libellé."""
    return oid(seed, "option", collection, champ, valeur)


def _image(seed: int, cle: str, alt: str) -> dict[str, Any]:
    fichier = oid(seed, "asset", cle)
    return {
        "fileId": fichier,
        "url": f"https://cdn.prod.website-files.com/{oid(seed, 'site')}/{fichier}_{slugifier(alt)}.jpg",
        "alt": alt,
    }


def _element(  # noqa: PLR0917 — un constructeur de fixture porte ses parties
    seed: int,
    rng: random.Random,
    cle_collection: str,
    cle: str,
    nom: str,
    donnees: dict[str, Any],
    cms_locale: str,
    *,
    cree: date,
    brouillon: bool = False,
    archive: bool = False,
) -> dict[str, Any]:
    cree_ts = _instant(rng, cree)
    maj_ts = _maj(rng, cree)
    publie = None if brouillon else maj_ts
    return {
        "id": oid(seed, "item", cle_collection, cle),
        "cmsLocaleId": cms_locale,
        "lastPublished": publie,
        "lastUpdated": maj_ts,
        "createdOn": cree_ts,
        "isArchived": archive,
        "isDraft": brouillon,
        "fieldData": {"name": nom, "slug": slugifier(nom), **donnees},
    }


_TITRES_ARTICLES: tuple[tuple[str, str], ...] = (
    ("Industrialiser un modèle ML : les cinq erreurs qu'on voit partout", "Data & Analytics"),
    ("dbt en production : ce que trois ans de projets nous ont appris", "Data & Analytics"),
    ("Power BI et RLS : l'autorisation vit dans la base, pas dans le rapport", "Data & Analytics"),
    ("Kubernetes multi-tenant : cloisonner sans multiplier les clusters", "Cloud & Platform"),
    ("FinOps : lire une facture cloud comme un compte de résultat", "Cloud & Platform"),
    ("Zero trust en pratique : par où commencer", "Cybersécurité"),
    ("Pentest interne : ce que les rapports ne disent pas", "Cybersécurité"),
    ("Retour de l'équipe de Lyon sur le Devoxx 2026", "Vie d'agence"),
    ("Nos trois alternants racontent leur première année", "Vie d'agence"),
    ("Data contracts : la promesse et la pratique", "Data & Analytics"),
    ("Migrer un entrepôt on-premise vers le cloud en six mois", "Cloud & Platform"),
    ("NIS2 : ce qui change pour les ETI en 2026", "Cybersécurité"),
    ("Lakehouse ou entrepôt ? La question est mal posée", "Data & Analytics"),
    ("GitOps pour les données : versionner les pipelines comme du code", "Cloud & Platform"),
    ("Sécuriser une chaîne CI/CD : dix contrôles qui comptent", "Cybersécurité"),
    ("Boréal Conseil ouvre son agence de Nantes", "Vie d'agence"),
    ("Observabilité des pipelines : au-delà du CronJob vert", "Data & Analytics"),
    ("Sobriété numérique : mesurer avant de promettre", "Cloud & Platform"),
    ("SOC externalisé : lire un contrat de supervision", "Cybersécurité"),
    ("Semaine data : ce que nous retenons de l'édition 2026", "Événement"),
    ("Qualité de données : les tests qu'on ne désactive jamais", "Data & Analytics"),
    ("Landing zones : le socle avant les applications", "Cloud & Platform"),
    ("Phishing en 2026 : les campagnes que nos clients ont subies", "Cybersécurité"),
    ("Métriques d'engagement : ce que GA4 ne dit pas", "Data & Analytics"),
    ("Kubernetes : trois ans de mises à jour majeures sans coupure", "Cloud & Platform"),
    ("Gestion des secrets : pourquoi le .env n'est pas une stratégie", "Cybersécurité"),
    ("Bilan RSE 2025 : nos engagements et nos écarts", "Vie d'agence"),
    ("L'entrepôt analytique de Boréal : notre propre dogfooding", "Data & Analytics"),
    ("Spot instances et charges batch : le calcul qui rapporte", "Cloud & Platform"),
    ("RGPD et entrepôt de données : la minimisation à l'extraction", "Cybersécurité"),
    ("Meetup Power BI Lyon : les slides de mars", "Événement"),
    ("Modèle sémantique : un seul modèle, cinq périmètres", "Data & Analytics"),
    ("Cloud souverain : état des lieux 2026", "Cloud & Platform"),
    ("Red team : la mission dont on ne parle pas en public", "Cybersécurité"),
    ("Nos engagements salariés : télétravail, formation, parentalité", "Vie d'agence"),
    ("Streaming ou batch ? Le coût de la latence", "Data & Analytics"),
)

_ETUDES: tuple[tuple[str, str, str], ...] = (
    ("Lumina Retail", "Data & Analytics", "Un entrepôt unique pour 340 magasins"),
    ("Banque Hexagone", "Cybersécurité", "Programme zero trust sur trois entités"),
    ("Voltalis Énergie", "Cloud & Platform", "Migration de la supervision vers Kubernetes"),
    ("Mutuelle Armor", "Data & Analytics", "Reporting réglementaire automatisé"),
    ("TransEuropa Fret", "Cloud & Platform", "FinOps : -31 % sur la facture cloud"),
    ("Pharmadis", "Cybersécurité", "Mise en conformité NIS2 en neuf mois"),
    ("Citymob", "Data & Analytics", "Prévision de fréquentation temps réel"),
    ("Assurial", "Data & Analytics", "Modèle sémantique et RLS pour 1 200 utilisateurs"),
    ("Groupe Ardentes", "Cloud & Platform", "Landing zone multi-pays"),
    ("Banque Hexagone", "Data & Analytics", "Data contracts entre 14 équipes"),
    ("Voltalis Énergie", "Cybersécurité", "SOC externalisé et astreinte"),
    ("Lumina Retail", "Cloud & Platform", "GitOps pour 60 applications"),
)

_OFFRES: tuple[tuple[str, str, str, str, bool, bool], ...] = (
    ("Data Engineer confirmé", "Paris", "Data & Analytics", "CDI", False, False),
    ("Consultant BI Power BI", "Lyon", "Data & Analytics", "CDI", False, False),
    ("Architecte cloud senior", "Paris", "Cloud & Platform", "CDI", False, False),
    ("Ingénieur plateforme Kubernetes", "Nantes", "Cloud & Platform", "CDI", False, False),
    ("Pentester", "Paris", "Cybersécurité", "CDI", False, False),
    ("Analyste SOC", "Lyon", "Cybersécurité", "CDI", False, False),
    ("Chef de projet data", "Nantes", "Data & Analytics", "CDI", False, False),
    ("Alternance data engineering", "Lyon", "Data & Analytics", "Alternance", False, False),
    ("Stage cybersécurité — audit", "Paris", "Cybersécurité", "Stage", False, False),
    ("Stage cloud — FinOps", "Nantes", "Cloud & Platform", "Stage", False, False),
    ("Consultant MLOps", "Paris", "Data & Analytics", "CDD", False, False),
    ("Responsable d'agence Nantes", "Nantes", "Cloud & Platform", "CDI", False, True),
    ("Data Analyst", "Lyon", "Data & Analytics", "CDI", False, True),
    ("Ingénieur sécurité cloud", "Paris", "Cybersécurité", "CDI", True, False),
)

_AUTEURS: tuple[tuple[str, str, str], ...] = (
    ("Camille Rousset", "Directrice Data & Analytics", "Paris"),
    ("Yanis Belkacem", "Architecte cloud", "Lyon"),
    ("Inès Marchand", "Responsable cybersécurité", "Paris"),
    ("Thomas Guérin", "Responsable d'agence", "Nantes"),
    ("Léa Fournier", "Consultante BI", "Lyon"),
    ("Mehdi Haddad", "Data Engineer", "Nantes"),
)

_EVENEMENTS: tuple[tuple[str, date, str, str], ...] = (
    ("Meetup Power BI Lyon — mars", date(2026, 3, 12), "Lyon, agence Boréal", "Meetup"),
    ("Webinar : industrialiser le ML", date(2026, 4, 9), "En ligne", "Webinar"),
    ("Salon Big Data & AI Paris", date(2026, 4, 22), "Paris, Porte de Versailles", "Salon"),
    (
        "Petit-déjeuner NIS2 pour les ETI",
        date(2026, 5, 20),
        "Paris, agence Boréal",
        "Petit-déjeuner",
    ),
    ("Webinar : FinOps en pratique", date(2026, 6, 4), "En ligne", "Webinar"),
    ("Meetup Kubernetes Nantes", date(2026, 6, 25), "Nantes, agence Boréal", "Meetup"),
    ("Webinar : Power BI et RLS", date(2026, 9, 17), "En ligne", "Webinar"),
    ("Salon Cyber Lille", date(2026, 10, 8), "Lille, Grand Palais", "Salon"),
)


def _elements(
    seed: int, rng: random.Random, collections: list[dict[str, Any]], cms_locale: str
) -> dict[str, list[dict[str, Any]]]:
    par_cle = {c["_cle"]: c["id"] for c in collections}
    resultat: dict[str, list[dict[str, Any]]] = {}

    auteurs = [
        _element(
            seed, rng, "auteurs", f"a{i}", nom,
            {
                "poste": poste,
                "agence": _option(seed, "auteurs", "agence", agence),
                "photo": _image(seed, f"auteur-{i}", nom),
            },
            cms_locale, cree=MISE_EN_LIGNE + timedelta(days=rng.randint(0, 30)),
        )
        for i, (nom, poste, agence) in enumerate(_AUTEURS)
    ]  # fmt: skip
    resultat[par_cle["auteurs"]] = auteurs

    articles: list[dict[str, Any]] = []
    debut = MISE_EN_LIGNE + timedelta(days=20)
    for i, (titre, categorie) in enumerate(_TITRES_ARTICLES):
        # Un article toutes les ~3 semaines, les derniers en brouillon.
        publie_le = debut + timedelta(days=int(i * 23.5) + rng.randint(0, 4))
        # Les deux derniers sont en BROUILLON : rédigés, pas publiés. Ils
        # sortent de `/items` et pas de `/items/live` — c'est l'écart que le
        # consommateur doit connaître.
        brouillon = publie_le > DERNIERE_MAJ or i >= len(_TITRES_ARTICLES) - 2
        archive = i in (3, 8)  # deux articles retirés (refonte, événement passé)
        cree = min(publie_le - timedelta(days=rng.randint(3, 12)), DERNIERE_MAJ)
        auteur = rng.choice(auteurs)
        articles.append(
            _element(
                seed, rng, "articles", f"p{i}", titre,
                {
                    "resume": f"{titre}. Retour d'expérience de l'équipe {categorie}.",
                    "corps": f"<h2>{titre}</h2><p>Le texte complet de l'article, en HTML.</p>",
                    "date-de-publication": _dt(min(publie_le, DERNIERE_MAJ), 8, 30),
                    "auteur": auteur["id"],
                    "categorie": _option(seed, "articles", "categorie", categorie),
                    "image-principale": _image(seed, f"article-{i}", titre),
                    "temps-de-lecture": rng.randint(3, 12),
                },
                cms_locale, cree=cree, brouillon=brouillon, archive=archive,
            )
        )  # fmt: skip
    resultat[par_cle["articles"]] = articles

    etudes = [
        _element(
            seed, rng, "etudes", f"e{i}", titre,
            {
                "client": client,
                "secteur": _option(
                    seed, "etudes", "secteur", next(s for n, s, _ in CLIENTS if n == client)
                ),
                "expertise": _option(seed, "etudes", "expertise", expertise),
                "resume": f"{client} — {titre}.",
                "resultats": "<ul><li>Résultat 1</li><li>Résultat 2</li></ul>",
                "image-principale": _image(seed, f"etude-{i}", client),
            },
            cms_locale, cree=MISE_EN_LIGNE + timedelta(days=40 + i * 55),
        )
        for i, (client, expertise, titre) in enumerate(_ETUDES)
    ]  # fmt: skip
    resultat[par_cle["etudes"]] = etudes

    offres: list[dict[str, Any]] = []
    for i, (titre, agence, pole, contrat, brouillon, archive) in enumerate(_OFFRES):
        cree = date(2026, 1, 12) + timedelta(days=i * 11)
        offres.append(
            _element(
                seed, rng, "offres", f"o{i}", titre,
                {
                    "agence": _option(seed, "offres", "agence", agence),
                    "pole": _option(seed, "offres", "pole", pole),
                    "type-de-contrat": _option(seed, "offres", "type-de-contrat", contrat),
                    "date-de-publication": _dt(cree, 9, 0),
                    "description": f"<p>{titre} — {agence}, pôle {pole}.</p>",
                    # La référence de l'offre côté BoondManager : le pont entre
                    # les deux mondes, comme `reference-boond` chez les autres.
                    "reference-boond": f"BM-{2026}-{100 + i:03d}",
                    "teletravail": contrat != "Stage",
                },
                cms_locale, cree=cree, brouillon=brouillon, archive=archive,
            )
        )  # fmt: skip
    resultat[par_cle["offres"]] = offres

    evenements = [
        _element(
            seed, rng, "evenements", f"v{i}", titre,
            {
                "date": _dt(jour, 18 if fmt != "Petit-déjeuner" else 8, 30),
                "lieu": lieu,
                "format": _option(seed, "evenements", "format", fmt),
                "description": f"<p>{titre}, {lieu}.</p>",
                "lien-inscription": f"https://www.boreal-conseil.example/evenements/{slugifier(titre)}",
            },
            cms_locale, cree=jour - timedelta(days=rng.randint(30, 60)),
        )
        for i, (titre, jour, lieu, fmt) in enumerate(_EVENEMENTS)
    ]  # fmt: skip
    resultat[par_cle["evenements"]] = evenements
    return resultat


#: (clé, nom, page, champs (displayName → type), volume hebdomadaire moyen)
_FORMULAIRES: tuple[tuple[str, str, str, tuple[tuple[str, str], ...], float], ...] = (
    (
        "contact",
        "Contact",
        "contact",
        (
            ("Prénom", "Plain"),
            ("Nom", "Plain"),
            ("Email", "Email"),
            ("Société", "Plain"),
            ("Téléphone", "Phone"),
            ("Sujet", "Plain"),
            ("Message", "Plain"),
            ("Consentement", "Plain"),
        ),
        3.2,
    ),
    ("newsletter", "Newsletter", "accueil", (("Email", "Email"),), 5.5),
    (
        "candidature",
        "Candidature spontanée",
        "carrieres",
        (
            ("Prénom", "Plain"),
            ("Nom", "Plain"),
            ("Email", "Email"),
            ("Téléphone", "Phone"),
            ("Poste souhaité", "Plain"),
            ("Message", "Plain"),
        ),
        2.1,
    ),
    (
        "lb_mlops",
        "Téléchargement — Industrialiser le ML",
        "lb_mlops",
        (
            ("Prénom", "Plain"),
            ("Nom", "Plain"),
            ("Email professionnel", "Email"),
            ("Société", "Plain"),
            ("Fonction", "Plain"),
        ),
        3.8,
    ),
    (
        "lb_cyber",
        "Téléchargement — Sécuriser le cloud",
        "lb_cyber",
        (
            ("Prénom", "Plain"),
            ("Nom", "Plain"),
            ("Email professionnel", "Email"),
            ("Société", "Plain"),
            ("Fonction", "Plain"),
        ),
        2.4,
    ),
    (
        "evenement",
        "Inscription événement",
        "evenement_gabarit",
        (
            ("Prénom", "Plain"),
            ("Nom", "Plain"),
            ("Email", "Email"),
            ("Société", "Plain"),
            ("Événement", "Plain"),
        ),
        0.0,  # Les inscriptions arrivent par SALVES autour des événements.
    ),
)


def _formulaires(
    seed: int, rng: random.Random, site: dict[str, Any], pages: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    par_cle = {cle: page for (cle, *_), page in zip(_PAGES, pages, strict=True)}
    formulaires: list[dict[str, Any]] = []
    for cle, nom, page_cle, champs, _ in _FORMULAIRES:
        page = par_cle[page_cle]
        cree = MISE_EN_LIGNE + timedelta(days=rng.randint(0, 120))
        formulaires.append(
            {
                "id": oid(seed, "form", cle),
                "displayName": nom,
                "siteId": site["id"],
                "siteDomainId": site["customDomains"][0]["id"],
                "pageId": page["id"],
                "pageName": page["title"],
                "formElementId": _uuid(seed, "formelement", cle),
                "workspaceId": site["workspaceId"],
                "createdOn": _instant(rng, cree),
                "lastUpdated": _maj(rng, cree),
                "fields": {
                    oid(seed, "formfield", cle, nom_champ): {
                        "displayName": nom_champ,
                        "type": type_,
                        "placeholder": None,
                        "userVisible": True,
                    }
                    for nom_champ, type_ in champs
                },
                "responseSettings": {
                    "redirectUrl": f"https://{settings.site_domain}/merci",
                    "redirectMethod": "GET",
                    "redirectAction": None,
                    "sendEmailConfirmation": cle in {"lb_mlops", "lb_cyber", "evenement"},
                },
                "_cle": cle,
            }
        )
    return formulaires


def _uuid(seed: int, *parties: object) -> str:
    """Un UUID dérivé de la graine — `formElementId` en a la forme."""
    h = hashlib.sha1(":".join(str(p) for p in (seed, *parties)).encode(), usedforsecurity=False)
    x = h.hexdigest()
    return f"{x[:8]}-{x[8:12]}-4{x[13:16]}-{x[16:20]}-{x[20:32]}"


def personne(rng: random.Random) -> tuple[str, str, str, str | None]:
    """(prénom, nom, e-mail, société ou None) — une personne FICTIVE.

    Le domaine de l'e-mail dit d'où elle écrit : une entreprise du monde
    partagé, une entreprise prospect, ou un domaine générique — et c'est la
    seule chose qu'un consommateur analytique a besoin d'en garder.
    """
    prenom, nom = rng.choice(PRENOMS), rng.choice(NOMS)
    tirage = rng.random()
    if tirage < 0.22:
        societe, _, domaine = rng.choice(CLIENTS)
    elif tirage < 0.55:
        domaine = rng.choice(DOMAINES_PROSPECTS)
        societe = domaine.split(".")[0].replace("-", " ").title()
    else:
        domaine = rng.choice(DOMAINES_GENERIQUES)
        societe = None
    local = f"{slugifier(prenom)}.{slugifier(nom)}"
    return prenom, nom, f"{local}@{domaine}", societe


def reponse_formulaire(
    rng: random.Random, cle_formulaire: str, evenements: list[dict[str, Any]]
) -> dict[str, Any]:
    """Le `formResponse` d'une soumission, clé par `displayName`."""
    prenom, nom, email, societe = personne(rng)
    if cle_formulaire == "newsletter":
        return {"Email": email}
    if cle_formulaire == "contact":
        return {
            "Prénom": prenom,
            "Nom": nom,
            "Email": email,
            "Société": societe or "",
            "Téléphone": f"+33 6 {rng.randint(10, 99)} {rng.randint(10, 99)} {rng.randint(10, 99)} {rng.randint(10, 99)}",
            "Sujet": rng.choice(SUJETS_CONTACT),
            "Message": "Bonjour, nous souhaitons échanger sur un besoin de renfort.",
            "Consentement": "on",
        }
    if cle_formulaire == "candidature":
        return {
            "Prénom": prenom,
            "Nom": nom,
            "Email": email,
            "Téléphone": f"+33 7 {rng.randint(10, 99)} {rng.randint(10, 99)} {rng.randint(10, 99)} {rng.randint(10, 99)}",
            "Poste souhaité": rng.choice(POSTES_SOUHAITES),
            "Message": "Je vous adresse ma candidature spontanée.",
        }
    if cle_formulaire in {"lb_mlops", "lb_cyber"}:
        return {
            "Prénom": prenom,
            "Nom": nom,
            "Email professionnel": email,
            "Société": societe or "",
            "Fonction": rng.choice(FONCTIONS),
        }
    evenement = rng.choice(evenements)["fieldData"]["name"] if evenements else "Événement"
    return {
        "Prénom": prenom,
        "Nom": nom,
        "Email": email,
        "Société": societe or "",
        "Événement": evenement,
    }


def _soumissions(  # noqa: PLR0917 — idem
    seed: int,
    rng: random.Random,
    site: dict[str, Any],
    locales: dict[str, Any],
    formulaires: list[dict[str, Any]],
    evenements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Les soumissions de l'année, semaine par semaine.

    Un volume hebdomadaire moyen par formulaire, tiré en Poisson approché ;
    les inscriptions aux événements arrivent par salves dans les trois
    semaines qui précèdent chaque événement. Environ 12 % des soumissions
    viennent de la locale anglaise (`localeId` renseigné) ; les autres ont
    `localeId: null` — c'est la locale primaire, pas une valeur manquante.
    """
    en = locales["secondary"][0]["id"]
    soumissions: list[dict[str, Any]] = []
    numero = 0
    jour = DEBUT_SOUMISSIONS
    while jour <= DERNIERE_MAJ:
        for formulaire in formulaires:
            cle = formulaire["_cle"]
            moyenne = next(v for k, *_, v in _FORMULAIRES if k == cle)
            if cle == "evenement":
                # Salve : 4 à 9 inscriptions par semaine dans les 3 semaines
                # avant un événement du jeu.
                proches = [
                    e for e in evenements
                    if 0 <= (date.fromisoformat(e["fieldData"]["date"][:10]) - jour).days <= 21
                ]  # fmt: skip
                nombre = rng.randint(4, 9) if proches else 0
            else:
                nombre = max(0, round(rng.gauss(moyenne, moyenne**0.5)))
            for _ in range(nombre):
                quand = jour + timedelta(days=rng.randint(0, 6))
                if quand > DERNIERE_MAJ:
                    continue
                numero += 1
                anglaise = rng.random() < 0.12
                soumissions.append(
                    {
                        "id": oid(seed, "submission", numero),
                        "displayName": formulaire["displayName"],
                        "siteId": site["id"],
                        "workspaceId": site["workspaceId"],
                        "dateSubmitted": _instant(rng, quand, ouvre=False),
                        "formResponse": reponse_formulaire(rng, cle, evenements),
                        "localeId": en if anglaise else None,
                        "formId": formulaire["id"],
                    }
                )
        jour += timedelta(days=7)
    soumissions.sort(key=lambda s: s["dateSubmitted"], reverse=True)
    return soumissions


def _utilisateur(seed: int) -> dict[str, Any]:
    return {
        "id": oid(seed, "user"),
        "email": "marketing@boreal-conseil.example",
        "firstName": "Marketing",
        "lastName": "Boréal Conseil",
    }


def _autorisation(seed: int, site: dict[str, Any], utilisateur: dict[str, Any]) -> dict[str, Any]:
    return {
        "authorization": {
            "id": oid(seed, "authorization"),
            "createdOn": _dt(date(2026, 6, 2), 14, 3, 51, 208),
            "lastUsed": _dt(DERNIERE_MAJ, 4, 0, 12, 47),
            "grantType": "authorization_code",
            "rateLimit": settings.rate_limit,
            # Une CHAÎNE séparée par des virgules, pas un tableau.
            "scope": ",".join(sorted(settings.scopes)),
            "authorizedTo": {
                "siteIds": [site["id"]],
                "workspaceIds": [site["workspaceId"]],
                "userIds": [utilisateur["id"]],
            },
        },
        "application": {
            "id": oid(seed, "application"),
            "description": "Extraction analytique insights360",
            "homepage": "https://insights360.diametral.example",
            "displayName": "insights360",
        },
    }


# ── Assemblage ───────────────────────────────────────────────────────────────


def build_realiste_dataset(seed: int = 42) -> dict[str, Any]:
    rng = random.Random(seed)
    locales = _locales(seed)
    site = _site(seed, locales)
    collections = _collections(seed, rng)
    par_cle = {c["_cle"]: c["id"] for c in collections}
    pages, pages_en = _pages(seed, rng, site["id"], locales, par_cle)
    elements = _elements(seed, rng, collections, locales["primary"]["cmsLocaleId"])
    evenements = elements[par_cle["evenements"]]
    formulaires = _formulaires(seed, rng, site, pages)
    soumissions = _soumissions(seed, rng, site, locales, formulaires, evenements)
    utilisateur = _utilisateur(seed)
    return {
        "sites": [site],
        "pages": pages,
        "pages_en": pages_en,
        "collections": collections,
        # collection_id → éléments PRÉPARÉS (brouillons et archivés compris).
        "items": elements,
        "forms": formulaires,
        "form_submissions": soumissions,
        "authorized_user": utilisateur,
        "introspection": _autorisation(seed, site, utilisateur),
    }
