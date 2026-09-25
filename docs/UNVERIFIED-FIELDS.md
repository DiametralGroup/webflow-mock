---
type: reference
sources_of_truth:
  - "https://developers.webflow.com/llms.txt (index officiel, relevé le 2026-09-24)"
  - "La référence de chaque opération en Markdown (`https://developers.webflow.com/data/reference/<…>.md`) :
     sites/list, sites/get, sites/get-custom-domain, pages-and-components/pages/list,
     pages-and-components/pages/get-metadata, cms/collections/list, cms/collections/get,
     cms/collection-items/staged-items/list-items, cms/collection-items/live-items/list-items-live,
     forms/forms/list, forms/forms/get, forms/form-submissions/list-submissions,
     forms/form-submissions/list-submissions-by-site, forms/form-submissions/get-submission,
     token/authorized-by, token/introspect"
  - "Les guides : Error handling, Rate limits, Scopes"
  - "Une campagne de sondes contre un site RÉEL avec un site token, le 2026-09-25
     (scripts/compare_real.py + sondes manuelles sur limit/offset/introspect/401)"
review_triggers:
  - "Une nouvelle campagne de sondes contre un VRAI site Webflow (scripts/compare_real.py)"
  - "Une mise à jour de la référence qui documente un comportement laissé ouvert ici"
  - "Tout écart constaté par un consommateur entre le mock et la production"
update_policy: >-
  Tout champ ou comportement marqué `x-webflow-confidence: unverified` ou
  `invented` dans le contrat DOIT figurer dans ce fichier —
  `tests/test_contract_is_current.py` échoue sinon. Retirer une ligne d'ici
  demande de retirer le marqueur du modèle, et donc d'avoir levé le doute.
last_verified: 2026-09-25
---

# Ce qui n'est pas attesté

Ce mock est construit sur une source **publique et structurée** : la référence
de la Data API v2, dont chaque page est disponible en Markdown et déclare, champ
par champ, les types et les énumérations de ses réponses. Presque tout ce qu'il
sert en vient. Ce fichier liste ce qui n'en vient pas — et ce qu'il faudrait
faire pour lever chaque doute.

| Marqueur | Sens |
|---|---|
| *attesté* | vient de la référence ou d'un guide du fournisseur. Aucun marqueur. |
| `unverified` | le nom, la forme ou les valeurs sont **plausibles**, pas prouvés. |
| `invented` | n'existe **pas** chez Webflow — c'est une affordance du mock. |

## Ce que la sonde du 2026-09-25 a tranché

| Point | Avant | Observé | Le mock |
|---|---|---|---|
| `limit` > 100 | 400 supposé | **200, raboté à 100** (`pagination.limit: 100`) | rabote |
| `limit` nul, négatif, illisible | 400 supposé | 400 `validation_error`, message `Validation Error: ["Value (limit) should match pattern \"^[1-9]\\d*$\""]` | idem, au mot près |
| `offset` négatif ou illisible | — | 400, même forme (`^\d+$`) | idem |
| `offset` au-delà du total | page vide supposée | **page vide, 200** | idem |
| message du 401 | `Unauthorized` supposé | **`Request not authorized`**, code `not_authorized` | idem |
| `/token/introspect` avec un site token | 200 supposé | **500 `internal_error`, « An Internal Error Occurred »** | 500 par défaut (`WEBFLOW_MOCK_TOKEN_KIND=site`) ; `oauth` restaure le 200 |
| `/token/authorized_by` avec un site token | — | 200 | 200 |
| ordre des soumissions | non documenté | **`dateSubmitted` décroissant** sur les trois premières | décroissant (marqueur retiré) |
| `localeId` d'une page sur un site non localisé | — | `null`, alors que `locales.primary` existe | non reproduit : le mock est localisé |

## Champs de schéma

| Champ | Ressource | Ce qui est incertain | Pour lever le doute |
|---|---|---|---|
| `publishedPath` | `pages` | La forme du chemin d'une page **gabarit** de collection (`/blog/detail_article`) est plausible ; le site sondé n'a pas de collection avec gabarit visible dans la première page. | `GET /sites/{id}/pages` sur un site réel qui a une collection : lire le `publishedPath` de sa page gabarit. |
| `siteDomainId` | `forms` | Attesté par l'exemple de la référence, mais rien ne dit à quel domaine il correspond quand le site en a plusieurs. | Comparer `siteDomainId` et `customDomains[].id` sur un site réel à deux domaines. |
| `fullSiteCompiledAt` | `sites`, `customDomains` | **Observé** le 2026-09-25, absent de la référence. Sa sémantique (dernière compilation du site entier) est déduite du nom. | La référence, le jour où elle le documente. |
| `shouldPublish` | `pages` | **Observé** le 2026-09-25, absent de la référence. Le mock le sert à `true` sur une page ni brouillon ni archivée — une déduction. | Lire sa valeur sur un brouillon réel. |
| `componentId`, `componentElementId` | `forms`, `form_submissions` | **Observés** le 2026-09-25 : un formulaire posé dans un composant réutilisable les porte. Le mock les sert à `null` (formulaires posés dans la page). | Un site réel dont un formulaire vit dans un composant. |
| `pageId`, `publishedPath`, `schema` | `form_submissions` | **Observés** le 2026-09-25, absents de la référence : la page de la soumission et un `schema` vide. Ce que `schema` porte quand il n'est pas vide n'est pas connu. | Une soumission réelle avec `schema` non vide. |

## Comportements

| Comportement | Ce qui est incertain | Pour lever le doute |
|---|---|---|
| **Message du 403 `missing_scopes`** | Le code est attesté (énumération de la référence). Le message « You are missing the following scopes: 'x' » est celui qu'on observe couramment, non documenté — le jeton sondé portait tous ses scopes. | Générer un site token sans `forms:read` et appeler `/sites/{id}/forms`. |
| **Message du 409 `forms_require_republish`** | Le code et la description du statut (« To access this feature, the site needs to be republished. ») sont attestés ; que le message du corps soit exactement cette phrase ne l'est pas. | Appeler `/sites/{id}/forms` sur un site non republié depuis 2023. |
| **Filtres et tri des éléments** | `sortBy`, `sortOrder`, `name`, `slug`, `cmsLocaleId` sont attestés ; les filtres de dates (`createdOn[gte]`…) et `filter[…]`/`sort[…]` en notation crochets ne sont **pas servis**. Un paramètre inconnu est ignoré, pas refusé. | Sans objet pour le dialecte : les servir le jour où un consommateur en a besoin. |
| **Ordre par défaut des éléments** | Sans `sortBy`, le mock rend l'ordre de création. Le fournisseur rend l'ordre du CMS, qui n'est pas documenté. | `GET /collections/{id}/items?limit=5` sur une collection réelle réordonnée à la main. |
| **`slug` de la page d'accueil** | Le mock sert `accueil` avec `publishedPath: "/"`. Le fournisseur pourrait servir un slug vide ou `home`. | Lire la première page de `/sites/{id}/pages` sur un site réel. |
| **`X-RateLimit-Remaining` sur un 429** | Les en-têtes sur les réponses saines sont attestés (et observés : `X-Ratelimit-Limit: 60`, `X-Ratelimit-Remaining: 59`, `Retry-After: 60` **sur une réponse saine aussi**). Que le 429 porte `X-RateLimit-Remaining: 0` est une déduction. | Dépasser la limite sur un site réel et lire les en-têtes du 429. |
| **`Retry-After` sur les réponses saines** | **Observé** le 2026-09-25 : l'en-tête est présent sur un 200, à 60. Le mock ne le sert que sur le 429 — un consommateur qui dormirait dès qu'il le voit attendrait une minute par requête. | Sans objet : le mock est plus strict que le réel, dans le sens sûr. |
| **Fenêtre de débit** | « 60 requêtes par minute » est attesté ; que la minute soit **glissante** plutôt que calendaire ne l'est pas. Le mock n'applique la limite que par injection (`rate_limit`) — jamais spontanément. | À observer en production via les en-têtes. |
