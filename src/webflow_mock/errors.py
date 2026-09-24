"""Enveloppe d'erreur — la forme déclarée par la référence officielle de la v2.

    {"message": "…", "code": "resource_not_found", "externalReference": null, "details": []}

Quatre clés, toujours (guide « Error handling », relevé le 2026-09-24) :
`code` est le code machine, `message` le texte lisible, `externalReference`
un lien (le plus souvent `null`), `details` un tableau (le plus souvent vide).
Toute la surface — 401, 403, 404, 409, 429, 500 — parle cette forme, y compris
le 429, ce qui distingue Webflow de Pennylane où le 429 est du texte brut.

┌─ LES CODES SONT ATTESTÉS, LES MESSAGES LE SONT MOINS ───────────────────────┐
│ La référence énumère trente-six codes possibles sur CHAQUE opération, et le  │
│ guide en documente sept avec leur statut. Les MESSAGES, eux, ne sont donnés  │
│ qu'en exemple (`Requested resource not found: The site cannot be found`) ou  │
│ en description de statut. Ceux qui sont servis ici et ne viennent pas d'un   │
│ exemple sont inscrits dans docs/UNVERIFIED-FIELDS.md.                        │
└──────────────────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

#: Les codes du guide « Error handling » — statut par statut.
CODE_401 = "not_authorized"
CODE_403_SCOPE = "missing_scopes"
CODE_404 = "resource_not_found"
CODE_409_FORMS = "forms_require_republish"
CODE_429 = "too_many_requests"
CODE_400 = "validation_error"
CODE_500 = "internal_error"

#: Les messages. Ceux marqués (*) sont des descriptions de statut de la
#: référence, pas des corps observés — cf. docs/UNVERIFIED-FIELDS.md.
MESSAGE_401 = "Unauthorized"  # (*)
MESSAGE_404 = "Requested resource not found"  # exemple du guide, sans le suffixe
MESSAGE_409_FORMS = "To access this feature, the site needs to be republished."  # (*)
MESSAGE_429 = "Too Many Requests"  # exemple de la page « Rate limits »


def erreur(
    status_code: int,
    code: str,
    message: str,
    *,
    details: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """L'enveloppe d'erreur Webflow : quatre clés, dans cet ordre."""
    return JSONResponse(
        status_code=status_code,
        content={
            "message": message,
            "code": code,
            "externalReference": None,
            "details": details or [],
        },
        headers=headers or {},
    )


def erreur_jeton() -> JSONResponse:
    """401 — jeton absent, invalide ou révoqué. Les trois cas sont indistincts
    chez le fournisseur : un seul message, aucun indice sur LEQUEL des trois."""
    return erreur(401, CODE_401, MESSAGE_401)


def erreur_scope(scopes: list[str]) -> JSONResponse:
    """Le 403 de scope manquant — le message NOMME les scopes."""
    liste = ", ".join(f"'{s}'" for s in scopes)
    return erreur(403, CODE_403_SCOPE, f"You are missing the following scopes: {liste}")


def erreur_introuvable(quoi: str | None = None) -> JSONResponse:
    """404 — avec le suffixe « : The site cannot be found » quand on sait quoi."""
    message = MESSAGE_404 if quoi is None else f"{MESSAGE_404}: The {quoi} cannot be found"
    return erreur(404, CODE_404, message)


def erreur_republication() -> JSONResponse:
    """409 — les formulaires exigent que le site soit republié. Propre à
    `/sites/{id}/forms` et aux soumissions : un site qui n'a pas été publié
    depuis l'arrivée de la fonctionnalité ne les sert pas."""
    return erreur(409, CODE_409_FORMS, MESSAGE_409_FORMS)


def erreur_validation(message: str) -> JSONResponse:
    """400 — `limit` ou `offset` illisibles ou hors bornes."""
    return erreur(400, CODE_400, f"Validation Error: {message}")


def erreur_debit(retry_after: int, headers: dict[str, str]) -> JSONResponse:
    """429 — un corps JSON (contrairement à Pennylane) et `Retry-After`."""
    return erreur(429, CODE_429, MESSAGE_429, headers={**headers, "Retry-After": str(retry_after)})


def entetes_debit(limite: int, restant: int) -> dict[str, str]:
    """Les en-têtes `X-RateLimit-*`, présents sur TOUTE réponse — pas
    seulement sur les 429. C'est ce qui permet à un consommateur de se réguler
    avant de se faire limiter. Pas de `X-RateLimit-Reset` : le fournisseur n'en
    documente aucun, la fenêtre est la minute glissante."""
    return {
        "X-RateLimit-Limit": str(limite),
        "X-RateLimit-Remaining": str(max(0, restant)),
    }


def detail_route_inconnue(request: Request) -> JSONResponse:
    """Une route inexistante rend l'enveloppe Webflow, pas le 404 de FastAPI."""
    del request  # le fournisseur ne renvoie aucun écho du chemin demandé
    return erreur_introuvable()
