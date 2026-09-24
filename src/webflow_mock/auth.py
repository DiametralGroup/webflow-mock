"""Authentification — Bearer statique et scopes, le dialecte exact de Webflow.

Le même régime que Pennylane, le plus simple des six mocks de l'écosystème :
pas de JWT à fabriquer (BoondManager), pas d'échange client_credentials
(Entra), pas d'assertion RS256 (GA4), pas d'en-tête de version (LinkedIn). Un
« site token », longue durée, porté par `Authorization: Bearer <TOKEN>`.

Ce qui fait l'intérêt du dialecte est ailleurs : les **scopes**.

┌─ 401 ET 403 NE SE SOIGNENT PAS PAREIL ──────────────────────────────────────┐
│ 401 — le jeton est absent, invalide ou révoqué. Les trois cas sont           │
│       INDISTINCTS chez le fournisseur : un seul message, aucun indice sur    │
│       lequel des trois. Il faut regénérer un jeton.                          │
│ 403 — le jeton est valide, mais ne porte pas le scope requis. Le code est    │
│       `missing_scopes` et le message NOMME les scopes manquants ; c'est la   │
│       seule information actionnable de toute l'API : un site token se        │
│       génère case par case, et il faut savoir laquelle recocher.             │
│                                                                              │
│ Ni l'un ni l'autre n'est retentable. Un client qui rejoue un 403 en          │
│ espérant mieux boucle jusqu'à épuisement de ses tentatives, puis échoue sur  │
│ un message de timeout qui ne dit rien du vrai problème.                      │
└──────────────────────────────────────────────────────────────────────────────┘

Le scope d'une route se déclare dans `app.py` et vient de la référence
officielle, opération par opération. `GET /token/introspect` est le seul
endpoint SANS scope requis — c'est justement lui qui sert à découvrir les
scopes dont on dispose.
"""

from __future__ import annotations

from .settings import settings


def jeton_de_l_entete(valeur: str | None) -> str | None:
    """Extrait le jeton de `Authorization: Bearer <TOKEN>`.

    Le préfixe est comparé sans tenir compte de la casse : les bibliothèques
    HTTP écrivent aussi bien `Bearer` que `bearer`, et refuser la seconde
    forme serait une sévérité que le fournisseur n'a pas.
    """
    if not valeur:
        return None
    schema, _, jeton = valeur.partition(" ")
    if schema.lower() != "bearer":
        return None
    jeton = jeton.strip()
    return jeton or None


def jeton_est_valide(jeton: str | None) -> bool:
    return jeton is not None and jeton == settings.token


def scope_accorde(requis: str | None) -> bool:
    """Le scope requis est-il porté par le jeton ?

    Un endpoint documenté `x:read` doit accepter `x:write` : chez Webflow, le
    niveau « Read and write » d'un site token inclut la lecture. Sans cette
    tolérance, un jeton d'écriture se verrait refuser la lecture, ce qui
    n'arrive pas en réel.
    """
    if requis is None:
        return True
    if requis in settings.scopes:
        return True
    base, sep, suffixe = requis.partition(":")
    if sep and suffixe == "read":
        return f"{base}:write" in settings.scopes
    return False
