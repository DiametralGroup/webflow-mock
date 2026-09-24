"""Sonde un site Webflow RÉEL et compare les FORMES à celles du mock.

    WEBFLOW_TOKEN=xxx uv run python scripts/compare_real.py

GET seulement, n'écrit rien, et ne copie AUCUNE donnée dans son rapport : seuls
les noms de champs et leurs types sont relevés — c'est exactement là que les
pièges se voient (une clé absente, un `null` là où le mock sert une chaîne, une
liste non paginée). Les soumissions de formulaire sont nominatives : le script
n'en lit que les CLÉS de `formResponse`, jamais les valeurs.

Toute différence est une différence du MOCK : le fournisseur a raison.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

BASE = os.environ.get("WEBFLOW_API_URL", "https://api.webflow.com/v2").rstrip("/")


def _get(chemin: str, jeton: str) -> tuple[int, dict[str, str], Any]:
    requete = urllib.request.Request(
        f"{BASE}{chemin}",
        headers={"Authorization": f"Bearer {jeton}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(requete, timeout=30) as reponse:
            return reponse.status, dict(reponse.headers), json.loads(reponse.read() or b"null")
    except urllib.error.HTTPError as exc:
        corps = exc.read()
        try:
            return exc.code, dict(exc.headers), json.loads(corps)
        except ValueError:
            return exc.code, dict(exc.headers), corps.decode(errors="replace")[:200]


def _forme(valeur: Any, profondeur: int = 0) -> Any:
    """La forme d'une valeur : types et clés, jamais les valeurs."""
    if isinstance(valeur, dict):
        if profondeur >= 3:
            return "object"
        return {cle: _forme(v, profondeur + 1) for cle, v in sorted(valeur.items())}
    if isinstance(valeur, list):
        return [_forme(valeur[0], profondeur + 1)] if valeur else []
    if valeur is None:
        return "null"
    return type(valeur).__name__


def main() -> int:
    jeton = os.environ.get("WEBFLOW_TOKEN")
    if not jeton:
        print("WEBFLOW_TOKEN manquant", file=sys.stderr)
        return 2

    rapport: dict[str, Any] = {}

    statut, entetes, corps = _get("/token/introspect", jeton)
    rapport["introspect"] = {"status": statut, "forme": _forme(corps)}
    rapport["entetes_debit"] = {
        k: v for k, v in entetes.items() if k.lower().startswith(("x-ratelimit", "retry-after"))
    }

    statut, _, sites = _get("/sites", jeton)
    rapport["sites"] = {"status": statut, "forme": _forme(sites)}
    if statut != 200 or not sites.get("sites"):
        print(json.dumps(rapport, indent=2, ensure_ascii=False))
        return 1
    site_id = sites["sites"][0]["id"]

    for nom, chemin in (
        ("custom_domains", f"/sites/{site_id}/custom_domains"),
        ("pages", f"/sites/{site_id}/pages?limit=3"),
        ("pages_limit_101", f"/sites/{site_id}/pages?limit=101"),
        ("collections", f"/sites/{site_id}/collections"),
        ("forms", f"/sites/{site_id}/forms?limit=3"),
        ("form_submissions", f"/sites/{site_id}/form_submissions?limit=3"),
        ("inconnu", "/sites/000000000000000000000000/pages"),
    ):
        statut, _, corps = _get(chemin, jeton)
        forme = _forme(corps)
        # Les clés de `formResponse` disent la forme ; les valeurs, l'identité.
        if isinstance(corps, dict) and corps.get("formSubmissions"):
            forme = {
                **forme,
                "formResponse_keys": sorted(corps["formSubmissions"][0]["formResponse"]),
                "dateSubmitted_order": [s["dateSubmitted"] for s in corps["formSubmissions"]],
            }
        rapport[nom] = {"status": statut, "forme": forme}

    statut, _, cols = _get(f"/sites/{site_id}/collections", jeton)
    if statut == 200 and cols.get("collections"):
        col = cols["collections"][0]["id"]
        for nom, chemin in (
            ("collection", f"/collections/{col}"),
            ("items", f"/collections/{col}/items?limit=2"),
            ("items_live", f"/collections/{col}/items/live?limit=2"),
        ):
            statut, _, corps = _get(chemin, jeton)
            rapport[nom] = {"status": statut, "forme": _forme(corps)}

    print(json.dumps(rapport, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
