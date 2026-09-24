# webflow-mock

[![CI](https://github.com/LittleBigCode/webflow-mock/actions/workflows/ci.yml/badge.svg)](https://github.com/LittleBigCode/webflow-mock/actions/workflows/ci.yml)

Mock of the **Webflow Data API v2** (read surface), shipped both as a
**container image** and as an **installable Python package**. It serves the
**18 GET operations** an analytics connector reads — token, site, pages, CMS
collections and items, forms and form submissions — over one coherent
website: the showcase site of *Boréal Conseil*, the same fictional French IT
consultancy that already populates `boondmanager-mock`, `entra-mock`,
`linkedin-mock`, `ga-mock` and `pennylane-mock`.

The shapes are not written from memory. Every page of Webflow's reference is
available as Markdown and declares its response fields, types, nullability and
enumerations; those pages were downloaded and this mock reproduces them. The
method is replayable — see [`docs/EXTRACTION.md`](docs/EXTRACTION.md).

## Start in one command

```bash
# Pre-built image from GitHub Container Registry (published by CI):
docker run -p 8015:8000 -e WEBFLOW_MOCK_ADMIN_ENABLED=true \
    ghcr.io/littlebigcode/webflow-mock:latest

# Or build locally (admin plane open, evolution active):
docker compose up --build           # or: make up
curl http://localhost:8015/health

# Or locally without Docker:
make bootstrap && make run
```

The image is non-root (uid/gid 65532) with a built-in healthcheck, so
`depends_on: condition: service_healthy` works on the consumer side. Port
**8015** is this mock's slot in the insights360 ecosystem (8010 boondmanager,
8011 entra, 8012 linkedin, 8013 ga, 8014 pennylane are taken — the map is
shared).

## Credentials

Everything is overridable through environment variables (see
[Configuration](#configuration)); out of the box:

| Role | Variable | Default value |
|---|---|---|
| Site token | `WEBFLOW_MOCK_TOKEN` | `mock-webflow-token` |
| Granted scopes | `WEBFLOW_MOCK_SCOPES` | `authorized_user:read,sites:read,pages:read,cms:read,forms:read` |
| `/__admin` control plane | `WEBFLOW_MOCK_ADMIN_TOKEN` | `mock-admin-token` (header `X-Mock-Admin-Token`; only mounted when `WEBFLOW_MOCK_ADMIN_ENABLED=true`) |

```bash
curl -H "Authorization: Bearer mock-webflow-token" http://localhost:8015/v2/sites

# What may I read, and on which site? The natural smoke test for a connector —
# it is the ONLY endpoint that requires no scope.
curl -H "Authorization: Bearer mock-webflow-token" http://localhost:8015/v2/token/introspect
```

Heads-up, exactly as on the real API: **401** (`not_authorized`) means the
token is missing, invalid or revoked — the three are indistinguishable.
**403** (`missing_scopes`) means the token is fine but lacks a scope, and the
message *names the missing scopes*. Neither is retryable.

## Two modes, both maintained

```python
# In-process — for test suites.
from fastapi.testclient import TestClient
import webflow_mock as mock

client = TestClient(mock.app)
mock.state.reset(seed=42)
```

```bash
# In a container — for docker compose and CI services.
python -m webflow_mock
```

The property worth keeping: **the application your stack queries IS the one the
tests exercise.** The container mode is also what makes the `/__admin` control
plane necessary — outside the process, a test can no longer mutate state in
Python.

## Served surface

| Domain | Operations |
|---|---|
| Token | `GET /v2/token/authorized_by`, `GET /v2/token/introspect` |
| Sites | `GET /v2/sites`, `GET /v2/sites/{site_id}`, `GET /v2/sites/{site_id}/custom_domains` |
| Pages | `GET /v2/sites/{site_id}/pages` (per locale), `GET /v2/pages/{page_id}` |
| CMS | `GET /v2/sites/{site_id}/collections`, `GET /v2/collections/{id}`, `GET /v2/collections/{id}/items`, `…/items/{item_id}`, `…/items/live`, `…/items/live/{item_id}` |
| Forms | `GET /v2/sites/{site_id}/forms`, `GET /v2/forms/{form_id}`, `GET /v2/forms/{form_id}/submissions`, `GET /v2/sites/{site_id}/form_submissions`, `GET /v2/form_submissions/{id}` |

**Writes are out of scope.** This mock's consumer reads; it does not write. A
POST/PATCH/DELETE answers 404 *in the Webflow dialect* — never FastAPI's 405.
E-commerce, memberships, comments, assets, webhooks and branches are not
served: Boréal Conseil has none, and an analytics connector reads none.

## The reproduced dialect

Six things that will break a consumer if they are not exact — and each one is
different from the five sibling mocks:

| | Webflow | ...vs the neighbours |
|---|---|---|
| Auth | static `Authorization: Bearer` site token + **granular scopes** (`forms:read`…) | static JWT (Boond), client_credentials (Entra), RS256 SA (GA), bearer + version header (LinkedIn), bearer + scopes (Pennylane) |
| Pagination | **`offset`/`limit`** with a `pagination: {limit, offset, total}` object — and **three lists not paginated at all** | `page`/`maxResults`, `@odata.nextLink`, `start`/`count`, `limit`/`offset` without total, opaque cursor |
| List key | **changes per resource**: `sites`, `pages`, `collections`, `items`, `forms`, `formSubmissions` | `items` (Pennylane), `data` (Boond), `value` (Graph)… |
| Identifiers | **24-hex strings** (`"62b720ef280c7a7a3be8cabe"`) | integers everywhere else |
| Errors | `{message, code, externalReference, details}` on every status, **429 included** | `{error, status}` + plain-text 429 (Pennylane) |
| Rate limit | 60 req / min; `X-RateLimit-Limit` and `X-RateLimit-Remaining` on *every* response; 429 with `Retry-After: 60` | 25 / 5 s (Pennylane), quotas (GA) |

Five traps reproduced on purpose, because they are silent in production:

1. **`/sites`, `/sites/{id}/collections` and `/sites/{id}/custom_domains` have
   no `pagination` object.** A consumer that reads `body["pagination"]["total"]`
   without a guard raises a `KeyError` on the very first route it calls.
2. **Offset pagination drifts on a list that lives.** Submissions are served
   newest first; one that arrives between two pages shifts everything by one
   and the last row of page N comes back at the top of page N+1. No error, no
   warning — a duplicate. The `page_drift` injection reproduces it on demand.
3. **`/items` is not `/items/live`.** The staged list includes drafts and
   archived items; the live one is what visitors see. A consumer that counts
   "published articles" from `/items` overcounts.
4. **`formResponse` is keyed by field *display name*, `fields` by field *id*.**
   The two only meet by name. And `formResponse` is nominative — first name,
   e-mail, phone, free text — so the consumer, not the mock, decides what to
   keep.
5. **`localeId: null` on a submission means the primary locale**, not
   "unknown". A page is one entity localised twice: same `id`, different
   `title` and `publishedPath` (`/contact` vs `/en/contact`).

And one failure that neither token nor scope can fix: **409
`forms_require_republish`** on the form routes, when the site has not been
republished since the feature shipped. The mock exposes it as an injection and
as an environment flag.

## The dataset: Boréal Conseil's website

One coherent world, deterministic at seed **42**, anchored at **2026-07-15** —
never `datetime.now()`. Two runs produce the same bytes, which is what makes a
consumer's idempotence gate possible.

| | |
|---|---|
| site | `www.boreal-conseil.example`, primary locale `fr-FR`, secondary `en-US`, data collection `optOut` |
| pages | 22 — static pages, two folders, four collection templates, one draft, one archived |
| collections | Articles (36, two drafts, two archived), Études de cas (12), Offres d'emploi (14, one draft, two filled), Auteurs (6), Événements (8) |
| forms | Contact, Newsletter, Candidature spontanée, two white-paper downloads, event registration |
| submissions | ≈570 between January and July 2026, weekly volumes per form, bursts before each event, ≈12 % from the English locale |

**Shared with the sibling mocks** (duplicated, no package dependency): the
client company names (case studies cite them, prospects write from their
domains), the three agencies and three practices (job offers carry them as
options), the anchor date and the seed. The job offers carry a
`reference-boond` field — the bridge to `boondmanager-mock`.

**Not shared: the traffic.** GA4 measures visits; Webflow only serves what the
site *contains* and what its forms *receive*. A downstream test that joins the
two joins on page paths and days, not on counters.

### E-mail domains are the analytical signal

Around 45 % of submissions come from generic domains (`gmail.com`,
`orange.fr`…), 22 % from companies of the shared world, the rest from prospect
companies. A consumer that keeps only the *domain* of the e-mail — and drops
the name, the phone and the message — keeps everything a marketing dashboard
needs and nothing that identifies a person.

## Incremental extraction

**Time evolution** — the site lives. One scripted event per interval (60 s by
default), in a six-step cycle: a new submission (at the *top* of the list), a
page touched, an article drafted, the oldest draft published (the site's
`lastPublished` moves with it), a spontaneous application, an item updated.
Event *k* draws its randomness from `Random(f"{seed}:{k}")` and is stamped
`EPOQUE + (k+1) x interval`, so two mocks advanced by the same number of steps
hold the same world.

Set `WEBFLOW_MOCK_EVOLUTION_ENABLED=false` to freeze the dataset — which is
what a consumer's idempotence gate needs.

There is no changelog and no `updatedSince` filter on this API: a consumer
reloads lists and merges on `id`. What it can do incrementally is stop paging
submissions once it is past its last known `dateSubmitted` — provided it
trusts the descending order, which is *not* documented (see
[`docs/UNVERIFIED-FIELDS.md`](docs/UNVERIFIED-FIELDS.md)).

## Failure modes

*The point of the mock is to reproduce failure modes, not just happy paths.*
Rules are declarative and driven over HTTP, because the mock runs in a container
at the consumer's side.

```bash
A='X-Mock-Admin-Token: mock-admin-token'
BASE=http://localhost:8015

# 429 with Retry-After: 60 — a client that ignores the header replays within
# the same minute and gets limited again.
curl -H "$A" -X POST $BASE/__admin/inject \
  -d '{"kind":"rate_limit","scope":"/v2/*","after_requests":5}'

# A transient failure that stops on its own — otherwise you are not testing a
# retry, you are testing a failure.
curl -H "$A" -X POST $BASE/__admin/inject \
  -d '{"kind":"status","scope":"/v2/sites/*/pages","status":503,"times":1}'

# The most common real-world integration failure: a site token generated with
# one checkbox missing.
curl -H "$A" -X POST $BASE/__admin/inject \
  -d '{"kind":"scope_reject","scope":"/v2/sites/*/forms","scope_manquant":"forms:read"}'

# Offset drift: from page 2 on, one element is inserted at the head.
curl -H "$A" -X POST $BASE/__admin/inject \
  -d '{"kind":"page_drift","scope":"/v2/sites/*/form_submissions","after_page":1}'
```

Kinds: `rate_limit`, `status`, `latency`, `page_drift`, `auth_reject`,
`scope_reject`, `republish_required`. Each takes a glob `scope` and an optional
`times` — that is the difference between a transient failure a retry must
absorb and a persistent one that must fail the run with a non-zero exit code.

## Control plane

Closed by default; when disabled the surface **does not exist** (it is not
"mounted then forbidden").

| Route | Purpose |
|---|---|
| `POST /__admin/reset` | rebuild the dataset (`{"seed": 7}`), re-applying the environment's injection baseline |
| `GET /__admin/state` | seed, totals, `request_counts_by_path`, **`last_query_params_by_path`**, injections, clock offset, evolution log, scopes |
| `POST /__admin/inject` · `DELETE /__admin/inject/{id}` · `POST /__admin/inject/clear` | failure rules |
| `POST /__admin/clock` | `{"advance_seconds": 3600}` — time **without `sleep`** |
| `POST /__admin/evolve` | `{"pas": 5}` — force N evolution events, clock untouched |
| `POST /__admin/mutate` | edit an entity (`{"collection": "pages", "id": "…", "champs": {…}}`) and push its `lastUpdated` above every other |
| `POST /__admin/scopes` | redefine the token's scopes — the 403 lever |
| `POST /__admin/republish` | `{"required": true}` — the 409 lever on form routes |

`last_query_params_by_path` is the keystone for downstream tests: it is what
lets a consumer **prove** it actually sent its `offset`. Without that proof, a
pipeline that forgot to page would pass every test — it would simply reload
page one each time, and no assertion about content would notice.

## Configuration

| Variable | Default | What it does |
|---|---|---|
| `WEBFLOW_MOCK_TOKEN` | `mock-webflow-token` | the accepted bearer token |
| `WEBFLOW_MOCK_SCOPES` | the five read scopes | comma-separated; remove one to get a 403 |
| `WEBFLOW_MOCK_SEED` | `42` | dataset seed — the same seed, the same world |
| `WEBFLOW_MOCK_ADMIN_ENABLED` | `false` | mounts `/__admin` |
| `WEBFLOW_MOCK_ADMIN_TOKEN` | `mock-admin-token` | `X-Mock-Admin-Token` |
| `WEBFLOW_MOCK_EVOLUTION_ENABLED` | `true` | let the site live |
| `WEBFLOW_MOCK_EVOLUTION_INTERVAL` | `60` | seconds between events |
| `WEBFLOW_MOCK_DEFAULT_LIMIT` / `_MAX_LIMIT` | `100` / `100` | page size; out of bounds → 400 |
| `WEBFLOW_MOCK_RATE_LIMIT` / `_RATE_WINDOW` | `60` / `60` | advertised in `X-RateLimit-*` |
| `WEBFLOW_MOCK_RATE_LIMIT_AFTER` / `_RETRY_AFTER` | unset | a baseline `rate_limit` rule re-applied on every reset |
| `WEBFLOW_MOCK_FORMS_REQUIRE_REPUBLISH` | `false` | form routes answer 409 |
| `WEBFLOW_MOCK_SITE` / `_SITE_SHORT_NAME` / `_SITE_DOMAIN` | `Boréal Conseil` / `boreal-conseil` / `www.boreal-conseil.example` | what the site reports |
| `WEBFLOW_MOCK_HOST` / `_PORT` | `0.0.0.0` / `8000` | uvicorn bind |

There is deliberately **no `.env.example`** here: it lives with the consumer
(insights360), which is where the sources have to be wired together.

## Development

```bash
make bootstrap   # uv sync
make test        # pytest
make lint        # ruff check + ruff format --check + strict mypy
make format
make contract    # regenerate contracts/webflow.openapi.yaml — REVIEW the diff
```

The pydantic models are the **source** of the published contract. `make
contract` regenerates `contracts/webflow.openapi.yaml`, and a test fails if it
drifts — that file is what insights360 copies and pins, so if it lies, it lies
for everyone downstream. `/__admin` and `/health` are stripped from it.

Anything not attested by the vendor's reference is marked
`x-webflow-confidence` in the contract **and** listed in
[`docs/UNVERIFIED-FIELDS.md`](docs/UNVERIFIED-FIELDS.md), with what it would
take to settle each doubt. A test enforces it: honesty is a build constraint.

### Probing a real site

```bash
WEBFLOW_TOKEN=xxx uv run python scripts/compare_real.py
```

GET-only, writes nothing, and copies **no data** into its report — only field
names and types, and for submissions only the *keys* of `formResponse`. Any
difference is a difference of the *mock*: the vendor is right.
