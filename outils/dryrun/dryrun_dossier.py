"""Dry-run complet d'un rapport, en LECTURE SEULE (aucun objet permanent créé, date_reportgenerate non modifiée).

Comme run_single.py, sauf :
- la VM est créée en table TEMPORAIRE (vm_test) dans une session unique, puis la session passe en lecture seule
  (toute écriture accidentelle échoue) ; toutes les requêtes du générateur passent par cette session ;
- ni update_date_reportgenerator, ni suppression de vue.

Usage : poetry run python outils/dryrun/dryrun_dossier.py <list_analyse|-> <id_area> <buffer> <area_name> <sortie>
        (list_analyse « - » = vide = rapport générique ; id_area : une zone de type LPO_REPORT_STUDY)
  DRYRUN_QGIS / DRYRUN_TEMPLATE : projet QGIS / template Word d'essai à la place de ceux du dossier.
  DRYRUN_PARAMS : paramètres du dossier.toml à remplacer, en JSON (ex. '{"annee": 2024, "emprise": "zone_etude:1"}').
  Le dossier de sortie (rapport, data/ avec données SENSIBLES) doit être hors du dépôt.
Cache : <temp>/reportgenerator_dryrun/vm_<id_area>_<list_analyse>_<buffer>.bin (ou DRYRUN_CACHE) : copie binaire de
        la VM rechargée en quelques secondes ; données sensibles ; à supprimer si le SQL de la VM change.
"""
import dataclasses
import json
import os
import re
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

import reportgenerator.analysis.common.vm_queries as vmq
import reportgenerator.queries as q
from reportgenerator.analysis.common.filesystem import create_analysis_dirs
from reportgenerator.analysis.common.models import AnalysisResult
from reportgenerator.core import registry
from reportgenerator.core.context import ReportContext
from reportgenerator.core.dossier import resolve_dossier
from reportgenerator.core.pipeline import run_pipeline

list_analyse = "" if sys.argv[1] == "-" else sys.argv[1]
id_area, buffer, area_name, out = int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], Path(sys.argv[5])
SERVICE = "gnlpoaura"
# copie locale de la VM (même zone, même dossier, même buffer) : évite de la recalculer à chaque essai.
# Données SENSIBLES : jamais dans le dépôt (dossier temporaire du système, ou DRYRUN_CACHE).
CACHE_DIR = Path(os.getenv("DRYRUN_CACHE") or Path(tempfile.gettempdir()) / "reportgenerator_dryrun")
CACHE = CACHE_DIR / f"vm_{id_area}_{list_analyse or 'generique'}_{buffer}.bin"
CACHE.parent.mkdir(parents=True, exist_ok=True)

captured = []


class FakeCur:
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def execute(self, sql, *a): captured.append(sql)
    def fetchall(self): return []
    def fetchone(self): return None


class FakeConn:
    def cursor(self, **k): return FakeCur()
    def commit(self): pass


@contextmanager
def fake(_):
    yield FakeConn()


conn = psycopg.connect(service=SERVICE, row_factory=dict_row, autocommit=True)


@contextmanager
def real(_):
    yield conn


registry._load_bricks()
socle = registry.get_brick("socle_data")


def socle_dryrun(ctx):
    """socle_data : SQL de la VM capturé (connexion factice), exécuté en table temporaire, puis lecture seule."""
    q.get_connection = fake
    socle.run(ctx)
    sql = next(s for s in reversed(captured) if "create materialized view" in s)
    select = re.search(r"create materialized view \S+ as(.*?);", sql, re.S).group(1)
    t0 = time.time()
    with conn.cursor() as cur:
        # structure seule (rapide), puis contenu : copie locale si elle existe, sinon calcul complet puis copie
        # locale pour les essais suivants
        cur.execute(f"create temporary table vm_test as {select} with no data")
        if CACHE.exists():
            with cur.copy("copy vm_test from stdin (format binary)") as cp, CACHE.open("rb") as f:
                while bloc := f.read(1 << 20):
                    cp.write(bloc)
        else:
            cur.execute(f"insert into vm_test {select}")
            with cur.copy("copy vm_test to stdout (format binary)") as cp, CACHE.open("wb") as f:
                for bloc in cp:
                    f.write(bloc)
        for idx in ("(id_synthese)", "(cd_ref)", "(date_max)", "using gist (the_geom_local)",
                    "using gist (geom_maille)"):
            cur.execute(f"create index on vm_test {idx}")
        cur.execute("analyze vm_test")
        cur.execute("set session characteristics as transaction read only")
        cur.execute("select count(*) as n from vm_test")
        print(f"[dry-run] VM temporaire : {cur.fetchone()['n']} lignes en {time.time() - t0:.0f} s ; "
              "session en lecture seule")
    ctx.queries.vm = "vm_test"
    q.get_connection = real
    vmq.get_connection = real
    return AnalysisResult()


registry._REGISTRY["socle_data"] = dataclasses.replace(socle, run=socle_dryrun)

dossier = resolve_dossier(list_analyse)
# essais : projet QGIS et/ou template Word de remplacement (DRYRUN_QGIS, DRYRUN_TEMPLATE), sans toucher au dépôt
if os.getenv("DRYRUN_QGIS"):
    dossier = dataclasses.replace(dossier, qgis_project=Path(os.environ["DRYRUN_QGIS"]))
if os.getenv("DRYRUN_TEMPLATE"):
    dossier = dataclasses.replace(dossier, template=Path(os.environ["DRYRUN_TEMPLATE"]))
if os.getenv("DRYRUN_PARAMS"):
    dossier = dataclasses.replace(dossier, params={**dossier.params, **json.loads(os.environ["DRYRUN_PARAMS"])})
    print(f"[dry-run] paramètres remplacés : {os.environ['DRYRUN_PARAMS']}")
print(f"[dry-run] projet QGIS : {dossier.qgis_project} ; template : {dossier.template}")
enabled, ignored = dossier.select_analyses(list_analyse)
print(f"[dry-run] dossier {dossier.name}, analyses : {enabled} (ignorées : {ignored})")
output_dirs = create_analysis_dirs(out)
sq = q.SyntheseQueries(service_name=SERVICE, id_area=id_area, buffer=buffer)
ctx = ReportContext(service_name=SERVICE, id_area=id_area, area_name=area_name, referee="dry-run", buffer=buffer,
                    dossier=dossier, enabled=enabled, output_dirs=output_dirs, queries=sq,
                    params=dict(dossier.params))
unresolved = run_pipeline(ctx, output_file=out / f"{area_name}.docx")
print("[dry-run] placeholders non remplis :", sorted(unresolved) if unresolved else "aucun")
conn.close()
