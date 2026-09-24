"""Le plan de contrôle `/__admin` — hors de la surface fournisseur.

Il existe pour une raison précise : le mock tourne en CONTENEUR chez son
consommateur (docker compose, service GitHub Actions, Deployment de dev). Hors
du processus, un test ne peut plus muter l'état en Python — il lui faut du
HTTP. Sans ce plan, éprouver un 429 ou une extraction incrémentale depuis
insights360 serait impossible.

Il est FERMÉ par défaut (`WEBFLOW_MOCK_ADMIN_ENABLED`), et quand il est fermé
la surface n'existe pas du tout — cf. le montage conditionnel dans `app.py`.
Le préfixe `__admin` ne peut collisionner avec aucun chemin Webflow, qui
vivent tous sous `/v2`.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .injection import Kind, engine
from .settings import settings
from .state import state

router = APIRouter(prefix="/__admin", include_in_schema=False, tags=["mock control plane"])


def _refuse(jeton: str | None) -> JSONResponse | None:
    if jeton != settings.admin_token:
        return JSONResponse(
            status_code=403,
            content={
                "message": "Forbidden",
                "code": "forbidden",
                "externalReference": None,
                "details": [],
            },
        )
    return None


class DemandeReset(BaseModel):
    seed: int | None = None


class DemandeInjection(BaseModel):
    """Une règle d'injection. `times` absent = panne PERSISTANTE.

    La distinction porte tout : une panne transitoire doit être absorbée par le
    retry du consommateur et laisser le run vert ; une panne persistante doit
    le faire échouer avec un code de sortie non nul. Les deux se testent, et
    elles ne se testent pas avec la même règle.
    """

    kind: Kind
    scope: str = "*"
    times: int | None = None
    after_requests: int = 0
    retry_after_seconds: int = 60
    status: int = 500
    seconds: float = 0.0
    after_page: int = 1
    mode: Literal["insert", "remove"] = "insert"
    scope_manquant: str = "forms:read"


class DemandeHorloge(BaseModel):
    advance_seconds: float = Field(description="Décalage à AJOUTER à l'horloge virtuelle du mock.")


class DemandeMutation(BaseModel):
    """Mute un élément et pousse son `lastUpdated` au-dessus de tous les autres.

    C'est l'outil du test d'incrémentalité : après cet appel, exactement UNE
    ligne doit être rechargée par un consommateur incrémental. Les
    soumissions de formulaire, elles, n'ont pas de `lastUpdated` : une
    soumission ne se modifie pas, elle s'ajoute — cf. `/__admin/evolve`.
    """

    collection: str
    id: str
    champs: dict[str, Any] = Field(default_factory=dict)


class DemandeEvolution(BaseModel):
    pas: int = 1


@router.post("/reset")
def reset(demande: DemandeReset, x_mock_admin_token: str | None = Header(default=None)) -> Any:
    if (refus := _refuse(x_mock_admin_token)) is not None:
        return refus
    state.reset(seed=demande.seed)
    return {"status": "reset", "seed": state.seed, "totals": state.totals()}


@router.get("/state")
def etat(x_mock_admin_token: str | None = Header(default=None)) -> Any:
    """L'observabilité du mock.

    `last_query_params_by_path` est la clé de voûte des tests aval : c'est ce
    qui permet de PROUVER qu'un consommateur a bien envoyé son `offset` et son
    `limit`. Sans cette preuve, un pipeline qui aurait oublié de paginer
    passerait tous ses tests — il rechargerait simplement la première page à
    chaque fois, ce qui ne se voit dans aucune assertion portant sur le
    contenu.
    """
    if (refus := _refuse(x_mock_admin_token)) is not None:
        return refus
    return {
        "seed": state.seed,
        "totals": state.totals(),
        "request_counts_by_path": dict(engine.request_counts),
        "last_query_params_by_path": dict(engine.last_query_params),
        "injections": engine.snapshot(),
        "clock_offset": engine.clock_offset,
        "evolution": {
            "enabled": settings.evolution_enabled,
            "interval": settings.evolution_interval,
            "rang": state.evolution.rang,
            "journal": state.evolution.journal[-20:],
        },
        "scopes": sorted(settings.scopes),
        "forms_require_republish": settings.forms_require_republish,
    }


@router.post("/inject")
def injecter(
    demande: DemandeInjection, x_mock_admin_token: str | None = Header(default=None)
) -> Any:
    if (refus := _refuse(x_mock_admin_token)) is not None:
        return refus
    regle = engine.add(**demande.model_dump())
    return {"status": "injected", "rule": {"id": regle.id, **demande.model_dump()}}


@router.delete("/inject/{rule_id}")
def retirer(rule_id: str, x_mock_admin_token: str | None = Header(default=None)) -> Any:
    if (refus := _refuse(x_mock_admin_token)) is not None:
        return refus
    return {"status": "removed" if engine.remove(rule_id) else "unknown", "id": rule_id}


@router.post("/inject/clear")
def vider(x_mock_admin_token: str | None = Header(default=None)) -> Any:
    if (refus := _refuse(x_mock_admin_token)) is not None:
        return refus
    engine.clear()
    engine.reset_counters()
    return {"status": "cleared"}


@router.post("/clock")
def horloge(demande: DemandeHorloge, x_mock_admin_token: str | None = Header(default=None)) -> Any:
    """Avance l'horloge VIRTUELLE du mock.

    Les tests d'évolution ne dorment JAMAIS : ils font défiler le temps
    explicitement. C'est ce qui les rend déterministes et rapides — une suite
    qui `sleep(60)` pour voir un événement est une suite qu'on finit par
    désactiver.
    """
    if (refus := _refuse(x_mock_admin_token)) is not None:
        return refus
    engine.clock_offset += demande.advance_seconds
    state.avancer_evolution(engine.now())
    return {"status": "advanced", "clock_offset": engine.clock_offset}


@router.post("/evolve")
def evoluer(
    demande: DemandeEvolution, x_mock_admin_token: str | None = Header(default=None)
) -> Any:
    """Force N événements d'évolution, sans toucher à l'horloge."""
    if (refus := _refuse(x_mock_admin_token)) is not None:
        return refus
    state.evolution.forcer(state.dataset, demande.pas)
    state.invalider_caches()
    return {"status": "evolved", "rang": state.evolution.rang, "totals": state.totals()}


@router.post("/mutate")
def muter(
    demande: DemandeMutation,
    x_mock_admin_token: str | None = Header(default=None),
) -> Any:
    if (refus := _refuse(x_mock_admin_token)) is not None:
        return refus
    element = state.index().get((demande.collection, demande.id))
    if element is None:
        return JSONResponse(
            status_code=404,
            content={
                "message": "Requested resource not found",
                "code": "resource_not_found",
                "externalReference": None,
                "details": [],
            },
        )

    from .evolution import horodatage_de_mutation

    element.update(demande.champs)
    horodatage = horodatage_de_mutation(state.dataset.get(demande.collection, []))
    if "lastUpdated" in element:
        element["lastUpdated"] = horodatage
    state.invalider_caches()
    return {
        "status": "mutated",
        "collection": demande.collection,
        "id": demande.id,
        "lastUpdated": horodatage,
    }


@router.post("/scopes")
def scopes(
    corps: dict[str, list[str]], x_mock_admin_token: str | None = Header(default=None)
) -> Any:
    """Redéfinit les scopes du jeton — le levier « 403 » du dialecte.

    Retirer `forms:read` reproduit exactement la panne la plus fréquente en
    intégration Webflow : un site token régénéré sans une case cochée. Le
    message d'erreur NOMME le scope manquant.
    """
    if (refus := _refuse(x_mock_admin_token)) is not None:
        return refus
    settings.scopes = frozenset(corps.get("scopes", []))
    return {"status": "updated", "scopes": sorted(settings.scopes)}


@router.post("/republish")
def republication(
    corps: dict[str, bool], x_mock_admin_token: str | None = Header(default=None)
) -> Any:
    """`{"required": true}` : les routes de formulaires rendent 409 jusqu'à
    `{"required": false}` — le geste « publier le site » côté fournisseur."""
    if (refus := _refuse(x_mock_admin_token)) is not None:
        return refus
    settings.forms_require_republish = bool(corps.get("required", False))
    return {"status": "updated", "forms_require_republish": settings.forms_require_republish}
