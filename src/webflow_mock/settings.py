"""Configuration — tout par variables d'environnement, aucun fichier.

Même mécanique que les cinq autres mocks de l'écosystème : un objet relu à
chaud par `reload()`, pour qu'un test puisse changer une valeur sans recharger
le module. C'est aussi le seul mécanisme qui marche identiquement en docker
compose, en Deployment Kubernetes et en service GitHub Actions.

Le préfixe est `WEBFLOW_MOCK_*`. Il n'y a délibérément AUCUN `.env.example`
ici : le fichier d'exemple vit chez le consommateur (insights360), parce que
c'est lui qui doit documenter comment brancher les sources ensemble.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

#: Le jeton par défaut. Statique — un « site token » Webflow est un bearer
#: longue durée généré dans les réglages du site (Apps & integrations), pas un
#: jeton de session (cf. docs/EXTRACTION.md §auth).
JETON_DEFAUT = "mock-webflow-token"

#: Les scopes en LECTURE de la surface servie, relevés sur
#: https://developers.webflow.com/data/reference/scopes (état 2026-09-24).
#: C'est le périmètre par défaut du mock : un consommateur en lecture les a
#: tous. `users`, `ecommerce`, `comments`, `assets`, `components`,
#: `custom_code`, `site_activity`, `workspace` ne sont pas servis : Boréal
#: Conseil n'a ni boutique ni espace membres, et un connecteur analytique n'en
#: lit rien.
SCOPES_LECTURE: tuple[str, ...] = (
    "authorized_user:read",
    "sites:read",
    "pages:read",
    "cms:read",
    "forms:read",
)


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    """État de configuration, relu à chaud par `reload()`."""

    token: str = ""

    #: Scopes portés par le jeton. Le levier « 403 » du mock : retirer un scope
    #: reproduit un jeton à périmètre restreint, exactement comme chez le
    #: fournisseur — un « site token » se génère case par case, et oublier
    #: `forms:read` est la panne la plus fréquente en intégration réelle.
    scopes: frozenset[str] = frozenset()

    seed: int = 42

    # Plan de contrôle /__admin. Fermé par défaut : il n'a de sens qu'en test.
    admin_enabled: bool = False
    admin_token: str = "mock-admin-token"

    # ── Pagination ───────────────────────────────────────────────────────────
    # `limit` par défaut 100 et plafond 100 : c'est ce que la référence déclare
    # sur chaque liste paginée (« max limit: 100 », « default: 100 »). Deux
    # réglages quand même, parce que le défaut se voit dans `pagination.limit`
    # et qu'un consommateur doit pouvoir éprouver un défaut plus bas.
    #
    # Sondé le 2026-09-25 : `limit` AU-DELÀ du plafond est RABOTÉ en silence
    # (`limit=101` → 200, `pagination.limit: 100`), tandis qu'un `limit` nul,
    # négatif ou illisible rend 400 `validation_error` avec le motif de
    # validation dans le message. Les deux se reproduisent tels quels.
    limite_defaut: int = 100
    limite_max: int = 100

    #: Limite de débit — 60 requêtes / minute au jeton (offres Starter et
    #: Basic ; 120 sur CMS/Business). Les en-têtes `X-RateLimit-*` partent sur
    #: chaque réponse, pas seulement sur les 429.
    rate_limit: int = 60
    rate_window: float = 60.0

    #: Ce que le site rapporte de lui-même.
    site_name: str = "Boréal Conseil"
    site_short_name: str = "boreal-conseil"
    site_domain: str = "www.boreal-conseil.example"

    #: La NATURE du jeton : `site` (un site token, généré dans les réglages du
    #: site) ou `oauth` (un jeton d'application Data Client). Sondé le
    #: 2026-09-25 contre l'API réelle : avec un site token,
    #: `GET /token/introspect` rend **500 `internal_error`** — la référence le
    #: réserve aux applications. Un connecteur qui s'en sert comme test de
    #: fumée échoue donc avant d'avoir rien lu. `authorized_by`, lui, répond.
    token_kind: str = "site"

    #: Un site dont les formulaires exigent une republication. Chez le
    #: fournisseur, `/sites/{id}/forms` rend 409 `forms_require_republish` tant
    #: que le site n'a pas été republié depuis l'arrivée de la fonctionnalité.
    #: Faux par défaut ; c'est un mode de panne, à injecter ou à activer ici.
    forms_require_republish: bool = False

    # ── Évolution temporelle (extraction incrémentale) ───────────────────────
    # Le jeu de données VIT : un événement scripté toutes les
    # `evolution_interval` secondes (une soumission de formulaire, un article
    # publié, une page retouchée…). Mettre à false — ou l'intervalle à 0 —
    # fige le jeu de données pour les usages qui exigent un contenu stable à
    # l'octet près (le gate d'idempotence d'insights360).
    evolution_enabled: bool = True
    evolution_interval: float = 60.0

    extra: dict[str, str] = field(default_factory=dict)

    def reload(self) -> None:
        self.token = os.environ.get("WEBFLOW_MOCK_TOKEN", JETON_DEFAUT)
        brut = os.environ.get("WEBFLOW_MOCK_SCOPES")
        self.scopes = (
            frozenset(SCOPES_LECTURE)
            if brut is None
            else frozenset(s.strip() for s in brut.split(",") if s.strip())
        )
        self.seed = int(os.environ.get("WEBFLOW_MOCK_SEED", "42"))
        self.admin_enabled = _flag("WEBFLOW_MOCK_ADMIN_ENABLED", False)
        self.admin_token = os.environ.get("WEBFLOW_MOCK_ADMIN_TOKEN", "mock-admin-token")
        self.limite_defaut = int(os.environ.get("WEBFLOW_MOCK_DEFAULT_LIMIT", "100"))
        self.limite_max = int(os.environ.get("WEBFLOW_MOCK_MAX_LIMIT", "100"))
        self.rate_limit = int(os.environ.get("WEBFLOW_MOCK_RATE_LIMIT", "60"))
        self.rate_window = float(os.environ.get("WEBFLOW_MOCK_RATE_WINDOW", "60"))
        self.site_name = os.environ.get("WEBFLOW_MOCK_SITE", "Boréal Conseil")
        self.site_short_name = os.environ.get("WEBFLOW_MOCK_SITE_SHORT_NAME", "boreal-conseil")
        self.site_domain = os.environ.get("WEBFLOW_MOCK_SITE_DOMAIN", "www.boreal-conseil.example")
        self.token_kind = os.environ.get("WEBFLOW_MOCK_TOKEN_KIND", "site")
        self.forms_require_republish = _flag("WEBFLOW_MOCK_FORMS_REQUIRE_REPUBLISH", False)
        self.evolution_enabled = _flag("WEBFLOW_MOCK_EVOLUTION_ENABLED", True)
        self.evolution_interval = float(os.environ.get("WEBFLOW_MOCK_EVOLUTION_INTERVAL", "60"))


settings = Settings()
settings.reload()
