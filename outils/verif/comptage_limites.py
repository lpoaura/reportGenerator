"""LECTURE SEULE : pour chaque zone de test, EXPLAIN du comptage, comptage réel (durée) et nombre de lignes de la vue
(même SELECT que la VM, sans la créer). Usage : limites_zones.py <list_analyse|-> <id_area> <buffer> [--sans-vue]"""
import re
import sys
import time
from contextlib import contextmanager
from types import SimpleNamespace

import psycopg
from psycopg.rows import dict_row

import reportgenerator.queries as q
from reportgenerator.core import registry
from reportgenerator.core.dossier import resolve_dossier
from reportgenerator.core.limites import statement_timeout_ms

list_analyse = "" if sys.argv[1] == "-" else sys.argv[1]
id_area, buffer = int(sys.argv[2]), int(sys.argv[3])
captured = []


class FakeCur:
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def execute(self, sql, *a): captured.append(sql)
    def fetchall(self): return []
    def fetchone(self): return {"n": 0}


class FakeConn:
    def cursor(self, **k): return FakeCur()


@contextmanager
def fake(_):
    yield FakeConn()


q.get_connection = fake
registry._load_bricks()
dossier = resolve_dossier(list_analyse)
params = dossier.params_for(list_analyse)
sq = q.SyntheseQueries("x", id_area, buffer)
registry.get_brick("socle_data").run(SimpleNamespace(params=params, queries=sq))
comptage = next(s for s in captured if "select count(*) as n from obs_final" in s)
vue = next(s for s in captured if "create materialized view" in s)
select = re.search(r"create materialized view \S+ as(.*?);", vue, re.S).group(1)

conn = psycopg.connect(service="gnlpoaura", row_factory=dict_row)
conn.read_only = True
with conn.cursor() as cur:
    cur.execute("EXPLAIN " + comptage)
    plan = [r["QUERY PLAN"] for r in cur.fetchall()]
    print(f"== {dossier.name} id_area={id_area} buffer={buffer} anneaux={sq.anneaux_km}")
    print("EXPLAIN comptage :", plan[0])
    # même délai qu'en génération (core/limites.py) : au-delà, la demande serait refusée
    lim = sq.limites
    cur.execute(f"set local statement_timeout = {statement_timeout_ms(lim.comptage_min)}")
    t = time.time()
    try:
        cur.execute(comptage)
    except psycopg.errors.QueryCanceled:
        print(f"Comptage arrêté après {time.time() - t:.0f} s (délai {lim.comptage_min} min) : demande REFUSÉE")
        sys.exit(0)
    n = cur.fetchone()["n"]
    print(f"Comptage : {n} en {time.time() - t:.1f} s (seuil {lim.donnees})"
          f"{' : demande REFUSÉE' if n > lim.donnees else ''}")
    cur.execute("set local statement_timeout = 0")
    if "--sans-vue" not in sys.argv:
        t = time.time()
        cur.execute(f"select count(*) as n from ({select}) v")
        print(f"Lignes de la vue : {cur.fetchone()['n']} en {time.time() - t:.1f} s")
conn.rollback()
conn.close()
