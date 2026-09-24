"""L'évolution du monde — ce qui rend l'extraction incrémentale éprouvable.

Aucun test ne dort : le temps défile EXPLICITEMENT via `/__admin/clock` ou
`/__admin/evolve`.
"""

from __future__ import annotations

from conftest import ADMIN, BASE, H, tout_paginer


def _etat(client) -> dict:
    return client.get("/__admin/state", headers=ADMIN).json()


def test_le_monde_ne_bouge_pas_tout_seul_pendant_la_suite(client, site_id):
    avant = client.get(f"{BASE}/sites/{site_id}/form_submissions?limit=10", headers=H).json()
    apres = client.get(f"{BASE}/sites/{site_id}/form_submissions?limit=10", headers=H).json()
    assert avant == apres
    assert _etat(client)["evolution"]["rang"] == 0


def test_l_evolution_est_deterministe(client, site_id):
    client.post("/__admin/evolve", headers=ADMIN, json={"pas": 8})
    premier = client.get(f"{BASE}/sites/{site_id}/form_submissions?limit=20", headers=H).json()
    client.post("/__admin/reset", headers=ADMIN, json={})
    client.post("/__admin/evolve", headers=ADMIN, json={"pas": 8})
    second = client.get(f"{BASE}/sites/{site_id}/form_submissions?limit=20", headers=H).json()
    assert premier == second


def test_une_soumission_nouvelle_arrive_en_tete(client, site_id, donnees):
    """Et elle est STRICTEMENT postérieure au jeu de base : un curseur posé
    sur le jeu de base doit la voir, et elle seule."""
    plafond = max(s["dateSubmitted"] for s in donnees["form_submissions"])
    avant = client.get(f"{BASE}/sites/{site_id}/form_submissions?limit=1", headers=H).json()
    client.post("/__admin/evolve", headers=ADMIN, json={"pas": 1})
    apres = client.get(f"{BASE}/sites/{site_id}/form_submissions?limit=1", headers=H).json()
    assert apres["pagination"]["total"] == avant["pagination"]["total"] + 1
    assert apres["formSubmissions"][0]["dateSubmitted"] > plafond
    assert apres["formSubmissions"][0]["id"] != avant["formSubmissions"][0]["id"]


def test_un_article_est_redige_puis_publie(client, collection_id, site_id):
    site_avant = client.get(f"{BASE}/sites/{site_id}", headers=H).json()
    live_avant = client.get(
        f"{BASE}/collections/{collection_id}/items/live?limit=100", headers=H
    ).json()
    tous_avant = client.get(f"{BASE}/collections/{collection_id}/items?limit=100", headers=H).json()

    # Rang 2 : un brouillon apparaît — dans `/items`, pas dans `/items/live`.
    client.post("/__admin/evolve", headers=ADMIN, json={"pas": 3})
    live = client.get(f"{BASE}/collections/{collection_id}/items/live?limit=100", headers=H).json()
    tous = client.get(f"{BASE}/collections/{collection_id}/items?limit=100", headers=H).json()
    assert tous["pagination"]["total"] == tous_avant["pagination"]["total"] + 1
    assert live["pagination"]["total"] == live_avant["pagination"]["total"]

    # Rang 3 : le plus ancien brouillon est publié — et le SITE avec lui.
    client.post("/__admin/evolve", headers=ADMIN, json={"pas": 1})
    live = client.get(f"{BASE}/collections/{collection_id}/items/live?limit=100", headers=H).json()
    assert live["pagination"]["total"] == live_avant["pagination"]["total"] + 1
    site = client.get(f"{BASE}/sites/{site_id}", headers=H).json()
    assert site["lastPublished"] > site_avant["lastPublished"]


def test_l_horloge_virtuelle_declenche_l_evolution(client):
    """Avec un intervalle à 3600 s, avancer de deux heures doit produire
    exactement deux événements."""
    assert _etat(client)["evolution"]["rang"] == 0
    client.post("/__admin/clock", headers=ADMIN, json={"advance_seconds": 7200})
    assert _etat(client)["evolution"]["rang"] == 2


def test_le_journal_d_evolution_est_observable(client):
    client.post("/__admin/evolve", headers=ADMIN, json={"pas": 6})
    journal = _etat(client)["evolution"]["journal"]
    assert [e["genre"] for e in journal] == [
        "nouvelle_soumission",
        "maj_page",
        "nouvel_article_brouillon",
        "publication_article",
        "nouvelle_candidature",
        "maj_element",
    ]


def test_le_parcours_reste_coherent_apres_evolution(client, site_id):
    client.post("/__admin/evolve", headers=ADMIN, json={"pas": 12})
    tout = tout_paginer(client, f"{BASE}/sites/{site_id}/form_submissions", "formSubmissions", 40)
    assert len({s["id"] for s in tout}) == len(tout)


def test_un_reset_rearme_la_chronologie(client):
    client.post("/__admin/evolve", headers=ADMIN, json={"pas": 5})
    assert _etat(client)["evolution"]["rang"] == 5
    client.post("/__admin/reset", headers=ADMIN, json={})
    assert _etat(client)["evolution"]["rang"] == 0
