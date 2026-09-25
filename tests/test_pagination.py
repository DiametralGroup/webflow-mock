"""L'offset — le sixième dialecte de pagination de l'écosystème insights360.

BoondManager pagine par `page`/`maxResults`, Graph par `@odata.nextLink`,
LinkedIn par `start`/`count`, GA4 par `limit`/`offset` sans total, Pennylane
par curseur opaque. Un connecteur qui aurait « une » boucle générique se casse
ici, et c'est le but.
"""

from __future__ import annotations

import pytest
from conftest import ADMIN, BASE, H, tout_paginer


def test_le_parcours_complet_ne_perd_ni_ne_double_aucune_ligne(client, site_id):
    tout = tout_paginer(client, f"{BASE}/sites/{site_id}/form_submissions", "formSubmissions", 7)
    identifiants = [element["id"] for element in tout]
    assert len(identifiants) == len(set(identifiants)), "doublons entre deux pages"
    total = client.get(f"{BASE}/sites/{site_id}/form_submissions?limit=1", headers=H).json()[
        "pagination"
    ]["total"]
    assert len(identifiants) == total


def test_la_pagination_dit_ce_qui_a_ete_applique(client, site_id):
    corps = client.get(f"{BASE}/sites/{site_id}/pages?limit=5&offset=10", headers=H).json()
    assert corps["pagination"] == {"limit": 5, "offset": 10, "total": len(_toutes(client, site_id))}
    assert len(corps["pages"]) == 5


def _toutes(client, site_id):
    return client.get(f"{BASE}/sites/{site_id}/pages?limit=100", headers=H).json()["pages"]


def test_un_offset_au_dela_du_total_rend_une_page_vide_pas_une_erreur(client, site_id):
    corps = client.get(f"{BASE}/sites/{site_id}/pages?limit=5&offset=9999", headers=H).json()
    assert corps["pages"] == []
    assert corps["pagination"]["offset"] == 9999


@pytest.mark.parametrize("valeur", ["101", "9999"])
def test_limit_au_dela_du_plafond_est_rabote_en_silence(client, site_id, valeur):
    """Sondé le 2026-09-25 : `limit=101` → 200, `pagination.limit: 100`. Un
    consommateur qui avance son offset de SA valeur et non de
    `pagination.limit` saute des lignes — sans erreur."""
    reponse = client.get(f"{BASE}/sites/{site_id}/form_submissions?limit={valeur}", headers=H)
    assert reponse.status_code == 200
    assert reponse.json()["pagination"]["limit"] == 100
    assert len(reponse.json()["formSubmissions"]) == 100


@pytest.mark.parametrize("valeur", ["0", "-1", "abc", "2.5"])
def test_limit_nul_ou_illisible_rend_400_avec_le_motif(client, site_id, valeur):
    reponse = client.get(f"{BASE}/sites/{site_id}/pages?limit={valeur}", headers=H)
    assert reponse.status_code == 400
    assert reponse.json()["code"] == "validation_error"
    assert reponse.json()["message"].startswith('Validation Error: ["Value (limit) should match')


@pytest.mark.parametrize("valeur", ["-1", "abc", "1.5"])
def test_offset_illisible_rend_400(client, site_id, valeur):
    reponse = client.get(f"{BASE}/sites/{site_id}/pages?offset={valeur}", headers=H)
    assert reponse.status_code == 400
    assert reponse.json()["code"] == "validation_error"


def test_la_limite_par_defaut_est_cent(client, site_id):
    corps = client.get(f"{BASE}/sites/{site_id}/form_submissions", headers=H).json()
    assert corps["pagination"]["limit"] == 100
    assert len(corps["formSubmissions"]) == 100


def test_les_soumissions_sont_servies_de_la_plus_recente_a_la_plus_ancienne(client, site_id):
    tout = tout_paginer(client, f"{BASE}/sites/{site_id}/form_submissions", "formSubmissions", 50)
    dates = [s["dateSubmitted"] for s in tout]
    assert dates == sorted(dates, reverse=True)


def test_la_derive_d_offset_se_reproduit_a_la_demande(client, site_id):
    """La propriété structurelle d'une pagination par offset sur une liste qui
    vit : un élément arrivé en tête décale tout, et la dernière ligne de la
    page N revient en tête de la page N+1. Sans erreur."""
    client.post(
        "/__admin/inject",
        headers=ADMIN,
        json={"kind": "page_drift", "scope": f"{BASE}/sites/*/form_submissions", "after_page": 1},
    )
    page1 = client.get(
        f"{BASE}/sites/{site_id}/form_submissions?limit=5&offset=0", headers=H
    ).json()
    page2 = client.get(
        f"{BASE}/sites/{site_id}/form_submissions?limit=5&offset=5", headers=H
    ).json()
    assert page2["formSubmissions"][0]["id"] == page1["formSubmissions"][-1]["id"]
    assert page2["pagination"]["total"] == page1["pagination"]["total"] + 1


def test_la_derive_peut_aussi_faire_sauter_une_ligne(client, site_id):
    client.post(
        "/__admin/inject",
        headers=ADMIN,
        json={
            "kind": "page_drift",
            "scope": f"{BASE}/sites/*/form_submissions",
            "after_page": 1,
            "mode": "remove",
        },
    )
    sans_derive = client.get(
        f"{BASE}/sites/{site_id}/form_submissions?limit=5&offset=0", headers=H
    ).json()
    total = sans_derive["pagination"]["total"]
    page2 = client.get(
        f"{BASE}/sites/{site_id}/form_submissions?limit=5&offset=5", headers=H
    ).json()
    assert page2["pagination"]["total"] == total - 1


def test_element_id_filtre_les_soumissions_d_un_site(client, site_id, donnees):
    formulaire = donnees["forms"][0]
    corps = client.get(
        f"{BASE}/sites/{site_id}/form_submissions?elementId={formulaire['formElementId']}&limit=100",
        headers=H,
    ).json()
    assert corps["formSubmissions"]
    assert all(s["formId"] == formulaire["id"] for s in corps["formSubmissions"])
