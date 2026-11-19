"""Limites de génération et bilan des demandes (docs/limites/conception.md) : sans base de données ni QGIS."""

from datetime import datetime
from types import SimpleNamespace

import pytest

from reportgenerator import queries as q
from reportgenerator import run_queue, run_single, suivi
from reportgenerator.core.limites import (ComptageTropLong, Limites, TropDeDonnees, VueTropLongue, bilan_echec,
                                          bilan_en_cours, bilan_interrompu, bilan_ok, duree)

QUAND = datetime(2026, 11, 19, 14, 9)


# --- textes et bilans ---

def test_duree_lisible():
    assert duree(45) == "45 s"
    assert duree(432) == "7 min 12 s"
    assert duree(1800) == "30 min"
    assert duree(3720) == "1 h 2 min"


def test_limites_du_dossier():
    assert Limites.du_dossier({}) == Limites(1_000_000, 5, 30)
    assert Limites.du_dossier({"limite_donnees": 2_000_000, "limite_vue_min": 60}) == Limites(2_000_000, 5, 60)
    assert Limites.du_dossier({"limite_donnees": 10}, sans_limite=True) == Limites(None, None, None)


def test_bilan_en_cours_sans_date():
    b = bilan_en_cours(QUAND, "generique")
    assert b.statut == "en_cours"
    assert b.commentaire == "EN COURS depuis le 19/11/2026 14:09"
    assert b.details["dossier"] == "generique"


def test_bilan_ok_avec_vue():
    b = bilan_ok(QUAND, 432, "generique", nb_donnees=352410, duree_vue_s=220)
    assert b.statut == "ok"
    assert b.commentaire == "OK le 19/11/2026 14:09 : 7 min 12 s (vue 3 min 40 s), 352 410 données"
    assert b.details == {"dossier": "generique", "duree_s": 432, "duree_vue_s": 220, "nb_donnees": 352410}


def test_bilan_ok_sans_vue():
    b = bilan_ok(QUAND, 123, "indicateurs")
    assert b.commentaire == "OK le 19/11/2026 14:09 : 2 min 3 s"
    assert "nb_donnees" not in b.details


def test_bilan_refus_trop_de_donnees():
    b = bilan_echec(TropDeDonnees(1_532_004, 1_000_000), QUAND, 12, "eolien")
    assert b.statut == "refuse"
    assert b.commentaire.startswith("REFUSÉ le 19/11/2026 14:09 : trop de données, 1 532 004 > 1 000 000.")
    assert "--sans-limite" in b.commentaire
    assert b.details["motif"] == "trop_de_donnees"
    assert b.details["nb_donnees"] == 1_532_004 and b.details["seuil_donnees"] == 1_000_000


def test_bilan_refus_comptage_trop_long():
    b = bilan_echec(ComptageTropLong(5), QUAND, 300, "generique")
    assert b.statut == "refuse"
    assert b.commentaire.startswith("REFUSÉ le 19/11/2026 14:09 : comptage des données trop long (> 5 min).")
    assert b.details["motif"] == "comptage_trop_long"


def test_bilan_echec_vue_trop_longue():
    b = bilan_echec(VueTropLongue(30, nb_donnees=900_000), QUAND, 1810, "n2000")
    assert b.statut == "erreur"
    assert b.commentaire == "ÉCHEC le 19/11/2026 14:09 : temps de calcul trop long, vue arrêtée après 30 min"
    assert b.details["motif"] == "temps_de_calcul" and b.details["nb_donnees"] == 900_000


def test_bilan_echec_erreur_avec_brique():
    e = KeyError("x")
    e.brique = "sp_patrimoniales"
    b = bilan_echec(e, QUAND, 65, "generique")
    assert b.statut == "erreur"
    assert b.commentaire == "ÉCHEC le 19/11/2026 14:09 : erreur KeyError: 'x' (brique sp_patrimoniales)"
    assert b.details["motif"] == "erreur" and b.details["brique"] == "sp_patrimoniales"


def test_bilan_echec_message_tronque():
    b = bilan_echec(ValueError("a" * 5000), QUAND, 1, "generique")
    assert len(b.commentaire) < 700


def test_bilan_interrompu():
    b = bilan_interrompu(QUAND)
    assert b.statut == "erreur"
    assert b.commentaire == "ÉCHEC le 19/11/2026 14:09 : génération interrompue (processus arrêté)"
    assert b.details["motif"] == "interrompue"


# --- comptage et délais de la vue de synthèse (connexion factice) ---

class QueryCanceled(Exception):
    """Même nom que psycopg.errors.QueryCanceled (délai statement_timeout dépassé)."""


class FausseBase:
    def __init__(self, nb=1000, annule=None):
        self.nb, self.annule, self.sql = nb, annule, []

    def cursor(self, **_):
        return self

    def connection(self, *_a, **_k):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.sql.append(sql)
        if self.annule and self.annule in sql:
            raise QueryCanceled("canceling statement due to statement timeout")

    def fetchone(self):
        return {"n": self.nb}

    def fetchall(self):
        return []

    def contient(self, texte):
        return [i for i, s in enumerate(self.sql) if texte in s]


def _vue(monkeypatch, base, limites):
    monkeypatch.setattr(q, "get_connection", base.connection)
    monkeypatch.setattr(q, "DELAI_DEPASSE", (QueryCanceled,))
    sq = q.SyntheseQueries("svc", 1, 2, limites=limites)
    sq.set_global_data()
    return sq


def test_comptage_sous_le_seuil_puis_vue_avec_delai(monkeypatch):
    base = FausseBase(nb=1000)
    sq = _vue(monkeypatch, base, Limites(1_000_000, 5, 30))
    comptage = base.contient("select count(*) as n from obs_final")
    vue = base.contient("create materialized view")
    assert comptage and vue and comptage[0] < vue[0]
    assert "statement_timeout = 300000" in base.sql[comptage[0] - 1]
    assert "statement_timeout = 1800000" in base.sql[vue[0] - 1]
    assert sq.nb_donnees_comptees == 1000
    assert sq.nb_donnees == 1000 and sq.duree_vue_s is not None


def test_comptage_au_dessus_du_seuil_sans_vue(monkeypatch):
    base = FausseBase(nb=1_500_000)
    with pytest.raises(TropDeDonnees) as e:
        _vue(monkeypatch, base, Limites(1_000_000, 5, 30))
    assert e.value.nb == 1_500_000 and e.value.seuil == 1_000_000
    assert not base.contient("create materialized view")


def test_comptage_trop_long(monkeypatch):
    base = FausseBase(annule="select count(*) as n from obs_final")
    with pytest.raises(ComptageTropLong):
        _vue(monkeypatch, base, Limites(1_000_000, 5, 30))
    assert not base.contient("create materialized view")


def test_vue_trop_longue(monkeypatch):
    base = FausseBase(nb=800_000, annule="create materialized view")
    with pytest.raises(VueTropLongue) as e:
        _vue(monkeypatch, base, Limites(1_000_000, 5, 30))
    assert e.value.delai_min == 30 and e.value.nb_donnees == 800_000


def test_sans_limite_ni_comptage_ni_delai(monkeypatch):
    base = FausseBase(nb=5_000_000)
    _vue(monkeypatch, base, Limites(None, None, None))
    assert not base.contient("from obs_final o where")
    vue = base.contient("create materialized view")[0]
    assert "statement_timeout = 0" in base.sql[vue - 1]


# --- génération d'un rapport : bilan écrit dans tous les cas ---

def _run_single(monkeypatch, tmp_path, pipeline):
    bilans = []
    dossier = SimpleNamespace(name="generique", label="Générique", select_analyses=lambda la: (["socle_data"], []),
                              params_for=lambda la: {"limite_donnees": 10})
    monkeypatch.setattr(run_single, "resolve_dossier", lambda la: dossier)
    monkeypatch.setattr(run_single, "run_pipeline", pipeline)
    monkeypatch.setattr(run_single, "ecrire_bilan", lambda svc, id_area, b: bilans.append((id_area, b)))

    class SQ:
        def __init__(self, **kw):
            self.limites, self.nb_donnees, self.duree_vue_s = kw["limites"], 42, 3.0
            SQ.instance = self

        def delete_reportgenerator_view(self):
            self.supprimee = True

    monkeypatch.setattr(run_single, "SyntheseQueries", SQ)
    kw = dict(service_name="svc", id_area=7, referee="r", list_analyse="", buffer=2, area_name="Zone",
              output="Zone.docx", output_dir_base=tmp_path)
    return bilans, SQ, kw


def test_run_single_ok_ecrit_en_cours_puis_ok(monkeypatch, tmp_path):
    bilans, SQ, kw = _run_single(monkeypatch, tmp_path, lambda ctx, output_file: set())
    run_single.run_single_report(**kw)
    assert [b.statut for _, b in bilans] == ["en_cours", "ok"]
    assert bilans[1][0] == 7 and bilans[1][1].details["nb_donnees"] == 42
    assert SQ.instance.supprimee
    assert SQ.instance.limites == Limites(10, 5, 30)


def test_run_single_erreur_ecrit_le_bilan_et_relance_l_exception(monkeypatch, tmp_path):
    def plante(ctx, output_file):
        raise TropDeDonnees(20, 10)

    bilans, SQ, kw = _run_single(monkeypatch, tmp_path, plante)
    with pytest.raises(TropDeDonnees):
        run_single.run_single_report(**kw)
    assert [b.statut for _, b in bilans] == ["en_cours", "refuse"]
    assert SQ.instance.supprimee


def test_run_single_sans_limite(monkeypatch, tmp_path):
    bilans, SQ, kw = _run_single(monkeypatch, tmp_path, lambda ctx, output_file: set())
    run_single.run_single_report(**kw, sans_limite=True)
    assert SQ.instance.limites == Limites(None, None, None)


def test_run_single_nom_invalide_marque_en_erreur(monkeypatch, tmp_path):
    bilans, SQ, kw = _run_single(monkeypatch, tmp_path, lambda ctx, output_file: set())
    kw["area_name"] = "../x"
    with pytest.raises(ValueError):
        run_single.run_single_report(**kw)
    assert [b.statut for _, b in bilans][-1] == "erreur"


def test_pipeline_note_la_brique_en_erreur(monkeypatch, tmp_path):
    from reportgenerator.core import pipeline

    def plante(ctx):
        raise KeyError("x")

    template = tmp_path / "t.docx"
    template.write_bytes(b"")
    brique = SimpleNamespace(requires=[], last=False, run=plante)
    monkeypatch.setattr(pipeline, "get_brick", lambda n: brique)
    ctx = SimpleNamespace(dossier=SimpleNamespace(name="d", template=template), enabled=["b1"], results={})
    with pytest.raises(KeyError) as e:
        pipeline.run_pipeline(ctx, tmp_path / "out.docx")
    assert e.value.brique == "b1"


# --- file d'attente : verrou, demandes interrompues, plus de filtre de surface ---

def _file(monkeypatch, verrou=True, interrompues=()):
    lances, bilans = [], []
    pending = [{"id_area": i, "area_name": f"Z{i}", "referee": "r", "list_analyse": "", "buffer": 2,
                "area_km2": 5000} for i in (1, 2, 3)]

    class Verrou:
        def __enter__(self):
            return verrou

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(run_queue, "verrou_generate", lambda svc: Verrou())
    monkeypatch.setattr(run_queue, "get_connection", lambda svc: Verrou())
    monkeypatch.setattr(run_queue, "get_pending_areas", lambda conn: pending)
    monkeypatch.setattr(run_queue, "demandes_interrompues", lambda conn, ids: [i for i in ids if i in interrompues])
    monkeypatch.setattr(run_queue, "ecrire_bilan", lambda svc, id_area, b: bilans.append((id_area, b)))
    monkeypatch.setattr(run_queue, "run_single_report", lambda **kw: lances.append(kw["id_area"]))
    return lances, bilans


def test_file_traite_les_grandes_zones(monkeypatch):
    lances, _ = _file(monkeypatch)
    run_queue.run_all_report("svc")
    assert lances == [1, 2, 3]


def test_file_verrou_deja_pris(monkeypatch):
    lances, bilans = _file(monkeypatch, verrou=False)
    run_queue.run_all_report("svc")
    assert lances == [] and bilans == []


def test_file_demande_interrompue_marquee_et_ignoree(monkeypatch):
    lances, bilans = _file(monkeypatch, interrompues=(2,))
    run_queue.run_all_report("svc")
    assert lances == [1, 3]
    assert [(i, b.details["motif"]) for i, b in bilans] == [(2, "interrompue")]


def test_get_pending_areas_sans_filtre_de_surface():
    base = FausseBase()
    run_queue.get_pending_areas(base)
    assert "st_area" not in base.sql[0].split("WHERE")[1].lower()


# --- écriture du bilan en base ---

class UndefinedFunction(Exception):
    """Même nom que psycopg.errors.UndefinedFunction (fonction pas encore créée en base)."""


def test_ecrire_bilan_appelle_la_fonction(monkeypatch):
    base = FausseBase()
    monkeypatch.setattr(suivi, "get_connection", base.connection)
    suivi.ecrire_bilan("svc", 7, bilan_ok(QUAND, 10, "generique"))
    assert "update_reportgenerator_bilan" in base.sql[0]


def test_ecrire_bilan_repli_sur_la_date(monkeypatch):
    base = FausseBase(annule="update_reportgenerator_bilan")
    monkeypatch.setattr(suivi, "get_connection", base.connection)
    monkeypatch.setattr(suivi, "FONCTION_ABSENTE", (QueryCanceled,))
    suivi.ecrire_bilan("svc", 7, bilan_echec(KeyError("x"), QUAND, 10, "generique"))
    assert "update_reportgenerator_date" in base.sql[-1]


def test_ecrire_bilan_en_cours_sans_repli(monkeypatch):
    base = FausseBase(annule="update_reportgenerator_bilan")
    monkeypatch.setattr(suivi, "get_connection", base.connection)
    monkeypatch.setattr(suivi, "FONCTION_ABSENTE", (QueryCanceled,))
    suivi.ecrire_bilan("svc", 7, bilan_en_cours(QUAND, "generique"))
    assert not any("update_reportgenerator_date" in s for s in base.sql)


def test_ecrire_bilan_n_echoue_jamais(monkeypatch):
    def connexion_impossible(svc):
        raise OSError("base injoignable")

    monkeypatch.setattr(suivi, "get_connection", connexion_impossible)
    suivi.ecrire_bilan("svc", 7, bilan_ok(QUAND, 10, "generique"))  # pas d'exception : l'erreur d'origine prime
