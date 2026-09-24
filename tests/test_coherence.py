"""La cohérence du monde — ce qu'un consommateur peut joindre, il doit le trouver."""

from __future__ import annotations

from collections import Counter

from conftest import BASE, tout_paginer


def test_chaque_soumission_reference_un_formulaire_existant(donnees):
    formulaires = {f["id"] for f in donnees["forms"]}
    assert all(s["formId"] in formulaires for s in donnees["form_submissions"])
    assert all(s["siteId"] == donnees["sites"][0]["id"] for s in donnees["form_submissions"])


def test_chaque_formulaire_est_pose_sur_une_page_existante(donnees):
    pages = {p["id"]: p for p in donnees["pages"]}
    for formulaire in donnees["forms"]:
        assert formulaire["pageId"] in pages
        assert formulaire["pageName"] == pages[formulaire["pageId"]]["title"]


def test_les_pages_gabarit_pointent_vers_une_collection_existante(donnees):
    collections = {c["id"] for c in donnees["collections"]}
    gabarits = [p for p in donnees["pages"] if p["collectionId"]]
    assert len(gabarits) == 4
    assert all(p["collectionId"] in collections for p in gabarits)


def test_les_references_des_articles_visent_des_auteurs(donnees):
    par_cle = {c["_cle"]: c["id"] for c in donnees["collections"]}
    auteurs = {a["id"] for a in donnees["items"][par_cle["auteurs"]]}
    assert all(a["fieldData"]["auteur"] in auteurs for a in donnees["items"][par_cle["articles"]])


def test_les_slugs_sont_uniques_par_collection(donnees):
    for elements in donnees["items"].values():
        slugs = [e["fieldData"]["slug"] for e in elements]
        assert len(slugs) == len(set(slugs))


def test_le_jeu_est_ancre_et_borne(donnees):
    """Rien après le 12 juillet 2026 dans le jeu de BASE, rien avant la mise en
    ligne : c'est ce qui laisse à l'évolution une fenêtre strictement à elle."""
    horodatages = [s["dateSubmitted"] for s in donnees["form_submissions"]]
    horodatages += [p["lastUpdated"] for p in donnees["pages"]]
    for elements in donnees["items"].values():
        horodatages += [e["lastUpdated"] for e in elements]
    assert max(horodatages) < "2026-07-13"
    assert min(horodatages) >= "2024-03-18"  # la mise en ligne du site


def test_les_volumes_sont_ceux_d_un_site_b2b(client, site_id):
    tout = tout_paginer(client, f"{BASE}/sites/{site_id}/form_submissions", "formSubmissions", 100)
    par_formulaire = Counter(s["displayName"] for s in tout)
    assert 400 <= len(tout) <= 800
    assert par_formulaire["Newsletter"] > par_formulaire["Contact"]
    assert par_formulaire["Inscription événement"] > 0
    domaines = Counter(_domaine(s) for s in tout)
    assert domaines["gmail.com"] > 10, "les domaines génériques doivent peser"
    assert any(d.endswith("-retail.example") for d in domaines), "et les clients du monde partagé"


def _domaine(soumission: dict) -> str:
    for cle, valeur in soumission["formResponse"].items():
        if cle.startswith("Email"):
            return str(valeur).rsplit("@", 1)[-1]
    return ""


def test_le_jeu_est_deterministe_a_l_octet(donnees):
    from webflow_mock import build_dataset

    assert build_dataset(42) == donnees
    assert build_dataset(7) != donnees
