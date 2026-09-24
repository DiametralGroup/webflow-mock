# D'où vient chaque forme

Ce mock n'a pas été écrit de mémoire. Il est adossé à une source **publique et
structurée**, relevée le **2026-09-24**, et ce fichier dit laquelle, comment la
rejouer, et ce qu'elle contient.

## La source : la référence en Markdown

Webflow publie un index pour agents à
[`https://developers.webflow.com/llms.txt`](https://developers.webflow.com/llms.txt),
et **toute page de documentation est disponible en Markdown** en lui ajoutant
`.md`. Chaque page de référence déclare, sous `## Response` et `## Types`, les
champs de sa réponse avec leur type, leur caractère optionnel ou nullable et
leurs énumérations — et sous `## Errors`, les statuts servis avec l'énumération
complète des trente-six codes d'erreur.

```bash
mkdir -p ref && cd ref
for p in sites/list sites/get sites/get-custom-domain \
         pages-and-components/pages/list pages-and-components/pages/get-metadata \
         cms/collections/list cms/collections/get \
         cms/collection-items/staged-items/list-items \
         cms/collection-items/live-items/list-items-live \
         forms/forms/list forms/forms/get \
         forms/form-submissions/list-submissions \
         forms/form-submissions/list-submissions-by-site \
         forms/form-submissions/get-submission \
         token/authorized-by token/introspect \
         error-handling rate-limits scopes; do
  curl -sS "https://developers.webflow.com/data/reference/$p.md" -o "$(echo $p | tr / _).md"
done
```

## Ce qui est servi, et ce qui ne l'est pas

La Data API v2 compte plus d'une centaine d'opérations. Le mock en sert
**dix-huit**, toutes en GET : celles qu'un connecteur **analytique** lit.

| Servi | Non servi, et pourquoi |
|---|---|
| Jeton : `authorized_by`, `introspect` | — |
| Sites : liste, détail, domaines personnalisés | activité (Enterprise), redirections, custom code, robots, sitemap |
| Pages : liste (par locale), métadonnées | contenu DOM (`/pages/{id}/dom`), composants |
| CMS : collections, détail avec champs, éléments préparés et publiés | création, mise à jour, publication, suppression |
| Formulaires : liste, détail, soumissions par formulaire et par site, détail | modification d'une soumission, suppression |
| — | e-commerce, membres (`users`), commentaires, assets, webhooks, branches, workspaces |

Les écritures (POST/PATCH/PUT/DELETE) rendent **404 au dialecte Webflow**
(`resource_not_found`). Le fournisseur, lui, les servirait ou rendrait un
`405` : c'est un écart assumé, le consommateur de ce mock ne doit jamais
écrire.

## Ce que la référence ne dit pas

Voir [`UNVERIFIED-FIELDS.md`](UNVERIFIED-FIELDS.md) — chaque ligne dit ce qui
est incertain et quelle sonde le tranche. Le script
[`scripts/compare_real.py`](../scripts/compare_real.py) exécute ces sondes
contre un site réel, en lecture seule, sans copier une donnée.
