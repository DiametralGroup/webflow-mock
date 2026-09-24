"""Les modes de panne — « the point of the mock is to reproduce failure modes ».

Chaque règle est pilotée par HTTP, parce que le mock tourne en CONTENEUR chez
son consommateur : hors du processus, un test ne peut plus muter l'état en
Python.
"""

from __future__ import annotations

from conftest import ADMIN, BASE, H


def _injecter(client, **regle):
    reponse = client.post("/__admin/inject", headers=ADMIN, json=regle)
    assert reponse.status_code == 200, reponse.text
    return reponse.json()["rule"]["id"]


def test_le_429_est_du_json_avec_retry_after(client):
    """Contrairement à Pennylane, le 429 parle l'enveloppe. Le piège est
    `Retry-After` : 60 secondes, et un client qui l'ignore rejoue dans la
    même minute."""
    _injecter(client, kind="rate_limit", scope=f"{BASE}/sites", after_requests=1)
    client.get(f"{BASE}/sites", headers=H)
    reponse = client.get(f"{BASE}/sites", headers=H)
    assert reponse.status_code == 429
    assert reponse.json() == {
        "message": "Too Many Requests",
        "code": "too_many_requests",
        "externalReference": None,
        "details": [],
    }
    assert reponse.headers["retry-after"] == "60"
    assert reponse.headers["x-ratelimit-limit"] == "60"
    assert reponse.headers["x-ratelimit-remaining"] == "0"


def test_une_panne_transitoire_cesse_d_elle_meme(client):
    """Sinon on ne teste pas un retry, on teste un échec."""
    _injecter(client, kind="status", scope=f"{BASE}/*", status=503, times=1)
    assert client.get(f"{BASE}/sites", headers=H).status_code == 503
    assert client.get(f"{BASE}/sites", headers=H).status_code == 200


def test_une_panne_persistante_ne_cesse_pas(client, site_id):
    _injecter(client, kind="status", scope=f"{BASE}/sites/*/pages", status=500)
    for _ in range(4):
        reponse = client.get(f"{BASE}/sites/{site_id}/pages", headers=H)
        assert reponse.status_code == 500
        assert reponse.json()["code"] == "internal_error"
    # Le périmètre est respecté : les autres ressources répondent.
    assert client.get(f"{BASE}/sites/{site_id}/forms", headers=H).status_code == 200


def test_auth_reject_preempte_l_authentification(client):
    _injecter(client, kind="auth_reject", scope=f"{BASE}/*")
    reponse = client.get(f"{BASE}/sites", headers=H)
    assert reponse.status_code == 401
    assert reponse.json()["code"] == "not_authorized"


def test_scope_reject_nomme_le_scope_manquant(client, site_id):
    _injecter(
        client, kind="scope_reject", scope=f"{BASE}/sites/*/forms", scope_manquant="forms:read"
    )
    reponse = client.get(f"{BASE}/sites/{site_id}/forms", headers=H)
    assert reponse.status_code == 403
    assert reponse.json()["message"] == "You are missing the following scopes: 'forms:read'"


def test_republish_required_est_injectable_et_transitoire(client, site_id):
    _injecter(client, kind="republish_required", scope=f"{BASE}/sites/*/forms", times=1)
    reponse = client.get(f"{BASE}/sites/{site_id}/forms", headers=H)
    assert reponse.status_code == 409
    assert reponse.json()["code"] == "forms_require_republish"
    assert client.get(f"{BASE}/sites/{site_id}/forms", headers=H).status_code == 200


def test_une_regle_se_retire_et_se_vide(client):
    ident = _injecter(client, kind="status", scope="*", status=500)
    assert client.get(f"{BASE}/sites", headers=H).status_code == 500
    client.delete(f"/__admin/inject/{ident}", headers=ADMIN)
    assert client.get(f"{BASE}/sites", headers=H).status_code == 200

    _injecter(client, kind="status", scope="*", status=500)
    client.post("/__admin/inject/clear", headers=ADMIN)
    assert client.get(f"{BASE}/sites", headers=H).status_code == 200


def test_le_plan_de_controle_est_protege(client):
    assert client.get("/__admin/state").status_code == 403
    assert client.post("/__admin/reset", json={}).status_code == 403
    assert client.post("/__admin/inject", json={"kind": "status"}).status_code == 403


def test_le_plan_de_controle_expose_les_parametres_recus(client, site_id):
    """La clé de voûte des tests aval : PROUVER que le consommateur a envoyé
    son offset. Sans cette preuve, un pipeline qui l'aurait oublié passerait
    tous ses tests — il rechargerait simplement la première page."""
    client.get(f"{BASE}/sites/{site_id}/pages?limit=3", headers=H)
    client.get(f"{BASE}/sites/{site_id}/pages?limit=3&offset=3", headers=H)
    etat = client.get("/__admin/state", headers=ADMIN).json()
    vus = etat["last_query_params_by_path"][f"{BASE}/sites/{site_id}/pages"]
    assert vus == {"limit": "3", "offset": "3"}
    assert etat["request_counts_by_path"][f"{BASE}/sites/{site_id}/pages"] == 2


def test_le_reset_restaure_les_scopes_de_l_environnement(client, site_id):
    client.post("/__admin/scopes", headers=ADMIN, json={"scopes": ["sites:read"]})
    assert client.get(f"{BASE}/sites/{site_id}/pages", headers=H).status_code == 403
    client.post("/__admin/reset", headers=ADMIN, json={})
    assert client.get(f"{BASE}/sites/{site_id}/pages", headers=H).status_code == 200
    assert len(client.get("/__admin/state", headers=ADMIN).json()["scopes"]) == 5


def test_le_reset_reconstruit_le_monde_et_vide_les_regles(client):
    _injecter(client, kind="status", scope="*", status=500)
    reponse = client.post("/__admin/reset", headers=ADMIN, json={"seed": 7})
    assert reponse.status_code == 200
    assert reponse.json()["seed"] == 7
    assert client.get(f"{BASE}/sites", headers=H).status_code == 200
    assert client.get("/__admin/state", headers=ADMIN).json()["injections"] == []


def test_une_autre_graine_donne_d_autres_identifiants(client):
    avant = client.get(f"{BASE}/sites", headers=H).json()["sites"][0]["id"]
    client.post("/__admin/reset", headers=ADMIN, json={"seed": 7})
    apres = client.get(f"{BASE}/sites", headers=H).json()["sites"][0]["id"]
    assert avant != apres
    client.post("/__admin/reset", headers=ADMIN, json={"seed": 42})
    assert client.get(f"{BASE}/sites", headers=H).json()["sites"][0]["id"] == avant


def test_mutate_pousse_last_updated_au_dessus_de_tout(client, site_id):
    pages = client.get(f"{BASE}/sites/{site_id}/pages?limit=100", headers=H).json()["pages"]
    cible = pages[3]
    reponse = client.post(
        "/__admin/mutate",
        headers=ADMIN,
        json={"collection": "pages", "id": cible["id"], "champs": {"title": "Mutée"}},
    )
    assert reponse.status_code == 200, reponse.text
    apres = client.get(f"{BASE}/pages/{cible['id']}", headers=H).json()
    assert apres["title"] == "Mutée"
    assert apres["lastUpdated"] > max(p["lastUpdated"] for p in pages)
