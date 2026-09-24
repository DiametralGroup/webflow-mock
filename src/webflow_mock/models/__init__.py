"""Les modèles pydantic — la SOURCE du contrat publié.

Typer donne d'un coup le contrat OpenAPI, la page /docs et des formes
exploitables par les consommateurs. Mais typer POUSSE À INVENTER : dès qu'un
champ manque à la documentation, la tentation est de le déduire. La parade est
structurelle, et c'est la même que dans les cinq autres mocks :

  • `extra="allow"` partout — le modèle décrit ce qu'on SAIT, pas ce qui EST ;
  • `x-webflow-confidence` sur tout champ non adossé à la référence officielle ;
  • un test échoue si un champ `unverified` n'est pas inscrit dans
    docs/UNVERIFIED-FIELDS.md — l'honnêteté est une contrainte de build.
"""

from __future__ import annotations

from .common import (
    REPONSES_ERREUR,
    ErreurWebflow,
    Pagination,
    Permissif,
    invented,
    unverified,
)
from .entities import (
    Collection,
    CollectionField,
    CollectionItem,
    CustomDomain,
    Form,
    FormField,
    FormSubmission,
    ListeCollections,
    ListeCustomDomains,
    ListeForms,
    ListeFormSubmissions,
    ListeItems,
    ListePages,
    ListeSites,
    Locale,
    Locales,
    OpenGraph,
    Page,
    ResponseSettings,
    Seo,
    Site,
    TokenIntrospection,
    Utilisateur,
)

__all__ = [
    "REPONSES_ERREUR",
    "Collection",
    "CollectionField",
    "CollectionItem",
    "CustomDomain",
    "ErreurWebflow",
    "Form",
    "FormField",
    "FormSubmission",
    "ListeCollections",
    "ListeCustomDomains",
    "ListeFormSubmissions",
    "ListeForms",
    "ListeItems",
    "ListePages",
    "ListeSites",
    "Locale",
    "Locales",
    "OpenGraph",
    "Page",
    "Pagination",
    "Permissif",
    "ResponseSettings",
    "Seo",
    "Site",
    "TokenIntrospection",
    "Utilisateur",
    "invented",
    "unverified",
]
