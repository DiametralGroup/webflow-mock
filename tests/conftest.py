"""Harnais de tests.

Deux réglages d'environnement, posés AVANT l'import du paquet (la configuration
est lue à l'import) :

  • le plan de contrôle `/__admin` est monté — le montage est conditionnel ;
  • l'intervalle d'évolution passe à 3600 s : aucun événement ne se déclenche au
    fil de l'horloge murale pendant la suite, même sur une CI lente. Les tests
    d'évolution font défiler le temps EXPLICITEMENT via `/__admin/clock` ou
    `/__admin/evolve` — c'est ce qui les rend déterministes.
"""

from __future__ import annotations

import os

os.environ.setdefault("WEBFLOW_MOCK_ADMIN_ENABLED", "true")
os.environ.setdefault("WEBFLOW_MOCK_EVOLUTION_INTERVAL", "3600")

import pytest
from fastapi.testclient import TestClient

import webflow_mock as mock

BASE = "/v2"

#: Le trousseau d'une requête bien formée. Un seul en-tête.
H = {"Authorization": "Bearer mock-webflow-token"}
ADMIN = {"X-Mock-Admin-Token": "mock-admin-token"}


@pytest.fixture()
def client():
    """Un client sur un état REMIS À NEUF — avant ET après, pour qu'un test ne
    lègue ni règle d'injection, ni événement d'évolution, ni scope amputé au
    suivant."""
    c = TestClient(mock.app)
    mock.settings.reload()
    mock.state.reset()
    yield c
    mock.settings.reload()
    mock.state.reset()


@pytest.fixture()
def donnees(client):  # noqa: ARG001 — la fixture chaîne le reset
    """Le jeu de données, pour les tests qui l'inspectent directement."""
    return mock.state.dataset


@pytest.fixture()
def site_id(donnees) -> str:
    return donnees["sites"][0]["id"]


@pytest.fixture()
def collection_id(donnees) -> str:
    """La collection des articles — la plus fournie, avec brouillons et archivés."""
    return next(c["id"] for c in donnees["collections"] if c["_cle"] == "articles")


@pytest.fixture()
def form_id(donnees) -> str:
    return next(f["id"] for f in donnees["forms"] if f["_cle"] == "contact")


def tout_paginer(client, chemin: str, cle: str, limite: int = 7) -> list[dict]:
    """Le parcours de pagination complet — l'outil des tests de bout en bout.

    Il s'arrête sur `offset + limit >= total` et non sur une page courte :
    c'est la règle du dialecte, et un helper qui prendrait le raccourci
    masquerait justement le défaut qu'on cherche.
    """
    separateur = "&" if "?" in chemin else "?"
    elements: list[dict] = []
    offset = 0
    for _ in range(200):
        reponse = client.get(f"{chemin}{separateur}limit={limite}&offset={offset}", headers=H)
        assert reponse.status_code == 200, reponse.text
        corps = reponse.json()
        elements.extend(corps[cle])
        pagination = corps["pagination"]
        offset += pagination["limit"]
        if offset >= pagination["total"]:
            return elements
    raise AssertionError(f"pagination non terminée après 200 pages sur {chemin}")
