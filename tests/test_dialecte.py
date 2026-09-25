"""Le dialecte Webflow — ce qui casse un consommateur s'il n'est pas exact."""

from __future__ import annotations

import re

import pytest
from conftest import ADMIN, BASE, H

ENVELOPPE = {"message", "code", "externalReference", "details"}
OBJECT_ID = re.compile(r"^[0-9a-f]{24}$")
HORODATAGE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def test_health_est_ouvert(client):
    """La sonde n'est PAS authentifiée : le healthcheck de l'image l'interroge,
    et `depends_on: service_healthy` en dépend côté consommateur."""
    reponse = client.get("/health")
    assert reponse.status_code == 200
    assert reponse.json() == {"status": "ok", "service": "webflow-mock"}


def test_sans_jeton_c_est_401_a_l_enveloppe_webflow(client):
    reponse = client.get(f"{BASE}/sites")
    assert reponse.status_code == 401
    assert reponse.json() == {
        "message": "Request not authorized",
        "code": "not_authorized",
        "externalReference": None,
        "details": [],
    }


@pytest.mark.parametrize(
    "entete",
    [
        {},
        {"Authorization": "mock-webflow-token"},  # sans le schéma
        {"Authorization": "Basic bW9jazptb2Nr"},  # mauvais schéma
        {"Authorization": "Bearer mauvais-jeton"},
        {"Authorization": "Bearer "},
    ],
)
def test_toutes_les_facons_d_avoir_un_mauvais_jeton_donnent_le_meme_401(client, entete):
    """Les trois cas — absent, invalide, révoqué — sont INDISTINCTS chez le
    fournisseur : un seul code, aucun indice sur lequel des trois."""
    reponse = client.get(f"{BASE}/sites", headers=entete)
    assert reponse.status_code == 401
    assert reponse.json()["code"] == "not_authorized"


def test_bearer_est_insensible_a_la_casse(client):
    assert (
        client.get(
            f"{BASE}/sites", headers={"Authorization": "bearer mock-webflow-token"}
        ).status_code
        == 200
    )


def test_scope_manquant_c_est_403_et_le_message_nomme_le_scope(client, site_id):
    """La seule information actionnable de toute l'API : SANS le nom du scope,
    on regénère un site token au hasard, case par case."""
    client.post("/__admin/scopes", headers=ADMIN, json={"scopes": ["sites:read"]})
    reponse = client.get(f"{BASE}/sites/{site_id}/forms", headers=H)
    assert reponse.status_code == 403
    assert reponse.json() == {
        "message": "You are missing the following scopes: 'forms:read'",
        "code": "missing_scopes",
        "externalReference": None,
        "details": [],
    }
    # Le scope conservé continue de passer : c'est bien le PÉRIMÈTRE qui est
    # restreint, pas le jeton qui est cassé.
    assert client.get(f"{BASE}/sites", headers=H).status_code == 200


def test_un_scope_write_couvre_le_read(client, site_id):
    """Le niveau « Read and write » d'un site token inclut la lecture."""
    client.post("/__admin/scopes", headers=ADMIN, json={"scopes": ["sites:write", "pages:write"]})
    assert client.get(f"{BASE}/sites/{site_id}/pages", headers=H).status_code == 200


def test_introspect_rend_500_a_un_site_token(client):
    """Sondé le 2026-09-25 : un site token n'a pas d'introspection — 500
    `internal_error`, avec un jeton pourtant valide. Le test de fumée d'un
    connecteur est `/sites`, pas cet endpoint."""
    reponse = client.get(f"{BASE}/token/introspect", headers=H)
    assert reponse.status_code == 500
    assert reponse.json()["code"] == "internal_error"
    assert reponse.json()["message"] == "An Internal Error Occurred"


def test_introspect_repond_a_un_jeton_d_application_sans_scope(client, monkeypatch):
    """C'est LUI qui sert à découvrir les scopes d'une application : les
    exiger serait circulaire. Et `scope` est une CHAÎNE séparée par des
    virgules, pas un tableau."""
    import webflow_mock as mock

    monkeypatch.setattr(mock.settings, "token_kind", "oauth")
    client.post("/__admin/scopes", headers=ADMIN, json={"scopes": ["cms:read"]})
    reponse = client.get(f"{BASE}/token/introspect", headers=H)
    assert reponse.status_code == 200
    assert reponse.json()["authorization"]["scope"] == "cms:read"
    assert isinstance(reponse.json()["authorization"]["authorizedTo"]["siteIds"], list)


def test_authorized_by_exige_son_scope(client):
    client.post("/__admin/scopes", headers=ADMIN, json={"scopes": ["sites:read"]})
    assert client.get(f"{BASE}/token/authorized_by", headers=H).status_code == 403
    client.post("/__admin/scopes", headers=ADMIN, json={"scopes": ["authorized_user:read"]})
    corps = client.get(f"{BASE}/token/authorized_by", headers=H).json()
    assert set(corps) == {"id", "email", "firstName", "lastName"}


def test_route_inconnue_rend_l_enveloppe_webflow(client):
    """Un `{"detail": "Not Found"}` apprendrait au consommateur une forme
    d'erreur qui n'existe pas chez le fournisseur."""
    reponse = client.get(f"{BASE}/nimportequoi", headers=H)
    assert reponse.status_code == 404
    assert set(reponse.json()) == ENVELOPPE
    assert reponse.json()["code"] == "resource_not_found"


def test_un_site_inconnu_rend_le_message_du_guide(client):
    """L'exemple du guide « Error handling », au mot près."""
    reponse = client.get(f"{BASE}/sites/000000000000000000000000/pages", headers=H)
    assert reponse.status_code == 404
    assert reponse.json()["message"] == "Requested resource not found: The site cannot be found"


def test_methode_d_ecriture_refusee_au_dialecte(client, site_id):
    """Le mock est en LECTURE SEULE. Un POST rend l'enveloppe Webflow, pas le
    405 de FastAPI."""
    reponse = client.post(f"{BASE}/sites/{site_id}/pages", headers=H, json={})
    assert reponse.status_code == 404
    assert reponse.json()["code"] == "resource_not_found"


def test_les_entetes_de_debit_sont_sur_toute_reponse(client):
    """Pas seulement sur les 429 : c'est ce qui permet à un client de se réguler
    AVANT de se faire limiter."""
    reponse = client.get(f"{BASE}/sites", headers=H)
    assert reponse.status_code == 200
    assert reponse.headers["x-ratelimit-limit"] == "60"
    assert int(reponse.headers["x-ratelimit-remaining"]) >= 0
    # `Retry-After` n'apparaît QUE sur un 429.
    assert "retry-after" not in reponse.headers


def test_les_identifiants_sont_des_chaines_hexadecimales(client, site_id):
    """24 hexadécimaux, jamais un entier : un `bigint` côté consommateur casse
    à la première ligne."""
    page = client.get(f"{BASE}/sites/{site_id}/pages?limit=1", headers=H).json()["pages"][0]
    for champ in ("id", "siteId", "localeId"):
        assert isinstance(page[champ], str) and OBJECT_ID.match(page[champ]), champ


def test_les_horodatages_ont_trois_millisecondes_et_un_z(client, site_id):
    site = client.get(f"{BASE}/sites/{site_id}", headers=H).json()
    for champ in ("createdOn", "lastUpdated", "lastPublished"):
        assert HORODATAGE.match(site[champ]), (champ, site[champ])


def test_trois_listes_ne_sont_pas_paginees(client, site_id):
    """`/sites`, `/collections` et `/custom_domains` rendent la liste entière
    SANS objet `pagination`. Un consommateur qui lit `body["pagination"]` sans
    garde lève ici — sur la première route qu'il appelle."""
    for chemin, cle in (
        (f"{BASE}/sites", "sites"),
        (f"{BASE}/sites/{site_id}/collections", "collections"),
        (f"{BASE}/sites/{site_id}/custom_domains", "customDomains"),
    ):
        corps = client.get(chemin, headers=H).json()
        assert set(corps) == {cle}, chemin
        assert isinstance(corps[cle], list)


def test_la_cle_de_liste_change_a_chaque_ressource(client, site_id, collection_id, form_id):
    attendues = {
        f"{BASE}/sites/{site_id}/pages": "pages",
        f"{BASE}/collections/{collection_id}/items": "items",
        f"{BASE}/sites/{site_id}/forms": "forms",
        f"{BASE}/forms/{form_id}/submissions": "formSubmissions",
        f"{BASE}/sites/{site_id}/form_submissions": "formSubmissions",
    }
    for chemin, cle in attendues.items():
        corps = client.get(f"{chemin}?limit=1", headers=H).json()
        assert set(corps) == {cle, "pagination"}, chemin


def test_la_liste_des_collections_ne_porte_pas_les_champs(client, site_id):
    """Un second appel par collection est nécessaire pour connaître le schéma."""
    liste = client.get(f"{BASE}/sites/{site_id}/collections", headers=H).json()["collections"]
    assert liste and all("fields" not in c for c in liste)
    detail = client.get(f"{BASE}/collections/{liste[0]['id']}", headers=H).json()
    assert detail["fields"][0]["slug"] == "name"
    assert {"id", "isRequired", "isEditable", "type", "displayName", "slug"} <= set(
        detail["fields"][0]
    )


def test_aucune_cle_interne_ne_fuit(client, site_id):
    """Les clés `_cle` du jeu de données sont des affordances du mock."""
    for chemin in (
        f"{BASE}/sites/{site_id}/collections",
        f"{BASE}/sites/{site_id}/forms",
    ):
        assert "_cle" not in client.get(chemin, headers=H).text


def test_les_champs_d_un_formulaire_sont_un_objet_et_la_reponse_est_clee_par_nom(client, form_id):
    """`fields` est un OBJET clé par identifiant ; `formResponse` est clé par
    `displayName`. Le rapprochement se fait par le nom, pas par l'identifiant."""
    formulaire = client.get(f"{BASE}/forms/{form_id}", headers=H).json()
    assert isinstance(formulaire["fields"], dict)
    noms = {champ["displayName"] for champ in formulaire["fields"].values()}
    soumission = client.get(f"{BASE}/forms/{form_id}/submissions?limit=1", headers=H).json()[
        "formSubmissions"
    ][0]
    # Hors les `utm_*` : le site les pousse dans le formulaire sans qu'ils
    # soient des champs déclarés (observé le 2026-09-25).
    assert {k for k in soumission["formResponse"] if not k.startswith("utm_")} <= noms
    assert soumission["displayName"] == formulaire["displayName"]
    assert soumission["pageId"] == formulaire["pageId"]
    assert "publishedPath" in soumission and soumission["schema"] == []


def test_locale_id_est_null_pour_la_locale_primaire(client, site_id):
    """`null` n'est pas « inconnu » : c'est la langue par défaut."""
    tout = client.get(f"{BASE}/sites/{site_id}/form_submissions?limit=100", headers=H).json()[
        "formSubmissions"
    ]
    assert any(s["localeId"] is None for s in tout)
    assert any(isinstance(s["localeId"], str) for s in tout)


def test_une_page_est_une_entite_localisee(client, site_id, donnees):
    """Même `id` dans chaque locale ; `title` et `publishedPath` changent."""
    en = donnees["sites"][0]["locales"]["secondary"][0]["id"]
    fr = client.get(f"{BASE}/sites/{site_id}/pages?limit=100", headers=H).json()["pages"]
    en_pages = client.get(
        f"{BASE}/sites/{site_id}/pages?limit=100&localeId={en}", headers=H
    ).json()["pages"]
    assert [p["id"] for p in fr] == [p["id"] for p in en_pages]
    assert all(p["publishedPath"].startswith("/en") for p in en_pages)
    assert fr[0]["publishedPath"] == "/" and en_pages[0]["publishedPath"] == "/en"
    assert fr[0]["localeId"] != en_pages[0]["localeId"]


def test_les_elements_live_excluent_brouillons_et_archives(client, collection_id):
    prepares = client.get(f"{BASE}/collections/{collection_id}/items?limit=100", headers=H).json()
    publies = client.get(
        f"{BASE}/collections/{collection_id}/items/live?limit=100", headers=H
    ).json()
    assert any(e["isDraft"] for e in prepares["items"])
    assert any(e["isArchived"] for e in prepares["items"])
    assert publies["pagination"]["total"] < prepares["pagination"]["total"]
    assert all(not e["isDraft"] and not e["isArchived"] for e in publies["items"])
    assert all(e["lastPublished"] is not None for e in publies["items"])


def test_un_brouillon_n_est_pas_servi_par_le_detail_live(client, collection_id):
    prepares = client.get(f"{BASE}/collections/{collection_id}/items?limit=100", headers=H).json()
    brouillon = next(e for e in prepares["items"] if e["isDraft"])
    assert (
        client.get(
            f"{BASE}/collections/{collection_id}/items/{brouillon['id']}", headers=H
        ).status_code
        == 200
    )
    reponse = client.get(
        f"{BASE}/collections/{collection_id}/items/live/{brouillon['id']}", headers=H
    )
    assert reponse.status_code == 404


def test_field_data_ne_garantit_que_name_et_slug(client, collection_id):
    """Un champ `Option` vaut l'ID de l'option, un `Reference` l'ID de
    l'élément visé, une `Image` un objet — le schéma se lit dans la collection."""
    element = client.get(f"{BASE}/collections/{collection_id}/items?limit=1", headers=H).json()[
        "items"
    ][0]
    donnees = element["fieldData"]
    assert {"name", "slug"} <= set(donnees)
    assert isinstance(donnees["categorie"], str) and len(donnees["categorie"]) == 24
    assert isinstance(donnees["auteur"], str) and len(donnees["auteur"]) == 24
    assert set(donnees["image-principale"]) == {"fileId", "url", "alt"}
    # Le libellé de l'option ne se lit que dans la DÉFINITION du champ.
    collection = client.get(f"{BASE}/collections/{collection_id}", headers=H).json()
    champ = next(c for c in collection["fields"] if c["slug"] == "categorie")
    options = {o["id"]: o["name"] for o in champ["validations"]["options"]}
    assert donnees["categorie"] in options


def test_le_tri_des_elements_est_explicite(client, collection_id):
    corps = client.get(
        f"{BASE}/collections/{collection_id}/items?limit=100&sortBy=lastUpdated&sortOrder=desc",
        headers=H,
    ).json()["items"]
    dates = [e["lastUpdated"] for e in corps]
    assert dates == sorted(dates, reverse=True)
    reponse = client.get(f"{BASE}/collections/{collection_id}/items?sortBy=prix", headers=H)
    assert reponse.status_code == 400
    assert reponse.json()["code"] == "validation_error"


def test_les_formulaires_peuvent_exiger_une_republication(client, site_id, form_id):
    """409 `forms_require_republish` — ni jeton ni scope ne le résolvent."""
    client.post("/__admin/republish", headers=ADMIN, json={"required": True})
    for chemin in (
        f"{BASE}/sites/{site_id}/forms",
        f"{BASE}/forms/{form_id}",
        f"{BASE}/forms/{form_id}/submissions",
        f"{BASE}/sites/{site_id}/form_submissions",
    ):
        reponse = client.get(chemin, headers=H)
        assert reponse.status_code == 409, chemin
        assert reponse.json()["code"] == "forms_require_republish"
    # Les pages, elles, ne sont pas concernées.
    assert client.get(f"{BASE}/sites/{site_id}/pages", headers=H).status_code == 200
    client.post("/__admin/republish", headers=ADMIN, json={"required": False})
    assert client.get(f"{BASE}/sites/{site_id}/forms", headers=H).status_code == 200
