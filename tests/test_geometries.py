"""Données localisées par une ligne ou un polygone (transects, placettes) : règle de la VM, couches de la carte,
tableau et phrase de méthode, section masquée sans donnée. Sans base ni QGIS."""

from contextlib import contextmanager

import pytest

import reportgenerator.queries as q
from reportgenerator.analysis.common.models import AnalysisResult
from reportgenerator.analysis.geometries import calculs as c


def test_protocole_et_couleurs():
    assert c.protocole("MONITORING_STERF_EBMS") == "STERF (papillons de jour)"
    assert c.protocole("MONITORING_POPREPTILE") == "POPReptile (reptiles)"
    assert c.protocole("MONITORING_ODONATES_STELI") == "Suivi ODONATES STELI"
    assert c.protocole("gn2pg_depobio") == c.protocole(None) == c.AUTRES
    teintes = c.couleurs([c.AUTRES, "Suivi A", "STERF (papillons de jour)", "Suivi B", "Suivi A"])
    assert teintes["STERF (papillons de jour)"] == "#e6550d" and teintes[c.AUTRES] == c.COULEUR_AUTRES
    assert teintes["Suivi A"] == c.PALETTE[0] and teintes["Suivi B"] == c.PALETTE[1]


OBJETS = [
    {"source": "gn2pg_depobio", "type_geom": "polygone", "nb_donnees": 3},
    {"source": "MONITORING_STERF_EBMS", "type_geom": "ligne", "nb_donnees": 40},
    {"source": "MONITORING_POPREPTILE", "type_geom": "ligne", "nb_donnees": 12},
]


def test_couches_par_type_avec_protocole_couleur_ordre():
    out = c.couches(OBJETS)
    assert [o["protocole"] for o in out["transects_lignes"]] == ["STERF (papillons de jour)", "POPReptile (reptiles)"]
    assert [o["ordre"] for o in out["transects_lignes"]] == [1, 2]          # protocoles connus en tête de légende
    poly = out["transects_polygones"][0]
    assert poly["protocole"] == c.AUTRES and poly["ordre"] == 3 and poly["couleur"] == c.COULEUR_AUTRES


def test_tableau_trie_par_protocole_puis_donnees():
    synthese = [
        {"source": "gn2pg_depobio", "jeu": "Inventaire", "type_geom": "polygone", "nb_objets": 2, "nb_donnees": 9,
         "premiere_annee": 2021, "derniere_annee": 2021},
        {"source": "MONITORING_STERF_EBMS", "jeu": "STERF_CD26", "type_geom": "ligne", "nb_objets": 4,
         "nb_donnees": 50, "premiere_annee": 2018, "derniere_annee": 2025},
        {"source": "MONITORING_STERF_EBMS", "jeu": "STERF_AURA", "type_geom": "ligne", "nb_objets": 8,
         "nb_donnees": 120, "premiere_annee": 2016, "derniere_annee": 2026},
    ]
    rows = c.tableau(synthese)
    assert [r["jeu"] for r in rows] == ["STERF_AURA", "STERF_CD26", "Inventaire (gn2pg_depobio)"]  # source : autres
    assert rows[0]["annees"] == "2016-2026" and rows[2]["annees"] == "2021" and rows[2]["type"] == "placettes"


def test_texte_methode():
    t = c.texte_methode({"ligne": 1799, "polygone": 12}, [{"type_geom": "polygone", "nb_donnees": 480}], 1000)
    assert "de moins de 1 km d'étendue" in t
    assert ": 1811 données (1799 sur des lignes et 12 sur des polygones)." in t
    assert "480 données rattachées à une emprise plus large" in t and "ne sont pas utilisées." in t
    t = c.texte_methode({}, [{"type_geom": "polygone", "nb_donnees": 1}], 1000)
    assert "aucune donnée de ce type ici." in t and "1 donnée rattachée" in t and "n'est pas utilisée." in t
    t = c.texte_methode({"polygone": 63}, [], 1000)
    assert ": 63 données, sur des polygones." in t and "rattachée" not in t


def test_emprise_marge():
    assert c.emprise([0, 0, 10000, 5000]) == [-2000, -2000, 12000, 7000]           # minimum 2 km
    assert c.emprise([0, 0, 100000, 10000]) == [-8000, -8000, 108000, 18000]       # 8 % du plus grand côté


# ------------------------------------------------------------------ VM : géométrie d'analyse et seuil d'étendue
@pytest.fixture
def sql_vm(monkeypatch):
    captured = []

    class Cur:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def execute(self, sql, *a): captured.append(sql)
        def fetchall(self): return []
        def fetchone(self): return {"n": 0}  # comptage avant la vue (core/limites.py)

    class Conn:
        def cursor(self, **k): return Cur()

    @contextmanager
    def fake(_):
        yield Conn()

    monkeypatch.setattr(q, "get_connection", fake)
    sq = q.SyntheseQueries("x", 1, 2)
    sq.set_global_data(anneaux_km=[1, 5], rayons_km={"defaut": 1, "ordres": {"Chiroptera": 5}})
    return sq, next(s for s in captured if "create materialized view" in s)


def test_vm_lignes_polygones_ramenes_au_point_representatif(sql_vm):
    sq, sql = sql_vm
    assert "ST_GeometryType(o.the_geom_local) = 'ST_Point'" not in sql          # plus de filtre « points seuls »
    assert "as the_geom_local" in sql and "s.the_geom_local as geom_origine" in sql
    assert "ST_PointOnSurface" in sql and "ST_ClosestPoint" in sql
    assert f"<= {q.GEOM_ETENDUE_MAX_M}" in sql and f"> {q.GEOM_ETENDUE_MAX_M}" not in sql
    # emprise et rayon par taxon mesurés depuis le point représentatif, pas depuis la géométrie entière
    assert "ST_Within(s.the_geom_local, (select geom from zone_etude" not in sql
    assert f"ST_DWithin({q.point_representatif_sql('s.the_geom_local')}" in sql
    # données écartées : mêmes filtres, condition inverse sur l'étendue
    assert f"> {q.GEOM_ETENDUE_MAX_M}" in sq._sql_geom_exclues and "from obs_rang s" in sq._sql_geom_exclues


# ------------------------------------------------------------------ brique geometries (fausse base)
class FakeGeometries:
    def __init__(self, objets):
        self._objets = objets

    def __call__(self, synthese_queries):
        return self

    def objets(self):
        return [{**o, "geom": "MULTILINESTRING((0 0,100 0))"} for o in self._objets]

    def synthese(self):
        return [{"source": o["source"], "jeu": "J", "type_geom": o["type_geom"], "nb_objets": 1,
                 "nb_donnees": o["nb_donnees"], "nb_especes": 2, "groupes": "Reptiles",
                 "premiere_annee": 2020, "derniere_annee": 2024} for o in self._objets]

    def enveloppe(self):
        return [0, 0, 10000, 10000]


class FakeSynthese:
    def geometries_exclues(self):
        return [{"type_geom": "polygone", "nb_donnees": 7}]


@pytest.mark.parametrize("objets", [OBJETS, []])
def test_brique_geometries(monkeypatch, tmp_path, objets):
    from reportgenerator.bricks import geometries as b
    from reportgenerator.core.context import ReportContext
    from reportgenerator.core.dossier import load_dossier

    monkeypatch.setattr(b, "GeometriesQueries", FakeGeometries(objets))
    exports = {}
    monkeypatch.setattr(b, "export_gpkg", lambda rows, d, layer_name, **k: exports.setdefault(layer_name, rows))
    ctx = ReportContext(service_name="x", id_area=1, area_name="t", referee="r", buffer=1,
                        dossier=load_dossier("generique"), enabled=[], output_dirs={"data": tmp_path},
                        queries=FakeSynthese(), params={})
    res = b.geometries(ctx)
    assert "7 données rattachées à une emprise plus large" in res.texts["TEXTE_GEOMETRIES"]
    assert res.meta["sans_section"] is (not objets)
    render = ctx.params.get("qgis_render") or {}
    if objets:
        assert len(exports["transects_lignes"]) == 2 and len(exports["transects_polygones"]) == 1
        assert render["categories_dynamiques"]["transects_lignes"] == ["protocole", "ordre", "couleur"]
        assert render["layout_extents"][b.CARTE] == [-2000, -2000, 12000, 12000]
        assert len(res.tables["TABLE_GEOMETRIES"].data) == 3
    else:
        assert "layout_extents" not in render


# ------------------------------------------------------------------ section {{#geometries}} masquée sans donnée
def test_section_masquee_quand_la_brique_le_demande(monkeypatch, tmp_path):
    from dataclasses import replace

    from reportgenerator.core import pipeline, registry
    from reportgenerator.core.context import ReportContext
    from reportgenerator.core.dossier import load_dossier

    registry._load_bricks()
    monkeypatch.setitem(registry._REGISTRY, "b_vide", registry.Brick("b_vide", lambda ctx: AnalysisResult(
        meta={"sans_section": True})))
    monkeypatch.setitem(registry._REGISTRY, "b_pleine", registry.Brick("b_pleine", lambda ctx: AnalysisResult()))
    vu = {}
    monkeypatch.setattr(pipeline, "render_report", lambda tpl, res, out, sections: vu.setdefault("s", sections))
    dossier = replace(load_dossier("generique"))
    ctx = ReportContext(service_name="x", id_area=1, area_name="t", referee="r", buffer=1, dossier=dossier,
                        enabled=["b_vide", "b_pleine"], output_dirs={}, queries=None, params={})
    pipeline.run_pipeline(ctx, tmp_path / "r.docx")
    assert vu["s"] == {"b_pleine"}
