"""Les dix-huit opérations GET de la surface — toutes montées, toutes servies.

Le test qui compte ici n'est pas « la route existe » mais « aucune route n'a
été montée hors du prélude » : c'est lui qui applique le scope, les
injections et l'enveloppe, et une route qui y échapperait servirait des
données sans jeton.
"""

from __future__ import annotations

import pytest
from conftest import BASE, H

import webflow_mock as mock

ROUTES = sorted(
    chemin for chemin, operations in mock.contrat_openapi()["paths"].items() if "get" in operations
)


def test_la_surface_compte_dix_huit_operations():
    assert len(ROUTES) == 18


def _substituer(chemin: str, donnees: dict) -> str:
    site = donnees["sites"][0]
    collection = next(c for c in donnees["collections"] if c["_cle"] == "articles")
    element = next(
        e for e in donnees["items"][collection["id"]] if not e["isDraft"] and not e["isArchived"]
    )
    formulaire = donnees["forms"][0]
    soumission = donnees["form_submissions"][0]
    page = donnees["pages"][0]
    return (
        chemin.replace("{site_id}", site["id"])
        .replace("{collection_id}", collection["id"])
        .replace("{item_id}", element["id"])
        .replace("{form_id}", formulaire["id"])
        .replace("{form_submission_id}", soumission["id"])
        .replace("{page_id}", page["id"])
    )


@pytest.mark.parametrize("chemin", ROUTES)
def test_chaque_route_repond_200(client, donnees, chemin):
    url = _substituer(chemin, donnees)
    reponse = client.get(url, headers=H)
    # Un site token n'a pas d'introspection : 500, sondé le 2026-09-25.
    attendu = 500 if url.endswith("/token/introspect") else 200
    assert reponse.status_code == attendu, f"{url} → {reponse.status_code} {reponse.text[:200]}"


@pytest.mark.parametrize("chemin", ROUTES)
def test_aucune_route_ne_passe_a_cote_de_l_authentification(client, donnees, chemin):
    url = _substituer(chemin, donnees)
    reponse = client.get(url)
    assert reponse.status_code == 401, f"{url} répond sans jeton"


def test_un_identifiant_inconnu_rend_404(client, site_id, collection_id):
    for url in (
        f"{BASE}/sites/000000000000000000000000",
        f"{BASE}/pages/000000000000000000000000",
        f"{BASE}/collections/000000000000000000000000",
        f"{BASE}/collections/{collection_id}/items/000000000000000000000000",
        f"{BASE}/collections/000000000000000000000000/items",
        f"{BASE}/forms/000000000000000000000000",
        f"{BASE}/forms/000000000000000000000000/submissions",
        f"{BASE}/form_submissions/000000000000000000000000",
        f"{BASE}/sites/{site_id}/pages?localeId=000000000000000000000000",
    ):
        reponse = client.get(url, headers=H)
        assert reponse.status_code == 404, url
        assert reponse.json()["code"] == "resource_not_found"


def test_chaque_route_declare_son_scope(client, donnees):
    """Sans le scope, 403 — sauf `/token/introspect`, le seul sans scope."""
    from conftest import ADMIN

    client.post("/__admin/scopes", headers=ADMIN, json={"scopes": []})
    for chemin in ROUTES:
        url = _substituer(chemin, donnees)
        attendu = 500 if url.endswith("/token/introspect") else 403
        assert client.get(url, headers=H).status_code == attendu, url
