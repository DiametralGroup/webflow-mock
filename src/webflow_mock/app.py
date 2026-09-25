"""Assemblage de l'application FastAPI.

┌─ UN SEUL PIPELINE DE REQUÊTE ───────────────────────────────────────────────┐
│ Toute route de la surface fournisseur passe par `_prelude` :                 │
│                                                                              │
│     évolution → observation → injections → jeton → scope → handler           │
│                                                                              │
│ Les pannes sont dispatchées AVANT l'authentification, pour qu'un             │
│ `auth_reject` puisse la préempter. Il ne peut donc pas exister de route      │
│ « oubliée » où les pannes ne s'appliqueraient pas, ni où le scope ne serait  │
│ pas vérifié.                                                                 │
└──────────────────────────────────────────────────────────────────────────────┘

┌─ DIX-HUIT OPÉRATIONS GET, ET RIEN D'AUTRE ──────────────────────────────────┐
│ La Data API v2 en compte bien davantage (écriture, e-commerce, membres,      │
│ commentaires, branches, webhooks…). Le mock sert ce qu'un connecteur         │
│ ANALYTIQUE lit : le jeton, le site, ses pages, ses collections CMS et leurs  │
│ éléments, ses formulaires et leurs soumissions. Les écritures rendent 404    │
│ au dialecte Webflow — le fournisseur, lui, les servirait ; l'écart est       │
│ inscrit dans docs/EXTRACTION.md.                                             │
└──────────────────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from .auth import jeton_de_l_entete, jeton_est_valide, scope_accorde
from .errors import (
    entetes_debit,
    erreur,
    erreur_debit,
    erreur_interne,
    erreur_introuvable,
    erreur_jeton,
    erreur_republication,
    erreur_scope,
    erreur_validation,
)
from .injection import engine
from .models import (
    REPONSES_ERREUR,
    Collection,
    CollectionItem,
    Form,
    FormSubmission,
    ListeCollections,
    ListeCustomDomains,
    ListeForms,
    ListeFormSubmissions,
    ListeItems,
    ListePages,
    ListeSites,
    Page,
    Site,
    TokenIntrospection,
    Utilisateur,
)
from .pagination import ParametreInvalide, limite_demandee, offset_demande, paginer
from .settings import settings
from .state import state

PREFIXE = "/v2"
VERSION = "0.2.0"

#: Les requêtes de la fenêtre glissante — pour `X-RateLimit-Remaining`.
_fenetre: deque[float] = deque()


# ═════════════════════════════════════════════════════════════════════════════
#  Le pipeline de requête
# ═════════════════════════════════════════════════════════════════════════════


def _restant() -> int:
    maintenant = engine.now()
    while _fenetre and _fenetre[0] < maintenant - settings.rate_window:
        _fenetre.popleft()
    return settings.rate_limit - len(_fenetre)


def _entetes_debit_courants() -> dict[str, str]:
    """Les en-têtes `X-RateLimit-*`, sur TOUTE réponse.

    Le fournisseur les sert même sur un 200 : c'est ce qui permet à un client
    de se réguler AVANT de se faire limiter. Un mock qui ne les servirait que
    sur les 429 apprendrait au consommateur à ne pas les lire.
    """
    return entetes_debit(settings.rate_limit, _restant())


def _dispatch_injections(chemin: str, rang: int) -> Response | None:
    """Le point de dispatch unique, évalué avant l'authentification."""
    if (regle := engine.first("latency", chemin)) is not None and regle.consume():
        time.sleep(regle.seconds)

    regle = engine.first("rate_limit", chemin)
    if regle is not None and rang > regle.after_requests and regle.consume():
        # `X-RateLimit-Remaining: 0` sur un 429 — par définition.
        return erreur_debit(regle.retry_after_seconds, entetes_debit(settings.rate_limit, 0))

    if (regle := engine.first("auth_reject", chemin)) is not None and regle.consume():
        return erreur_jeton()

    if (regle := engine.first("scope_reject", chemin)) is not None and regle.consume():
        return erreur_scope([regle.scope_manquant])

    if (regle := engine.first("republish_required", chemin)) is not None and regle.consume():
        return erreur_republication()

    if (regle := engine.first("status", chemin)) is not None and regle.consume():
        code = "internal_error" if regle.status >= 500 else "bad_request"
        return erreur(regle.status, code, f"Injected failure ({regle.status})")
    return None


def _prelude(request: Request, chemin: str, scope: str | None) -> Response | None:
    """Le pipeline commun. Rend `None` quand la requête peut passer."""
    parametres = dict(request.query_params)
    state.avancer_evolution(engine.now())
    rang = engine.observe(chemin, parametres)
    _fenetre.append(engine.now())

    if (refus := _dispatch_injections(chemin, rang)) is not None:
        return refus

    jeton = jeton_de_l_entete(request.headers.get("Authorization"))
    if not jeton_est_valide(jeton):
        return erreur_jeton()
    if not scope_accorde(scope):
        return erreur_scope([scope or ""])
    return None


def _ok(contenu: Any) -> JSONResponse:
    return JSONResponse(content=contenu, headers=_entetes_debit_courants())


def _servir(element: dict[str, Any], *, sans: tuple[str, ...] = ()) -> dict[str, Any]:
    """Retire les clés INTERNES (préfixe `_`) — elles n'existent pas chez le
    fournisseur — et celles que la route ne sert pas."""
    return {k: v for k, v in element.items() if not k.startswith("_") and k not in sans}


def _page(
    elements: list[dict[str, Any]], request: Request, *, cle: str, chemin: str
) -> dict[str, Any] | Response:
    """Pagine une liste DÉJÀ triée et filtrée, avec la dérive injectée."""
    try:
        limite = limite_demandee(request.query_params.get("limit"))
        offset = offset_demande(request.query_params.get("offset"))
    except ParametreInvalide as exc:
        return erreur_validation(str(exc))

    regle = engine.first("page_drift", chemin)
    derive = regle is not None and offset > 0 and offset // max(1, limite) >= regle.after_page
    if derive and regle is not None and elements and regle.consume():
        if regle.mode == "insert":
            # Un élément nouveau EN TÊTE : la dernière ligne de la page
            # précédente revient — un doublon, sans erreur.
            elements = [elements[min(offset, len(elements)) - 1], *elements]
        else:
            # Un élément retiré EN TÊTE : une ligne saute — perdue, sans erreur.
            elements = elements[1:]
    return paginer(elements, cle=cle, limite=limite, offset=offset)


def _site_ou_404(site_id: str) -> dict[str, Any] | JSONResponse:
    site: dict[str, Any] = state.dataset["sites"][0]
    if site_id != site["id"]:
        return erreur_introuvable("site")
    return site


# ═════════════════════════════════════════════════════════════════════════════
#  Les paramètres de requête, déclarés POUR LE CONTRAT
# ═════════════════════════════════════════════════════════════════════════════
#
# ┌─ POURQUOI ILS NE SONT PAS DANS LA SIGNATURE DES HANDLERS ──────────────────┐
# │ Déclarer `limit: int` en argument ferait valider FastAPI À NOTRE PLACE, et │
# │ un `limit=abc` rendrait le 422 de FastAPI — une forme d'erreur qui         │
# │ n'existe pas chez Webflow, où c'est un 400 `validation_error`. Le mock     │
# │ apprendrait au consommateur une gestion d'erreur fausse.                  │
# └────────────────────────────────────────────────────────────────────────────┘


def _param(nom: str, type_: str, description: str, **extra: Any) -> dict[str, Any]:
    return {
        "name": nom,
        "in": "query",
        "required": False,
        "schema": {"type": type_, **extra},
        "description": description,
    }


def _params_pagination() -> list[dict[str, Any]]:
    return [
        _param(
            "offset",
            "integer",
            "Décalage de pagination. Défaut 0. Un offset au-delà du total rend une page vide.",
            minimum=0,
        ),
        _param(
            "limit",
            "integer",
            "Taille de page. Défaut 100, entre 1 et 100. Hors bornes → 400 `validation_error`.",
            minimum=1,
            maximum=100,
        ),
    ]


def _params_items() -> list[dict[str, Any]]:
    return [
        *_params_pagination(),
        _param("name", "string", "Filtre d'égalité EXACTE sur `fieldData.name`."),
        _param("slug", "string", "Filtre d'égalité EXACTE sur `fieldData.slug`."),
        _param("cmsLocaleId", "string", "La locale CMS des éléments demandés."),
        _param(
            "sortBy",
            "string",
            "`createdOn`, `lastPublished`, `lastUpdated`, `name` ou `slug`.",
            enum=["createdOn", "lastPublished", "lastUpdated", "name", "slug"],
        ),
        _param("sortOrder", "string", "`asc` ou `desc`.", enum=["asc", "desc"]),
    ]


# ═════════════════════════════════════════════════════════════════════════════
#  L'application
# ═════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Webflow Data API v2 — mock",
    version=VERSION,
    description=(
        "Mock de la Data API Webflow v2 (lecture seule) sur le site vitrine de "
        "« Boréal Conseil ». Pagination `offset`/`limit`/`total`, identifiants en "
        "chaînes, erreurs `{message, code, externalReference, details}`, scopes "
        "granulaires, soumissions de formulaires nominatives."
    ),
    docs_url="/docs",
    redoc_url=None,
)
routeur = APIRouter()


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    """Sonde de vivacité — NON authentifiée, hors de la surface fournisseur."""
    return {"status": "ok", "service": "webflow-mock"}


@app.exception_handler(StarletteHTTPException)
async def _erreur_http(request: Request, exc: StarletteHTTPException) -> Response:
    """Routes et méthodes inconnues : l'enveloppe Webflow, pas le 404 FastAPI."""
    del request
    if exc.status_code in (404, 405):
        return erreur_introuvable()
    return erreur(exc.status_code, "bad_request", str(exc.detail))


# ── Jeton ────────────────────────────────────────────────────────────────────


@routeur.get(
    f"{PREFIXE}/token/authorized_by",
    response_model=Utilisateur,
    responses=REPONSES_ERREUR,
    tags=["Token"],
    summary="L'utilisateur qui a autorisé le jeton",
)
def authorized_by(request: Request) -> Any:
    chemin = f"{PREFIXE}/token/authorized_by"
    if (refus := _prelude(request, chemin, "authorized_user:read")) is not None:
        return refus
    return _ok(state.dataset["authorized_user"])


@routeur.get(
    f"{PREFIXE}/token/introspect",
    response_model=TokenIntrospection,
    responses=REPONSES_ERREUR,
    tags=["Token"],
    summary="Ce que le jeton peut faire, et sur quoi",
)
def introspect(request: Request) -> Any:
    """Quels scopes, quels sites — pour un jeton d'APPLICATION seulement.

    Aucun scope requis. Mais un site token y reçoit 500 (cf. ci-dessous) : le
    test de fumée d'un connecteur à site token est `/sites`, pas cet endpoint.
    """
    chemin = f"{PREFIXE}/token/introspect"
    if (refus := _prelude(request, chemin, None)) is not None:
        return refus
    if settings.token_kind == "site":
        # ┌─ UN SITE TOKEN N'A PAS D'INTROSPECTION ─────────────────────────────┐
        # │ Sondé le 2026-09-25 : 500 `internal_error`, « An Internal Error     │
        # │ Occurred ». La référence réserve l'endpoint aux applications Data   │
        # │ Client. Un connecteur qui en fait son test de fumée échoue AVANT    │
        # │ d'avoir rien lu — avec un jeton pourtant valide. `authorized_by`   │
        # │ et `/sites` répondent, eux.                                          │
        # └──────────────────────────────────────────────────────────────────────┘
        return erreur_interne()
    corps = state.dataset["introspection"]
    autorisation = {**corps["authorization"], "scope": ",".join(sorted(settings.scopes))}
    return _ok({"authorization": autorisation, "application": corps["application"]})


# ── Sites ────────────────────────────────────────────────────────────────────


@routeur.get(
    f"{PREFIXE}/sites",
    response_model=ListeSites,
    responses=REPONSES_ERREUR,
    tags=["Sites"],
    summary="Les sites autorisés au jeton — NON paginée",
)
def sites(request: Request) -> Any:
    chemin = f"{PREFIXE}/sites"
    if (refus := _prelude(request, chemin, "sites:read")) is not None:
        return refus
    return _ok({"sites": [_servir(s) for s in state.dataset["sites"]]})


@routeur.get(
    f"{PREFIXE}/sites/{{site_id}}",
    response_model=Site,
    responses=REPONSES_ERREUR,
    tags=["Sites"],
    summary="Un site",
)
def site(site_id: str, request: Request) -> Any:
    chemin = f"{PREFIXE}/sites/{site_id}"
    if (refus := _prelude(request, chemin, "sites:read")) is not None:
        return refus
    trouve = _site_ou_404(site_id)
    if isinstance(trouve, Response):
        return trouve
    return _ok(_servir(trouve))


@routeur.get(
    f"{PREFIXE}/sites/{{site_id}}/custom_domains",
    response_model=ListeCustomDomains,
    responses=REPONSES_ERREUR,
    tags=["Sites"],
    summary="Les domaines personnalisés — NON paginée",
)
def custom_domains(site_id: str, request: Request) -> Any:
    chemin = f"{PREFIXE}/sites/{site_id}/custom_domains"
    if (refus := _prelude(request, chemin, "sites:read")) is not None:
        return refus
    trouve = _site_ou_404(site_id)
    if isinstance(trouve, Response):
        return trouve
    return _ok({"customDomains": trouve["customDomains"]})


# ── Pages ────────────────────────────────────────────────────────────────────


def _pages_de_la_locale(locale_id: str | None) -> list[dict[str, Any]] | None:
    """Les pages dans la locale demandée — la primaire sans paramètre."""
    site = state.dataset["sites"][0]
    if not locale_id or locale_id == site["locales"]["primary"]["id"]:
        return list(state.dataset["pages"])
    if any(loc["id"] == locale_id for loc in site["locales"]["secondary"]):
        return list(state.dataset["pages_en"])
    return None


@routeur.get(
    f"{PREFIXE}/sites/{{site_id}}/pages",
    response_model=ListePages,
    responses=REPONSES_ERREUR,
    tags=["Pages"],
    summary="Les pages d'un site",
    openapi_extra={
        "parameters": [
            _param(
                "localeId",
                "string",
                "La locale des pages demandées ; la primaire par défaut. Une page est "
                "UNE entité : même `id` dans chaque locale.",
            ),
            *_params_pagination(),
        ]
    },
)
def pages(site_id: str, request: Request) -> Any:
    chemin = f"{PREFIXE}/sites/{site_id}/pages"
    if (refus := _prelude(request, chemin, "pages:read")) is not None:
        return refus
    if isinstance(trouve := _site_ou_404(site_id), Response):
        return trouve
    liste = _pages_de_la_locale(request.query_params.get("localeId"))
    if liste is None:
        return erreur_introuvable("locale")
    resultat = _page(liste, request, cle="pages", chemin=chemin)
    if isinstance(resultat, Response):
        return resultat
    return _ok(resultat)


@routeur.get(
    f"{PREFIXE}/pages/{{page_id}}",
    response_model=Page,
    responses=REPONSES_ERREUR,
    tags=["Pages"],
    summary="Les métadonnées d'une page",
    openapi_extra={"parameters": [_param("localeId", "string", "La locale de la variante.")]},
)
def page(page_id: str, request: Request) -> Any:
    chemin = f"{PREFIXE}/pages/{page_id}"
    if (refus := _prelude(request, chemin, "pages:read")) is not None:
        return refus
    liste = _pages_de_la_locale(request.query_params.get("localeId"))
    if liste is None:
        return erreur_introuvable("locale")
    element = next((p for p in liste if p["id"] == page_id), None)
    if element is None:
        return erreur_introuvable("page")
    return _ok(_servir(element))


# ── CMS ──────────────────────────────────────────────────────────────────────


def _collection_ou_none(collection_id: str) -> dict[str, Any] | None:
    return next((c for c in state.dataset["collections"] if c["id"] == collection_id), None)


@routeur.get(
    f"{PREFIXE}/sites/{{site_id}}/collections",
    response_model=ListeCollections,
    responses=REPONSES_ERREUR,
    tags=["CMS"],
    summary="Les collections d'un site — NON paginée, SANS les champs",
)
def collections(site_id: str, request: Request) -> Any:
    chemin = f"{PREFIXE}/sites/{site_id}/collections"
    if (refus := _prelude(request, chemin, "cms:read")) is not None:
        return refus
    if isinstance(trouve := _site_ou_404(site_id), Response):
        return trouve
    return _ok(
        {"collections": [_servir(c, sans=("fields",)) for c in state.dataset["collections"]]}
    )


@routeur.get(
    f"{PREFIXE}/collections/{{collection_id}}",
    response_model=Collection,
    responses=REPONSES_ERREUR,
    tags=["CMS"],
    summary="Une collection, AVEC ses champs",
)
def collection(collection_id: str, request: Request) -> Any:
    chemin = f"{PREFIXE}/collections/{collection_id}"
    if (refus := _prelude(request, chemin, "cms:read")) is not None:
        return refus
    trouve = _collection_ou_none(collection_id)
    if trouve is None:
        return erreur_introuvable("collection")
    return _ok(_servir(trouve))


def _elements_filtres(
    collection_id: str, request: Request, *, publies: bool
) -> list[dict[str, Any]] | Response:
    """Les éléments d'une collection : filtrés, triés — puis paginés par l'appelant."""
    if _collection_ou_none(collection_id) is None:
        return erreur_introuvable("collection")
    elements = list(state.dataset["items"].get(collection_id, []))
    if publies:
        # `/items/live` : ce que les visiteurs voient. Ni brouillon, ni archivé,
        # et publié au moins une fois.
        elements = [
            e
            for e in elements
            if not e["isDraft"] and not e["isArchived"] and e["lastPublished"] is not None
        ]
    q = request.query_params
    if q.get("cmsLocaleId"):
        elements = [e for e in elements if e["cmsLocaleId"] in q["cmsLocaleId"].split(",")]
    if q.get("name"):
        elements = [e for e in elements if e["fieldData"].get("name") == q["name"]]
    if q.get("slug"):
        elements = [e for e in elements if e["fieldData"].get("slug") == q["slug"]]
    tri = q.get("sortBy")
    if tri:
        if tri not in {"createdOn", "lastPublished", "lastUpdated", "name", "slug"}:
            return erreur_validation(
                "sortBy must be one of createdOn, lastPublished, lastUpdated, name, slug"
            )
        ordre = q.get("sortOrder", "asc")
        if ordre not in {"asc", "desc"}:
            return erreur_validation("sortOrder must be asc or desc")

        def cle_tri(e: dict[str, Any]) -> str:
            valeur = e["fieldData"].get(tri) if tri in {"name", "slug"} else e.get(tri)
            return str(valeur or "")

        elements.sort(key=cle_tri, reverse=ordre == "desc")
    return elements


def _monter_items(suffixe: str, *, publies: bool, resume: str) -> None:
    """Monte `/items` ou `/items/live`, liste et détail — même prélude, même
    scope, même pagination. La fabrique lie `publies` à chaque montage."""
    base = f"{PREFIXE}/collections/{{collection_id}}/items{suffixe}"

    @routeur.get(
        base,
        response_model=ListeItems,
        responses=REPONSES_ERREUR,
        tags=["CMS"],
        summary=resume,
        name=f"list_items{suffixe.replace('/', '_')}",
        openapi_extra={"parameters": _params_items()},
    )
    def lister(collection_id: str, request: Request) -> Any:
        chemin = f"{PREFIXE}/collections/{collection_id}/items{suffixe}"
        if (refus := _prelude(request, chemin, "cms:read")) is not None:
            return refus
        elements = _elements_filtres(collection_id, request, publies=publies)
        if isinstance(elements, Response):
            return elements
        resultat = _page(elements, request, cle="items", chemin=chemin)
        if isinstance(resultat, Response):
            return resultat
        return _ok(resultat)

    @routeur.get(
        base + "/{item_id}",
        response_model=CollectionItem,
        responses=REPONSES_ERREUR,
        tags=["CMS"],
        summary=f"{resume} — un élément",
        name=f"get_item{suffixe.replace('/', '_')}",
    )
    def detail(collection_id: str, item_id: str, request: Request) -> Any:
        chemin = f"{PREFIXE}/collections/{collection_id}/items{suffixe}/{item_id}"
        if (refus := _prelude(request, chemin, "cms:read")) is not None:
            return refus
        elements = _elements_filtres(collection_id, request, publies=publies)
        if isinstance(elements, Response):
            return elements
        element = next((e for e in elements if e["id"] == item_id), None)
        if element is None:
            return erreur_introuvable("item")
        return _ok(element)


# `/items/live` AVANT `/items/{item_id}` : sans cet ordre, Starlette prend
# `live` pour un identifiant d'élément et rend 404 sur la route la plus utile.
_monter_items("/live", publies=True, resume="Les éléments PUBLIÉS — ce que les visiteurs voient")
_monter_items("", publies=False, resume="Les éléments PRÉPARÉS (brouillons et archivés compris)")


# ── Formulaires ──────────────────────────────────────────────────────────────


def _formulaires_ou_409() -> list[dict[str, Any]] | Response:
    if settings.forms_require_republish:
        return erreur_republication()
    return list(state.dataset["forms"])


@routeur.get(
    f"{PREFIXE}/sites/{{site_id}}/forms",
    response_model=ListeForms,
    responses=REPONSES_ERREUR,
    tags=["Forms"],
    summary="Les formulaires d'un site",
    openapi_extra={"parameters": _params_pagination()},
)
def forms(site_id: str, request: Request) -> Any:
    chemin = f"{PREFIXE}/sites/{site_id}/forms"
    if (refus := _prelude(request, chemin, "forms:read")) is not None:
        return refus
    if isinstance(trouve := _site_ou_404(site_id), Response):
        return trouve
    liste = _formulaires_ou_409()
    if isinstance(liste, Response):
        return liste
    resultat = _page([_servir(f) for f in liste], request, cle="forms", chemin=chemin)
    if isinstance(resultat, Response):
        return resultat
    return _ok(resultat)


@routeur.get(
    f"{PREFIXE}/forms/{{form_id}}",
    response_model=Form,
    responses=REPONSES_ERREUR,
    tags=["Forms"],
    summary="Un formulaire",
)
def form(form_id: str, request: Request) -> Any:
    chemin = f"{PREFIXE}/forms/{form_id}"
    if (refus := _prelude(request, chemin, "forms:read")) is not None:
        return refus
    liste = _formulaires_ou_409()
    if isinstance(liste, Response):
        return liste
    element = next((f for f in liste if f["id"] == form_id), None)
    if element is None:
        return erreur_introuvable("form")
    return _ok(_servir(element))


@routeur.get(
    f"{PREFIXE}/forms/{{form_id}}/submissions",
    response_model=ListeFormSubmissions,
    responses=REPONSES_ERREUR,
    tags=["Forms"],
    summary="Les soumissions d'un formulaire — de la plus récente à la plus ancienne",
    openapi_extra={"parameters": _params_pagination()},
)
def submissions(form_id: str, request: Request) -> Any:
    chemin = f"{PREFIXE}/forms/{form_id}/submissions"
    if (refus := _prelude(request, chemin, "forms:read")) is not None:
        return refus
    liste = _formulaires_ou_409()
    if isinstance(liste, Response):
        return liste
    if not any(f["id"] == form_id for f in liste):
        return erreur_introuvable("form")
    elements = [s for s in state.dataset["form_submissions"] if s["formId"] == form_id]
    resultat = _page(elements, request, cle="formSubmissions", chemin=chemin)
    if isinstance(resultat, Response):
        return resultat
    return _ok(resultat)


@routeur.get(
    f"{PREFIXE}/sites/{{site_id}}/form_submissions",
    response_model=ListeFormSubmissions,
    responses=REPONSES_ERREUR,
    tags=["Forms"],
    summary="Toutes les soumissions d'un site — de la plus récente à la plus ancienne",
    openapi_extra={
        "parameters": [
            _param(
                "elementId",
                "string",
                "Ne garder que les soumissions d'un élément de formulaire (`formElementId`).",
            ),
            *_params_pagination(),
        ]
    },
)
def site_submissions(site_id: str, request: Request) -> Any:
    chemin = f"{PREFIXE}/sites/{site_id}/form_submissions"
    if (refus := _prelude(request, chemin, "forms:read")) is not None:
        return refus
    if isinstance(trouve := _site_ou_404(site_id), Response):
        return trouve
    liste = _formulaires_ou_409()
    if isinstance(liste, Response):
        return liste
    elements = list(state.dataset["form_submissions"])
    if element_id := request.query_params.get("elementId"):
        formulaires = {f["id"] for f in liste if f["formElementId"] == element_id}
        elements = [s for s in elements if s["formId"] in formulaires]
    resultat = _page(elements, request, cle="formSubmissions", chemin=chemin)
    if isinstance(resultat, Response):
        return resultat
    return _ok(resultat)


@routeur.get(
    f"{PREFIXE}/form_submissions/{{form_submission_id}}",
    response_model=FormSubmission,
    responses=REPONSES_ERREUR,
    tags=["Forms"],
    summary="Une soumission",
)
def submission(form_submission_id: str, request: Request) -> Any:
    chemin = f"{PREFIXE}/form_submissions/{form_submission_id}"
    if (refus := _prelude(request, chemin, "forms:read")) is not None:
        return refus
    if isinstance(liste := _formulaires_ou_409(), Response):
        return liste
    element = next(
        (s for s in state.dataset["form_submissions"] if s["id"] == form_submission_id), None
    )
    if element is None:
        return erreur_introuvable("form submission")
    return _ok(element)


app.include_router(routeur)

# Le plan de contrôle n'est pas « monté puis interdit » : quand il est
# désactivé, la surface n'existe pas. C'est ce qui rend impossible de le
# laisser ouvert par accident sur un cluster.
if settings.admin_enabled:
    from .admin import router as admin_router

    app.include_router(admin_router)


# ═════════════════════════════════════════════════════════════════════════════
#  Le contrat
# ═════════════════════════════════════════════════════════════════════════════


def contrat_openapi() -> dict[str, Any]:
    """Le contrat PUBLIÉ — la surface fournisseur, et elle seule.

    `/__admin` et `/health` sont des affordances du MOCK : les publier ferait
    passer pour de l'API Webflow ce qui n'en est pas, et `/__admin` n'est
    monté que conditionnellement — le contrat dépendrait alors de
    l'environnement de génération.
    """
    schema = app.openapi()
    chemins = {
        chemin: operations
        for chemin, operations in schema["paths"].items()
        if chemin.startswith(PREFIXE)
    }
    contrat: dict[str, Any] = {
        "openapi": schema["openapi"],
        "info": dict(schema["info"]),
        "servers": [{"url": "https://api.webflow.com"}],
        "paths": chemins,
    }
    composants = schema.get("components", {})
    if composants:
        contrat["components"] = _elaguer_schemas(composants, chemins)
    return contrat


def _elaguer_schemas(composants: dict[str, Any], chemins: dict[str, Any]) -> dict[str, Any]:
    """Retire les schémas devenus orphelins après le retrait de /__admin."""
    import json
    import re

    schemas = dict(composants.get("schemas", {}))
    utilises: set[str] = set()
    a_visiter = set(re.findall(r"#/components/schemas/([A-Za-z0-9_.\[\]-]+)", json.dumps(chemins)))
    while a_visiter:
        nom = a_visiter.pop()
        if nom in utilises or nom not in schemas:
            continue
        utilises.add(nom)
        a_visiter |= set(
            re.findall(r"#/components/schemas/([A-Za-z0-9_.\[\]-]+)", json.dumps(schemas[nom]))
        )
    resultat = dict(composants)
    resultat["schemas"] = {nom: schemas[nom] for nom in sorted(utilises)}
    return resultat
