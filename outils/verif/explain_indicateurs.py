"""EXPLAIN de toutes les requêtes du dossier Indicateurs, en transaction read_only (rien n'est exécuté ni écrit).

Usage : poetry run python outils/verif/explain_indicateurs.py <id_area> [ANALYZE]
  ANALYZE : exécute aussi les requêtes (toujours en lecture seule) pour mesurer leur durée.
"""
import sys
import time

import psycopg
from psycopg.rows import dict_row

from reportgenerator.analysis.indicateurs.queries import IndicateursQueries

SERVICE = "gnlpoaura"
id_area = int(sys.argv[1])
analyze = len(sys.argv) > 2 and sys.argv[2].upper() == "ANALYZE"
conn = psycopg.connect(service=SERVICE, row_factory=dict_row)
conn.read_only = True


def explain(self, sql, **params):
    sql = sql.replace("{ZONE}", "zone AS (SELECT ST_Multi(ST_Union(geom)) AS geom FROM ref_geo.l_areas "
                                "WHERE id_area = %(id_area)s)")
    t0 = time.time()
    with conn.cursor() as cur:
        cur.execute(("EXPLAIN (ANALYZE, BUFFERS OFF) " if analyze else "EXPLAIN ") + sql,
                    {"id_area": self.id_area, **params})
        plan = [r["QUERY PLAN"] for r in cur.fetchall()]
    conn.rollback()
    print(f"  {plan[0][:110]}" + (f"\n  {plan[-1]} ({time.time() - t0:.1f} s)" if analyze else ""))
    return []


IndicateursQueries._fetch = explain
q = IndicateursQueries(SERVICE, id_area)
appels = {
    "zone": lambda: q.zone() if False else q._fetch("WITH {ZONE} SELECT * FROM zone"),
    "departements": q.departements,
    "zones_biogeo": q.zones_biogeo,
    "localiser": lambda: q.localiser([("a", 850000.0, 6500000.0)]),
    "aires_vigienature STOC": lambda: q.aires_vigienature(["STOC_EPS"]),
    "releves_vigienature STOC": lambda: q.releves_vigienature(["STOC_EPS"], 2001),
    "observations_vigienature STOC": lambda: q.observations_vigienature(["STOC_EPS"], 2021),
    "aires_vigienature sites": lambda: q.aires_vigienature(["STOC_SITES", "STOC_ONF", "STOC_SITES_RNF"], True),
    "observateurs_faune_france": lambda: q.observateurs_faune_france(["1"]),
}
for module in ("stom", "sterf_ebms", "POPReptile", "POPAmphibien"):
    appels[f"aires_monitoring {module}"] = lambda m=module: q.aires_monitoring(m)
    appels[f"unites_monitoring {module}"] = lambda m=module: q.unites_monitoring(m)
    appels[f"passages_monitoring {module}"] = lambda m=module: q.passages_monitoring(m, 2019, m == "sterf_ebms")
    appels[f"observateurs_monitoring {module}"] = lambda m=module: q.observateurs_monitoring(m)
    appels[f"observations_monitoring {module}"] = lambda m=module: q.observations_monitoring(m, 2021)
appels["etats_pop"] = lambda: q.etats_pop("v_popamphibien_aire_annee")
appels["anomalies_pop"] = lambda: q.anomalies_pop("v_popreptiles_anomalies", 2025)

erreurs = 0
for nom, appel in appels.items():
    print(nom)
    try:
        appel()
    except Exception as e:  # noqa: BLE001 - on liste toutes les erreurs
        erreurs += 1
        conn.rollback()
        print(f"  ERREUR {e}")
conn.close()
print(f"{len(appels)} requêtes, {erreurs} erreur(s)")
sys.exit(1 if erreurs else 0)
