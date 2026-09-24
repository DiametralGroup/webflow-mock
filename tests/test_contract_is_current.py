"""Le contrat committé ne doit pas dériver de l'application, et l'honnêteté est
une contrainte de build.

  1. `contracts/webflow.openapi.yaml` EST ce que l'application sert. C'est ce
     fichier que le consommateur copie chez lui, épinglé à une version de
     l'image ; s'il ment, il ment pour tout le monde en aval.
  2. Tout champ marqué `unverified` est inscrit au registre. Sans ce test, le
     marqueur deviendrait décoratif.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

import webflow_mock as mock

RACINE = Path(__file__).resolve().parents[1]
CONTRAT = RACINE / "contracts" / "webflow.openapi.yaml"
REGISTRE = RACINE / "docs" / "UNVERIFIED-FIELDS.md"


def test_le_contrat_committe_est_a_jour():
    genere = yaml.safe_load(
        yaml.safe_dump(mock.contrat_openapi(), sort_keys=False, allow_unicode=True)
    )
    committe = yaml.safe_load(CONTRAT.read_text(encoding="utf-8"))
    assert committe == genere, (
        "Le contrat committé a dérivé de l'application. Lancer `make contract`, "
        "RELIRE le diff, puis committer."
    )


def test_le_contrat_ne_publie_pas_les_affordances_du_mock():
    contrat = yaml.safe_load(CONTRAT.read_text(encoding="utf-8"))
    assert all(chemin.startswith("/v2/") for chemin in contrat["paths"])
    brut = CONTRAT.read_text(encoding="utf-8")
    assert "__admin" not in brut
    assert "/health" not in brut


def test_le_contrat_annonce_le_serveur_du_fournisseur():
    contrat = yaml.safe_load(CONTRAT.read_text(encoding="utf-8"))
    assert contrat["servers"] == [{"url": "https://api.webflow.com"}]


def test_le_contrat_couvre_les_dix_huit_operations():
    contrat = yaml.safe_load(CONTRAT.read_text(encoding="utf-8"))
    operations = [op for chemin in contrat["paths"].values() for op in chemin]
    assert len(operations) == 18
    assert set(operations) == {"get"}, "la surface est en LECTURE seule"


def test_le_contrat_documente_la_pagination():
    contrat = yaml.safe_load(CONTRAT.read_text(encoding="utf-8"))
    liste = contrat["paths"]["/v2/sites/{site_id}/pages"]["get"]
    noms = [p["name"] for p in liste["parameters"]]
    assert noms == ["site_id", "localeId", "offset", "limit"]
    reponse = liste["responses"]["200"]["content"]["application/json"]["schema"]
    schema = contrat["components"]["schemas"][reponse["$ref"].rsplit("/", 1)[-1]]
    assert set(schema["properties"]) == {"pages", "pagination"}
    # Et `/sites` n'en déclare AUCUNE.
    sites = contrat["paths"]["/v2/sites"]["get"]["responses"]["200"]["content"]["application/json"]
    schema_sites = contrat["components"]["schemas"][sites["schema"]["$ref"].rsplit("/", 1)[-1]]
    assert set(schema_sites["properties"]) == {"sites"}


def test_le_contrat_documente_les_modes_de_panne():
    contrat = yaml.safe_load(CONTRAT.read_text(encoding="utf-8"))
    reponses = contrat["paths"]["/v2/sites/{site_id}/forms"]["get"]["responses"]
    assert {"400", "401", "403", "404", "409", "429", "500", "503"} <= set(reponses)


def test_tout_champ_non_verifie_est_inscrit_au_registre():
    assert REGISTRE.exists(), f"{REGISTRE} est obligatoire"
    registre = REGISTRE.read_text(encoding="utf-8")

    brut = json.dumps(mock.contrat_openapi(), ensure_ascii=False)
    marques = re.findall(r'"x-webflow-confidence":\s*"(unverified|invented)"', brut)
    assert marques, (
        "aucun champ marqué : soit tout est attesté (à prouver), soit le marquage est perdu"
    )

    schemas = mock.contrat_openapi().get("components", {}).get("schemas", {})
    for nom, schema in schemas.items():
        for champ, definition in (schema.get("properties") or {}).items():
            if "x-webflow-confidence" not in json.dumps(definition, ensure_ascii=False):
                continue
            assert f"`{champ}`" in registre, (
                f"le champ `{champ}` de {nom} est marqué non vérifié mais "
                f"n'est pas inscrit dans docs/UNVERIFIED-FIELDS.md"
            )


def test_le_registre_porte_son_front_matter():
    texte = REGISTRE.read_text(encoding="utf-8")
    assert texte.startswith("---\n")
    entete = yaml.safe_load(texte.split("---", 2)[1])
    assert entete["type"] == "reference"
    assert entete["sources_of_truth"] and entete["review_triggers"]
    assert entete["update_policy"] and entete["last_verified"]
