"""Pagination par offset — le sixième dialecte de pagination de l'écosystème.

    {"pages": [...], "pagination": {"limit": 100, "offset": 0, "total": 23}}

À comparer aux cinq autres mocks : `page`/`maxResults` chez BoondManager,
`@odata.nextLink` chez Graph, `start`/`count` Rest.li chez LinkedIn,
`limit`/`offset` chez GA4 (mais SANS total), curseur opaque chez Pennylane. Un
connecteur qui aurait « une » boucle de pagination générique se casse ici, et
c'est le but.

┌─ QUATRE PIÈGES REPRODUITS EXPRÈS ───────────────────────────────────────────┐
│ 1. LA CLÉ DE LA LISTE CHANGE À CHAQUE RESSOURCE : `sites`, `pages`,          │
│    `collections`, `items`, `forms`, `formSubmissions`, `customDomains`.      │
│    Il n'y a pas de clé `items` universelle — `items` n'est que celle du CMS. │
│                                                                              │
│ 2. TROIS LISTES NE SONT PAS PAGINÉES DU TOUT. `/sites`,                      │
│    `/sites/{id}/collections` et `/sites/{id}/custom_domains` rendent la      │
│    liste entière SANS clé `pagination`. Un consommateur qui lit              │
│    `body["pagination"]["total"]` sans garde lève un KeyError sur la toute    │
│    première route qu'il appelle.                                             │
│                                                                              │
│ 3. L'OFFSET DÉRIVE SUR UNE LISTE QUI VIT. Les soumissions sont servies de la │
│    plus récente à la plus ancienne ; une soumission arrivée entre deux pages │
│    décale tout d'un cran et la dernière ligne de la page N revient en tête   │
│    de la page N+1. Ni erreur, ni avertissement : un doublon. C'est la        │
│    propriété structurelle d'une pagination par offset, et `page_drift`       │
│    l'injecte à la demande pour qu'un consommateur la rencontre en test.      │
│                                                                              │
│ 4. `limit` HORS BORNES REND 400. Le fournisseur documente « max limit: 100 » │
│    sans dire ce qu'il fait au-delà ; refuser est le côté sûr de l'erreur     │
│    (cf. docs/UNVERIFIED-FIELDS.md). Un plafond silencieux ferait croire à   │
│    un pipeline qu'il a demandé 5000 lignes et tout reçu.                     │
└──────────────────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from typing import Any

from .settings import settings


class ParametreInvalide(ValueError):
    """`limit` ou `offset` illisible ou hors bornes → 400 `validation_error`."""


def limite_demandee(brut: str | None) -> int:
    """Valide `limit` et rend la valeur effective. Défaut 100, bornes 1..100."""
    plafond = settings.limite_max
    if brut is None or brut == "":
        return settings.limite_defaut
    try:
        valeur = int(brut)
    except ValueError as exc:
        raise ParametreInvalide(f"limit must be an integer between 1 and {plafond}") from exc
    if valeur < 1 or valeur > plafond:
        raise ParametreInvalide(f"limit must be between 1 and {plafond}") from None
    return valeur


def offset_demande(brut: str | None) -> int:
    if brut is None or brut == "":
        return 0
    try:
        valeur = int(brut)
    except ValueError as exc:
        raise ParametreInvalide("offset must be a non-negative integer") from exc
    if valeur < 0:
        raise ParametreInvalide("offset must be a non-negative integer")
    return valeur


def paginer(
    elements: list[dict[str, Any]], *, cle: str, limite: int, offset: int
) -> dict[str, Any]:
    """Découpe une liste DÉJÀ triée et filtrée en une page du dialecte.

    `total` est le nombre d'éléments de la liste ENTIÈRE, pas de la page : c'est
    ce qui permet à un consommateur de savoir quand s'arrêter — et ce qui le
    trompe si la liste bouge entre deux appels (cf. l'encadré du module). Un
    offset au-delà du total n'est pas une erreur : la page est vide.
    """
    page = elements[offset : offset + limite]
    return {cle: page, "pagination": {"limit": limite, "offset": offset, "total": len(elements)}}
