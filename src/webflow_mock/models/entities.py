"""Les entités servies — champs relevés sur la référence officielle de la v2.

┌─ TOUS LES IDENTIFIANTS SONT DES CHAÎNES ────────────────────────────────────┐
│ `"62b720ef280c7a7a3be8cabe"` — 24 caractères hexadécimaux, jamais un        │
│ entier. Un consommateur qui déclare ses colonnes `bigint` sur la foi d'un   │
│ autre fournisseur casse à la première ligne ; un merge sur `id` typé en     │
│ entier ne trouve jamais rien. Même chose pour les horodatages : ISO 8601 en │
│ UTC avec TROIS chiffres de millisecondes et un `Z` final.                    │
└──────────────────────────────────────────────────────────────────────────────┘

┌─ camelCase PARTOUT ─────────────────────────────────────────────────────────┐
│ `displayName`, `lastUpdated`, `dateSubmitted`, `formResponse`, `isDraft`.   │
│ Un chargeur qui normalise les noms de colonnes doit le faire de façon       │
│ STABLE (dlt le fait : `lastUpdated` → `last_updated`) ; un modèle qui lit   │
│ `last_updated` dans le JSON brut ne trouve rien.                             │
└──────────────────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .common import Pagination, Permissif, unverified

# ── Jeton ────────────────────────────────────────────────────────────────────


class Utilisateur(Permissif):
    """`GET /token/authorized_by` — qui a autorisé ce jeton."""

    id: str
    email: str
    firstName: str
    lastName: str


class TokenIntrospection(Permissif):
    """`GET /token/introspect` — ce que le jeton peut faire, et sur quoi.

    `authorization.scope` est une chaîne de scopes SÉPARÉS PAR DES VIRGULES,
    pas un tableau ; `authorizedTo.siteIds` dit quels sites le jeton voit —
    un `/sites` vide n'est pas une panne, c'est un jeton autorisé sur rien.
    """

    authorization: dict[str, Any]
    application: dict[str, Any]


# ── Site ─────────────────────────────────────────────────────────────────────


class CustomDomain(Permissif):
    id: str
    url: str = Field(description="Le nom de domaine, sans schéma.")
    lastPublished: str | None = None


class Locale(Permissif):
    id: str
    cmsLocaleId: str
    enabled: bool
    displayName: str
    displayImageId: str | None = None
    redirect: bool
    subdirectory: str = Field(description='`""` pour la locale primaire, `"en"` sinon.')
    tag: str = Field(description="`fr-FR`, `en-US`…")


class Locales(Permissif):
    primary: Locale
    secondary: list[Locale]


class Site(Permissif):
    id: str
    workspaceId: str
    createdOn: str
    displayName: str
    shortName: str
    lastPublished: str | None = None
    lastUpdated: str
    previewUrl: str
    timeZone: str
    parentFolderId: str | None = None
    customDomains: list[CustomDomain]
    locales: Locales
    dataCollectionEnabled: bool
    dataCollectionType: str = Field(description="`always`, `optOut` ou `disabled`.")


class ListeSites(Permissif):
    """`GET /sites` — PAS de pagination : la liste entière, sans objet
    `pagination`. Un consommateur qui lit `body[\"pagination\"]` sans garde
    lève ici, sur la première route qu'il appelle."""

    sites: list[Site]


class ListeCustomDomains(Permissif):
    """`GET /sites/{id}/custom_domains` — non paginée non plus."""

    customDomains: list[CustomDomain]


# ── Pages ────────────────────────────────────────────────────────────────────


class Seo(Permissif):
    title: str
    description: str


class OpenGraph(Permissif):
    title: str
    titleCopied: bool
    description: str
    descriptionCopied: bool


class Page(Permissif):
    id: str
    siteId: str
    title: str
    slug: str
    parentId: str | None = Field(
        default=None,
        description="Le dossier parent ; `null` à la racine. Les dossiers ne sont PAS servis.",
    )
    collectionId: str | None = Field(
        default=None,
        description="Renseigné sur une page GABARIT de collection, `null` sinon.",
    )
    createdOn: str
    lastUpdated: str
    archived: bool = False
    draft: bool = False
    canBranch: bool = False
    isBranch: bool = False
    branchId: str | None = None
    seo: Seo
    openGraph: OpenGraph
    localeId: str | None = Field(
        default=None, description="La locale de cette variante de la page."
    )
    publishedPath: str = Field(
        description="Chemin relatif publié, préfixé du sous-répertoire de locale.",
        json_schema_extra=unverified(
            "la forme du chemin d'une page GABARIT de collection (`/blog/detail_article`) "
            "est plausible, pas attestée"
        ),
    )


class ListePages(Permissif):
    pages: list[Page]
    pagination: Pagination


# ── CMS ──────────────────────────────────────────────────────────────────────


class CollectionField(Permissif):
    id: str
    isRequired: bool
    isEditable: bool
    type: str = Field(
        description=(
            "Color, DateTime, Email, ExtFileRef, File, Image, Link, MultiImage, "
            "MultiReference, Number, Option, Phone, PlainText, Reference, RichText, "
            "Switch, VideoLink."
        )
    )
    displayName: str
    slug: str
    helpText: str | None = None
    validations: dict[str, Any] | None = None


class Collection(Permissif):
    """`GET /collections/{id}` — AVEC `fields`. La liste
    `/sites/{id}/collections`, elle, ne les porte PAS : un second appel par
    collection est nécessaire pour connaître le schéma des éléments."""

    id: str
    displayName: str
    singularName: str
    slug: str
    createdOn: str
    lastUpdated: str
    fields: list[CollectionField]


class CollectionResume(Permissif):
    """L'élément de `/sites/{id}/collections` — sans `fields`."""

    id: str
    displayName: str
    singularName: str
    slug: str
    createdOn: str
    lastUpdated: str


class ListeCollections(Permissif):
    """`GET /sites/{id}/collections` — non paginée."""

    collections: list[CollectionResume]


class CollectionItem(Permissif):
    """Un élément de collection.

    `fieldData` est LIBRE : ses clés sont les `slug` des champs de la
    collection, et seuls `name` et `slug` sont garantis. Un champ `Reference`
    y vaut l'ID de l'élément visé, un `Option` l'ID de l'option, un `Image`
    un objet `{fileId, url, alt}`. Le schéma se lit dans la collection, pas
    dans l'élément.
    """

    id: str
    cmsLocaleId: str
    lastPublished: str | None = Field(
        default=None, description="`null` tant que l'élément n'a jamais été publié."
    )
    lastUpdated: str
    createdOn: str
    isArchived: bool = False
    isDraft: bool = False
    fieldData: dict[str, Any]


class ListeItems(Permissif):
    """`/collections/{id}/items` (préparés, brouillons et archivés COMPRIS) ou
    `/collections/{id}/items/live` (publiés seulement)."""

    items: list[CollectionItem]
    pagination: Pagination


# ── Formulaires ──────────────────────────────────────────────────────────────


class FormField(Permissif):
    displayName: str
    type: str = Field(description="Plain, Email, Password, Phone ou Number.")
    placeholder: str | None = None
    userVisible: bool = True


class ResponseSettings(Permissif):
    redirectUrl: str | None = None
    redirectMethod: str | None = None
    redirectAction: str | None = None
    sendEmailConfirmation: bool = False


class Form(Permissif):
    """Un formulaire. `fields` est un OBJET clé par identifiant de champ, pas
    un tableau — et `formResponse` d'une soumission est clé par
    `displayName`, pas par identifiant. Le rapprochement se fait par le nom."""

    id: str
    displayName: str
    siteId: str
    siteDomainId: str = Field(
        json_schema_extra=unverified(
            "attesté par l'exemple de la référence, mais rien ne dit à quel domaine "
            "il correspond quand le site en a plusieurs"
        )
    )
    pageId: str
    pageName: str
    formElementId: str | None = None
    workspaceId: str
    createdOn: str
    lastUpdated: str
    fields: dict[str, FormField]
    responseSettings: ResponseSettings


class ListeForms(Permissif):
    forms: list[Form]
    pagination: Pagination


class FormSubmission(Permissif):
    """Une soumission.

    ┌─ `formResponse` EST LIBRE ET NOMINATIF ────────────────────────────────┐
    │ Ses clés sont les `displayName` des champs du formulaire (« Prénom »,  │
    │ « Email », « Message »), ses valeurs ce que le visiteur a tapé. C'est │
    │ de la donnée personnelle de PROSPECT, finalité distincte : un          │
    │ consommateur analytique ne doit en retenir que ce qui compte —        │
    │ quand, sur quel formulaire, depuis quelle locale — et rien de ce qui  │
    │ identifie.                                                              │
    └────────────────────────────────────────────────────────────────────────┘

    `localeId` est `null` pour une soumission depuis la locale PRIMAIRE (ou
    un site non localisé), et l'ID de locale sinon : `null` n'est pas
    « inconnu », c'est « la langue par défaut ».
    """

    id: str
    displayName: str = Field(description="Le nom du FORMULAIRE, pas du visiteur.")
    siteId: str
    workspaceId: str
    dateSubmitted: str
    formResponse: dict[str, Any]
    localeId: str | None = None
    formId: str


class ListeFormSubmissions(Permissif):
    """Servie de la plus récente à la plus ancienne — cf. UNVERIFIED-FIELDS."""

    formSubmissions: list[FormSubmission] = Field(
        json_schema_extra=unverified(
            "l'ordre de tri (dateSubmitted décroissant) n'est pas documenté ; il est "
            "reproduit tel qu'observé dans les exemples et l'interface"
        )
    )
    pagination: Pagination
