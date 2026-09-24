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
review_triggers:
  - "Une campagne de sondes contre un VRAI site Webflow (scripts/compare_real.py avec un site token)"
  - "Une mise à jour de la référence qui documente un comportement laissé ouvert ici"
  - "Tout écart constaté par un consommateur entre le mock et la production"
update_policy: >-
  Tout champ ou comportement marqué `x-webflow-confidence: unverified` ou
  `invented` dans le contrat DOIT figurer dans ce fichier —
  `tests/test_contract_is_current.py` échoue sinon. Retirer une ligne d'ici
  demande de retirer le marqueur du modèle, et donc d'avoir levé le doute.
last_verified: 2026-09-24
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

## Champs de schéma

| Champ | Ressource | Ce qui est incertain | Pour lever le doute |
|---|---|---|---|
| `publishedPath` | `pages` | La forme du chemin d'une page **gabarit** de collection (`/blog/detail_article`) est plausible ; la référence ne montre que des pages statiques. Les chemins des pages statiques et le préfixe de locale (`/en/…`) sont attestés par l'exemple de `pages/get-metadata`. | `GET /sites/{id}/pages` sur un site réel qui a une collection : lire le `publishedPath` de sa page gabarit. |
| `siteDomainId` | `forms` | Attesté par l'exemple de `forms/get`, mais rien ne dit à quel domaine il correspond quand le site en a plusieurs. Le mock sert l'identifiant du premier domaine personnalisé. | Comparer `siteDomainId` et `customDomains[].id` sur un site réel à deux domaines. |
| `formSubmissions` (ordre) | `form_submissions` | L'ordre de tri n'est **pas documenté**. Le mock sert de la plus récente à la plus ancienne, comme l'interface. Un consommateur ne doit pas s'y adosser pour s'arrêter avant `total`. | `GET /sites/{id}/form_submissions?limit=3` sur un site réel : lire les `dateSubmitted`. |

## Comportements

| Comportement | Ce qui est incertain | Pour lever le doute |
|---|---|---|
| **`limit` > 100** | La référence déclare « max limit: 100 » sur chaque liste, sans dire ce qu'elle fait au-delà. Le mock rend **400 `validation_error`** — le côté sûr : un consommateur qui borne lui-même passe dans les deux cas ; un consommateur qui compte sur un rabotage silencieux est pris ici plutôt qu'en production. | `GET /sites/{id}/pages?limit=101` sur un site réel. |
| **Message du 401** | Le guide donne le code `not_authorized` ; la référence décrit le statut par « Provided access token is invalid or does not have access to requested resource ». Le mock sert `"Unauthorized"`. Le **code** est attesté, le message ne l'est pas. | Appeler `/sites` avec un jeton faux et lire `message`. |
| **Message du 403 `missing_scopes`** | Le code est attesté (énumération de la référence). Le message « You are missing the following scopes: 'x' » est celui qu'on observe couramment, non documenté. | Générer un site token sans `forms:read` et appeler `/sites/{id}/forms`. |
| **Message du 409 `forms_require_republish`** | Le code et la description du statut (« To access this feature, the site needs to be republished. ») sont attestés ; que le message du corps soit exactement cette phrase ne l'est pas. | Appeler `/sites/{id}/forms` sur un site non republié depuis 2023. |
| **Filtres et tri des éléments** | `sortBy`, `sortOrder`, `name`, `slug`, `cmsLocaleId` sont attestés ; les filtres de dates (`createdOn[gte]`…) et `filter[…]`/`sort[…]` en notation crochets ne sont **pas servis** — un connecteur analytique charge tout et trie chez lui. Un paramètre inconnu est ignoré, pas refusé. | Sans objet pour le dialecte : les servir le jour où un consommateur en a besoin. |
| **Ordre par défaut des éléments** | Sans `sortBy`, le mock rend l'ordre de création. Le fournisseur rend l'ordre du CMS, qui n'est pas documenté. | `GET /collections/{id}/items?limit=5` sur une collection réelle réordonnée à la main. |
| **`slug` de la page d'accueil** | Le mock sert `accueil` avec `publishedPath: "/"`. Le fournisseur pourrait servir un slug vide ou `home`. | Lire la première page de `/sites/{id}/pages` sur un site réel. |
| **`X-RateLimit-Remaining` sur un 429** | Les en-têtes sur les réponses saines sont attestés ; que le 429 porte `X-RateLimit-Remaining: 0` est une déduction. | Dépasser la limite sur un site réel et lire les en-têtes du 429. |
| **Fenêtre de débit** | « 60 requêtes par minute » est attesté ; que la minute soit **glissante** plutôt que calendaire ne l'est pas. Le mock compte sur une fenêtre glissante et n'applique la limite que par injection (`rate_limit`) — jamais spontanément, pour que la suite d'un consommateur reste rapide. | Sans objet en test ; à observer en production via les en-têtes. |
