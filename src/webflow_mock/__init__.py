"""Mock de l'API Webflow (Data API v2) — image container et paquet Python.

La surface reproduit les opérations GET de la Data API v2 documentée
(https://developers.webflow.com/data/reference) qu'un connecteur analytique
consomme — jeton, sites, pages, collections CMS et leurs éléments,
formulaires et soumissions — servies sur UN site vitrine cohérent : celui de
« Boréal Conseil », l'ESN française qui peuple déjà `boondmanager-mock`,
`entra-mock`, `linkedin-mock`, `ga-mock` et `pennylane-mock`. Le monde ÉVOLUE
dans le temps pour éprouver l'extraction incrémentale (cf. evolution.py).

Deux modes d'utilisation, délibérément maintenus tous les deux :

  • **En process** — `TestClient(webflow_mock.app)`. La propriété qu'il ne
    faut pas perdre : l'application que la stack interroge EST celle que les
    tests exercent.

  • **En conteneur** — `python -m webflow_mock`, en docker compose comme en
    service CI. C'est ce mode qui rend indispensable le plan de contrôle
    `/__admin` : hors du processus, on ne peut plus muter l'état en Python.

Ré-exports pour que rien n'ait besoin de connaître la structure interne :

    app                  l'application FastAPI
    contrat_openapi      le contrat PUBLIÉ (sans /__admin ni /health)
    state                l'état mutable (dataset, reset, évolution)
    engine               le moteur d'injection de pannes
    settings             la configuration relue de l'environnement
    build_dataset        construction du jeu de données
"""

from __future__ import annotations

from .app import app, contrat_openapi
from .injection import engine
from .settings import settings
from .state import build_dataset, state

__all__ = [
    "app",
    "build_dataset",
    "contrat_openapi",
    "engine",
    "settings",
    "state",
]

__version__ = "0.1.0"
