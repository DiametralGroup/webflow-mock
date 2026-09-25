"""L'évolution du jeu de données dans le temps — pour l'extraction incrémentale.

Le site VIT : un événement scripté par intervalle (60 s par défaut). C'est ce
qui rend éprouvable la seule propriété qui compte pour un connecteur
incrémental — « une deuxième extraction ne recharge QUE ce qui a bougé » — et
qui permet de vérifier qu'il se termine bien sur `total` au lieu de recharger
l'univers à chaque passage.

┌─ DÉTERMINISME ──────────────────────────────────────────────────────────────┐
│ L'événement k tire son aléa de `Random(f"{seed}:{k}")` et son horodatage     │
│ vaut TOUJOURS `EPOQUE + (k+1) x intervalle`. Deux exécutions du même mock,   │
│ avancées du même nombre d'événements, produisent le même monde — sans quoi   │
│ un test d'incrémentalité ne serait pas rejouable.                            │
│                                                                              │
│ `avancer()` est idempotent et protégé par un verrou : les handlers FastAPI   │
│ tournent dans un pool de threads, et deux requêtes simultanées feraient      │
│ sinon avancer la chronologie deux fois pour le même pas.                     │
└──────────────────────────────────────────────────────────────────────────────┘

┌─ CE QUI BOUGE SUR UN SITE VITRINE ──────────────────────────────────────────┐
│ Surtout des SOUMISSIONS : c'est le flux, et c'est ce qu'un consommateur      │
│ charge à chaque run. Une soumission nouvelle arrive EN TÊTE de la liste      │
│ (tri décroissant) — et décale d'un cran tout ce qui suit : c'est la dérive   │
│ d'offset, et elle n'est pas injectée ici, elle est simplement vraie.        │
│ Puis le contenu : un article rédigé, puis publié (le `lastPublished` du site │
│ bouge avec lui), une page retouchée, un élément mis à jour.                  │
└──────────────────────────────────────────────────────────────────────────────┘

Pour figer le monde — le gate d'idempotence d'insights360 compare `raw` entre
deux exécutions et ne peut pas vivre avec un jeu qui bouge — poser
`WEBFLOW_MOCK_EVOLUTION_ENABLED=false`.
"""

from __future__ import annotations

import random
import threading
from datetime import UTC, datetime, timedelta
from typing import Any

from .dataset.realiste import (
    _TITRES_ARTICLES,
    _image,
    _option,
    horodatage,
    oid,
    slugifier,
    soumission,
)
from .settings import settings

#: L'origine de la chronologie. Postérieure à `DERNIERE_MAJ` du jeu de base
#: (2026-07-12) : un curseur posé sur le jeu de base rend zéro ligne, et le
#: PREMIER événement d'évolution est le premier changement qu'il verra.
EPOQUE = datetime(2026, 7, 15, 9, 0, 0, tzinfo=UTC)

#: Le cycle des événements. Six pas, puis on recommence — mais les entités
#: touchées, elles, avancent : le septième événement n'est pas le premier.
CYCLE: tuple[str, ...] = (
    "nouvelle_soumission",
    "maj_page",
    "nouvel_article_brouillon",
    "publication_article",
    "nouvelle_candidature",
    "maj_element",
)


def _instant(texte: str) -> datetime:
    quand = datetime.fromisoformat(texte.replace("Z", "+00:00"))
    return quand if quand.tzinfo else quand.replace(tzinfo=UTC)


def maintenant_virtuel(rang: int) -> datetime:
    """L'instant de référence du mock — l'ancre du jeu de données, pas `now()`.

    Elle avance avec la chronologie d'évolution : chaque événement vaut
    `EPOQUE + (k+1) x intervalle`, donc le « maintenant » d'un mock qui a joué
    N événements est `EPOQUE + N x intervalle`.
    """
    return EPOQUE + timedelta(seconds=settings.evolution_interval * rang)


def horodatage_de_mutation(elements: list[dict[str, Any]]) -> str:
    """Un horodatage STRICTEMENT au-dessus de tous ceux de la collection.

    Il doit passer au-dessus de tout, sinon un curseur posé avant la mutation
    ne la verrait pas — et rester dans le TEMPS DU MOCK, pas celui de
    l'horloge murale, pour que la suite reste rejouable quel que soit le jour.
    """
    from .state import state

    dernier = max(
        (
            e[cle]
            for e in elements
            if isinstance(e, dict)
            for cle in ("lastUpdated", "dateSubmitted")
            if cle in e
        ),
        default="",
    )
    candidat = maintenant_virtuel(state.evolution.rang)
    if dernier and horodatage(candidat) <= dernier:
        candidat = _instant(dernier) + timedelta(seconds=1)
    return horodatage(candidat)


class Evolution:
    """La chronologie. `avancer()` la fait progresser jusqu'à l'instant donné."""

    def __init__(self, seed: int, depart: float) -> None:
        self.seed = seed
        self.depart = depart
        self.rang = 0
        self.journal: list[dict[str, Any]] = []
        self._verrou = threading.Lock()

    # ── Progression ──────────────────────────────────────────────────────────

    def pas_attendus(self, maintenant: float) -> int:
        if not settings.evolution_enabled or settings.evolution_interval <= 0:
            return 0
        ecoule = max(0.0, maintenant - self.depart)
        return int(ecoule // settings.evolution_interval)

    def avancer(self, donnees: dict[str, Any], maintenant: float) -> bool:
        """Applique les événements dus. Rend True si le monde a bougé."""
        with self._verrou:
            cible = self.pas_attendus(maintenant)
            if cible <= self.rang:
                return False
            for k in range(self.rang, cible):
                self._appliquer(donnees, k)
            self.rang = cible
            return True

    def forcer(self, donnees: dict[str, Any], pas: int = 1) -> None:
        """Avance de `pas` événements, quelle que soit l'horloge — le levier
        de `/__admin/evolve`, pour un test qui ne veut pas manipuler le temps."""
        with self._verrou:
            for k in range(self.rang, self.rang + pas):
                self._appliquer(donnees, k)
            self.rang += pas

    # ── Les événements ───────────────────────────────────────────────────────

    def _appliquer(self, donnees: dict[str, Any], k: int) -> None:
        genre = CYCLE[k % len(CYCLE)]
        rng = random.Random(f"{self.seed}:{k}")
        quand = EPOQUE + timedelta(seconds=settings.evolution_interval * (k + 1))
        stamp = horodatage(quand)

        applique = getattr(self, f"_evt_{genre}")
        detail = applique(donnees, rng, stamp, k)
        self.journal.append({"rang": k, "genre": genre, "quand": stamp, **detail})

    def _collection(self, donnees: dict[str, Any], cle: str) -> dict[str, Any]:
        return next(c for c in donnees["collections"] if c["_cle"] == cle)

    def _soumettre(
        self, donnees: dict[str, Any], rng: random.Random, stamp: str, k: int, cle_formulaire: str
    ) -> dict[str, Any]:
        formulaire = next(f for f in donnees["forms"] if f["_cle"] == cle_formulaire)
        site = donnees["sites"][0]
        evenements = donnees["items"][self._collection(donnees, "evenements")["id"]]
        en = site["locales"]["secondary"][0]["id"]
        nouvelle = soumission(
            self.seed,
            rng,
            oid(self.seed, "submission-evolution", k),
            site,
            formulaire,
            stamp,
            en if rng.random() < 0.12 else None,
            evenements,
        )
        # EN TÊTE : le tri est décroissant, et c'est ce qui fait dériver
        # l'offset d'un consommateur en train de paginer.
        donnees["form_submissions"].insert(0, nouvelle)
        return {"soumission": nouvelle["id"], "formulaire": formulaire["displayName"]}

    def _evt_nouvelle_soumission(
        self, donnees: dict[str, Any], rng: random.Random, stamp: str, k: int
    ) -> dict[str, Any]:
        cle = rng.choice(("contact", "newsletter", "lb_mlops", "lb_cyber", "contact"))
        return self._soumettre(donnees, rng, stamp, k, cle)

    def _evt_nouvelle_candidature(
        self, donnees: dict[str, Any], rng: random.Random, stamp: str, k: int
    ) -> dict[str, Any]:
        return self._soumettre(donnees, rng, stamp, k, "candidature")

    def _evt_maj_page(
        self, donnees: dict[str, Any], rng: random.Random, stamp: str, k: int
    ) -> dict[str, Any]:
        del k
        candidates = [p for p in donnees["pages"] if not p["archived"] and not p["draft"]]
        page = rng.choice(candidates)
        page["lastUpdated"] = stamp
        # La variante anglaise porte le MÊME identifiant : elle bouge avec.
        for variante in donnees["pages_en"]:
            if variante["id"] == page["id"]:
                variante["lastUpdated"] = stamp
        donnees["sites"][0]["lastUpdated"] = stamp
        return {"page": page["id"], "titre": page["title"]}

    def _evt_nouvel_article_brouillon(
        self, donnees: dict[str, Any], rng: random.Random, stamp: str, k: int
    ) -> dict[str, Any]:
        collection = self._collection(donnees, "articles")
        articles = donnees["items"][collection["id"]]
        auteurs = donnees["items"][self._collection(donnees, "auteurs")["id"]]
        titre_base, categorie = _TITRES_ARTICLES[k % len(_TITRES_ARTICLES)]
        titre = f"{titre_base} (suite {k})"
        article = {
            "id": oid(self.seed, "item-evolution", "articles", k),
            "cmsLocaleId": donnees["sites"][0]["locales"]["primary"]["cmsLocaleId"],
            "lastPublished": None,
            "lastUpdated": stamp,
            "createdOn": stamp,
            "isArchived": False,
            "isDraft": True,
            "fieldData": {
                "name": titre,
                "slug": slugifier(titre),
                "resume": f"{titre}. Brouillon en cours de rédaction.",
                "corps": f"<h2>{titre}</h2><p>Brouillon.</p>",
                "date-de-publication": stamp,
                "auteur": rng.choice(auteurs)["id"],
                "categorie": _option(self.seed, "articles", "categorie", categorie),
                "image-principale": _image(self.seed, f"article-evolution-{k}", titre),
                "temps-de-lecture": rng.randint(3, 12),
            },
        }
        articles.append(article)
        collection["lastUpdated"] = stamp
        return {"article": article["id"], "titre": titre}

    def _evt_publication_article(
        self, donnees: dict[str, Any], rng: random.Random, stamp: str, k: int
    ) -> dict[str, Any]:
        del rng, k
        collection = self._collection(donnees, "articles")
        articles = donnees["items"][collection["id"]]
        brouillons = [a for a in articles if a["isDraft"] and not a["isArchived"]]
        if not brouillons:
            return {"article": None}
        article = min(brouillons, key=lambda a: a["createdOn"])
        article["isDraft"] = False
        article["lastPublished"] = stamp
        article["lastUpdated"] = stamp
        # Publier un élément publie le SITE : `lastPublished` bouge aussi.
        site = donnees["sites"][0]
        site["lastPublished"] = stamp
        for domaine in site["customDomains"]:
            domaine["lastPublished"] = stamp
        return {"article": article["id"], "titre": article["fieldData"]["name"]}

    def _evt_maj_element(
        self, donnees: dict[str, Any], rng: random.Random, stamp: str, k: int
    ) -> dict[str, Any]:
        del k
        cle = rng.choice(("offres", "etudes", "evenements"))
        collection = self._collection(donnees, cle)
        elements = [e for e in donnees["items"][collection["id"]] if not e["isArchived"]]
        element = rng.choice(elements)
        element["lastUpdated"] = stamp
        if not element["isDraft"]:
            element["lastPublished"] = stamp
        return {"collection": cle, "element": element["id"]}
