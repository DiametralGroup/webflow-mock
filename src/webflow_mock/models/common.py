"""Modèles de base — la pagination, l'erreur, et les marqueurs d'honnêteté.

La source de vérité de ce mock est la **référence officielle de la Data API
v2** (https://developers.webflow.com/data/reference, chaque page disponible en
Markdown en lui ajoutant `.md` — relevé le 2026-09-24). Tout ce qui en vient
est attesté. Tout le reste est marqué.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def unverified(description: str) -> dict[str, Any]:
    """Marque un champ dont le nom, la forme ou les valeurs ne sont PAS attestés.

    À utiliser via `json_schema_extra`. Tout champ ainsi marqué DOIT figurer
    dans `docs/UNVERIFIED-FIELDS.md` — `tests/test_contract_is_current.py` le
    vérifie.
    """
    return {"x-webflow-confidence": "unverified", "x-webflow-note": description}


def invented(description: str) -> dict[str, Any]:
    """Marque un champ ou un comportement qui n'existe PAS chez Webflow."""
    return {"x-webflow-confidence": "invented", "x-webflow-note": description}


class Permissif(BaseModel):
    """Base commune : les champs inconnus passent au lieu d'être rejetés.

    Un modèle strict transformerait chaque évolution de l'API réelle en panne
    du mock. Les modèles décrivent ce qui est émis, pas tout ce que Webflow
    peut exposer.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class Pagination(BaseModel):
    """`{"limit", "offset", "total"}` — l'objet de pagination.

    `total` est le nombre d'éléments de la liste ENTIÈRE. C'est ce qui permet
    de savoir quand s'arrêter (`offset + limit >= total`), et c'est ce qui
    trompe quand la liste bouge entre deux appels : une soumission arrivée en
    tête décale tout d'un cran, et la dernière ligne de la page N revient en
    tête de la page N+1. Ni erreur, ni avertissement — un doublon.
    """

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(description="La taille de page appliquée (défaut 100).")
    offset: int = Field(description="Le décalage appliqué (défaut 0).")
    total: int = Field(description="Le nombre TOTAL d'éléments, toutes pages confondues.")


class ErreurWebflow(Permissif):
    """Le corps d'erreur — quatre clés, sur TOUTE la surface, 429 compris.

    C'est ce qui distingue Webflow de Pennylane : ici le 429 est du JSON
    comme les autres. Le piège n'est pas la forme, c'est `Retry-After` : il
    vaut typiquement 60 secondes, et un client qui l'ignore rejoue dans la
    même minute et se fait limiter à nouveau.
    """

    message: str = Field(description="Message lisible.")
    code: str = Field(
        description=(
            "Code machine : `not_authorized`, `missing_scopes`, `resource_not_found`, "
            "`forms_require_republish`, `too_many_requests`, `validation_error`, "
            "`internal_error`…"
        )
    )
    externalReference: str | None = Field(default=None, description="Lien vers plus d'information.")
    details: list[Any] = Field(default_factory=list, description="Détails supplémentaires.")


#: Réutilisé sur chaque route (`responses=REPONSES_ERREUR`) : sans lui, le
#: contrat généré ne décrirait que le chemin heureux, et un consommateur ne
#: saurait pas quelles pannes il doit savoir traiter.
REPONSES_ERREUR: dict[int | str, dict[str, Any]] = {
    400: {
        "model": ErreurWebflow,
        "description": (
            "Paramètre invalide : `limit` hors bornes (elle n'est PAS rabotée), "
            "`offset` négatif ou illisible. Code `validation_error`."
        ),
    },
    401: {
        "model": ErreurWebflow,
        "description": (
            "Jeton absent, invalide ou révoqué — les trois cas sont indistincts. "
            "Code `not_authorized`. N'est PAS retentable."
        ),
    },
    403: {
        "model": ErreurWebflow,
        "description": (
            "Le jeton ne porte pas le scope requis. Code `missing_scopes`, et le "
            "message NOMME les scopes manquants. N'est PAS retentable."
        ),
    },
    404: {
        "model": ErreurWebflow,
        "description": (
            "Ressource inconnue, ou hors du périmètre du jeton. Code `resource_not_found`."
        ),
    },
    409: {
        "model": ErreurWebflow,
        "description": (
            "Formulaires seulement : le site doit être republié pour que la "
            "fonctionnalité soit disponible. Code `forms_require_republish`. Rien "
            "côté client ne le résout."
        ),
    },
    429: {
        "model": ErreurWebflow,
        "description": (
            "Limite de débit atteinte — 60 requêtes / minute au jeton. Code "
            "`too_many_requests`, en-tête `Retry-After` (typiquement 60). Les "
            "en-têtes `X-RateLimit-Limit` et `X-RateLimit-Remaining` sont présents "
            "sur TOUTES les réponses."
        ),
    },
    500: {"model": ErreurWebflow, "description": "Panne injectée. Code `internal_error`."},
    503: {"model": ErreurWebflow, "description": "Panne transitoire injectée."},
}
