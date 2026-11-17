"""Tests du dossier Indicateurs de biodiversité (sans base ni QGIS : données factices)."""

import dataclasses
from datetime import date

import pandas as pd
import pytest

from reportgenerator.analysis.indicateurs import selections as s
from reportgenerator.analysis.indicateurs.adaptateurs import jeu_monitoring, jeu_vigienature
from reportgenerator.analysis.indicateurs.modele import jeu_vide, verifier
from tests.indicateurs_factice import jeu_factice


# ------------------------------------------------------------------------------------------------- règles métier
@pytest.mark.parametrize("organisme, email, attendu", [
    ("LPO Auvergne-Rhône-Alpes", "x@gmail.com", ("Salarié LPO", "LPO Auvergne-Rhône-Alpes")),
    (None, "prenom.nom@lpo.fr", ("Salarié LPO", "LPO")),
    (None, "a.b@ofb.gouv.fr", ("Organisme tiers", "OFB")),
    ("CEN Savoie", "a@cen.fr", ("Organisme tiers", "CEN Savoie")),
    ("-", None, ("Bénévole", None)),
    (None, None, ("Bénévole", None)),
])
def test_categorie_observateur(organisme, email, attendu):
    assert s.categorie_observateur(organisme, email) == attendu


def test_categorie_inconnue_et_priorite():
    assert s.categorie_observateur("LPO", "x@lpo.fr", connu=False) == ("Non renseigné", None)
    assert s.categorie_prioritaire(["Bénévole", "Organisme tiers"]) == "Organisme tiers"
    assert s.categorie_prioritaire([]) == "Non renseigné"


def test_saison_hiver():
    for d in (date(2024, 11, 20), date(2024, 12, 15), date(2025, 1, 20), date(2025, 2, 10)):
        assert s.saison(d, "hiver") == 2025
    assert s.saison(date(2025, 5, 2), "civile") == 2025
    assert s.libelle_saison(2025, "hiver") == "2024-2025" and s.libelle_saison(2025, "civile") == "2025"


def test_annee_par_defaut():
    assert s.annee_par_defaut(date(2026, 11, 17)) == 2026
    assert s.annee_par_defaut(date(2026, 9, 30)) == 2025


def test_periodes():
    p = [["04-01", "05-08"], ["05-09", "06-15"]]
    assert s.numero_periode(date(2025, 5, 8), p) == 1
    assert s.numero_periode(date(2025, 5, 9), p) == 2
    assert s.numero_periode(date(2025, 3, 20), p) is None
    assert s.dans_periode(date(2025, 3, 20), ["03-01", "03-31"])


def test_stoc_site_n2000():
    assert s.est_stoc_site_n2000("STOC N2000 Dombes 3", "STOC N2000%")
    assert not s.est_stoc_site_n2000("STOC ONF Chartreuse", "STOC N2000%")
    assert not s.est_stoc_site_n2000(None, "STOC N2000%")


def test_completer_durees():
    p = pd.DataFrame({"saison": [2025, 2025, 2025, 2024], "duree_min": [60, 30, None, None],
                      "duree_estimee": [False, False, False, False]})
    r = s.completer_durees(p)
    assert r["duree_min"].tolist()[:3] == [60, 30, 45] and r["duree_estimee"].tolist()[2] is True
    assert pd.isna(r["duree_min"].iloc[3])
    r = s.completer_durees(p, duree_defaut_min=60)
    assert r["duree_min"].tolist() == [60, 30, 60, 60] and r["duree_estimee"].tolist() == [False, False, True, True]


def test_verifier_jeu():
    assert verifier(jeu_vide("stoc")).code == "stoc"
    with pytest.raises(ValueError):
        verifier(dataclasses.replace(jeu_vide("stoc"), aires=pd.DataFrame({"id_aire": []})))


def test_jeu_factice_valide():
    j = jeu_factice()
    assert verifier(j) is j and len(j.passages) == 9 and len(j.unites) == 9


# ---------------------------------------------------------------------------------------------------- adaptateurs
REGLE_V = {"saison": "hiver", "debut_serie": 2015, "debut_observateurs": 2015}


def test_jeu_vigienature_saisons_categories_anomalies():
    aires = [{"id_aire": "C1", "nom_aire": "Carré 1", "wkt": "POINT(0 0)", "x": 0, "y": 0, "nb_unites": 2}]
    releves = [
        {"id_passage": 1, "id_aire": "C1", "id_unite": "C1/1", "nom_unite": "1", "date": date(2024, 12, 10),
         "observateur": "11", "nb_donnees": 5, "passage_mnhn": 1},
        {"id_passage": 2, "id_aire": "C1", "id_unite": "C1/2", "nom_unite": "2", "date": date(2025, 1, 12),
         "observateur": "99", "nb_donnees": 3, "passage_mnhn": 7},
        {"id_passage": 3, "id_aire": "C1", "id_unite": "C1/1", "nom_unite": "1", "date": date(2013, 12, 10),
         "observateur": "11", "nb_donnees": 1, "passage_mnhn": 1},
    ]
    obs = [{"observateur": "11", "id_role": 5, "nom": "A B", "email": "a@lpo.fr", "organisme": None}]
    loc = [{"id_aire": "C1", "commune": "X", "departement": "Savoie", "zbiog": "Alpes"}]
    j = jeu_vigienature("shoc", aires, releves, [], obs, loc, REGLE_V)
    assert j.passages["saison"].tolist() == [2025, 2025]                 # 2013 retiré (début de série)
    assert set(j.observateurs["categorie"]) == {"Salarié LPO", "Non renseigné"}
    assert {a["code"] for a in j.anomalies} == {"observateur_inconnu", "passage_mnhn"}
    assert "email" not in j.observateurs.columns
    assert j.aires.loc[0, "departement"] == "Savoie" and len(j.unites) == 2


def test_jeu_monitoring_durees_et_sans_aire():
    aires = [{"id_aire": "sans_aire", "nom_aire": "Sans aire", "wkt": None, "x": 0, "y": 0, "nb_unites": 1}]
    unites = [{"id_unite": "7", "id_aire": "sans_aire", "nom_unite": "Mare 7"}]
    passages = [
        {"id_passage": 1, "id_aire": "sans_aire", "id_unite": "7", "date": date(2025, 4, 1), "nb_donnees": 2,
         "duree_min": 40, "duree_estimee": False},
        {"id_passage": 2, "id_aire": "sans_aire", "id_unite": "7", "date": date(2025, 5, 1), "nb_donnees": 1,
         "duree_min": None, "duree_estimee": False},
    ]
    j = jeu_monitoring("pop_amphibien", aires, unites, passages, [], [], [], {"saison": "civile",
                       "debut_serie": 2022})
    assert j.passages["duree_min"].tolist() == [40, 40] and j.passages["duree_estimee"].tolist() == [False, True]
    assert [a["code"] for a in j.anomalies] == ["site_sans_aire"]


def test_adaptateurs_sans_ligne():
    assert jeu_vigienature("stoc", [], [], [], [], [], REGLE_V).passages.empty
    assert jeu_monitoring("stom", [], [], [], [], [], [], {"saison": "civile", "debut_serie": 2019}).aires.empty
