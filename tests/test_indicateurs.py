"""Tests du dossier Indicateurs de biodiversité (sans base ni QGIS : données factices)."""

import dataclasses
from datetime import date

import pandas as pd
import pytest

from reportgenerator.analysis.indicateurs import communes, figures, textes
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


# ------------------------------------------------------------------------------------------ analyses communes (N)
TEMPS_MESURE = {"terrain_h": "mesure", "unite_terrain": "visite", "complement_h": 0, "unite_complement": "aire"}


def test_chiffres_2025():
    c = communes.chiffres(jeu_factice(), 2025, TEMPS_MESURE)
    assert (c["aires"], c["unites"], c["visites"], c["releves"]) == (3, 4, 3, 4)
    assert (c["observateurs"], c["donnees"], c["especes"]) == (3, 24, 3)
    assert c["heures"] == 3.0 and c["heures_estimees"] is True       # P9 complété à 45 min, P7 estimé


def test_categories_somme_egale_total():
    j = jeu_factice()
    assert communes.categorie_aires(j, 2025) == {"A1": "Bénévole", "A2": "Organisme tiers", "A4": "Non renseigné"}
    assert communes.categorie_passages(j)["P6"] == "Salarié LPO"
    lignes = {r["categorie"]: r for r in communes.par_categorie(j, 2025, TEMPS_MESURE)}
    assert sum(r["aires"] for r in lignes.values()) == 3
    assert sum(r["donnees"] for r in lignes.values()) == 24
    assert lignes["Salarié LPO"]["donnees"] == 12 and lignes["Non renseigné"]["donnees"] == 2


def test_temps_forfaitaires():
    j = jeu_factice()
    par_aire = {"terrain_h": 5, "unite_terrain": "aire", "complement_h": 1, "unite_complement": "aire"}
    par_visite = {"terrain_h": 2, "unite_terrain": "visite", "complement_h": 0, "unite_complement": "aire"}
    assert communes.temps_heures(j, 2025, par_aire)["heures"] == 18
    attendu = {"Salarié LPO": 2, "Organisme tiers": 2, "Non renseigné": 2}
    assert communes.temps_heures(j, 2025, par_visite) == {"heures": 6, "estime": True, "par_categorie": attendu}


def test_statut_completude_couverture():
    j = jeu_factice()
    assert communes.statut_aires(j, 2025) == {"A1": "suivie", "A2": "suivie", "A4": "nouvelle", "A3": "non suivie"}
    assert communes.completude(j, 2025, {"periodes": [["05-01", "06-30"]]}) == {
        "A1": "complète", "A2": "complète", "A4": "incomplète"}
    dep = communes.couverture(j, 2025, {"periodes": [["05-01", "06-30"]]}, par="departement")
    assert [(r["departement"], r["aires"]) for r in dep] == [("Isère", 1), ("Savoie", 2), ("Total", 3)]
    zb = communes.couverture(j, 2025, {"periodes": [["05-01", "06-30"]]}, par="zbiog")
    assert [(r["zbiog"], r["aires"]) for r in zb] == [("Plaine rhodanienne", 1), ("Zone alpine", 2), ("Total", 3)]


# ---------------------------------------------------------------------------- historique, fidélisation, espèces
def test_serie_et_categories():
    s_ = communes.serie(jeu_factice(), 2023, 2025, TEMPS_MESURE)
    assert [(r["saison"], r["aires"]) for r in s_] == [(2023, 2), (2024, 3), (2025, 3)]
    assert s_[0]["especes"] is None                                     # pas d'observations chargées en 2023
    cat = {r["saison"]: r for r in communes.series_categories(jeu_factice(), 2023, 2025)}
    assert cat[2025]["Bénévole"] == 1 and cat[2025]["Salarié LPO"] == 1 and cat[2025]["Organisme tiers"] == 1


def test_fidelisation():
    f = communes.fidelisation(jeu_factice(), 2025)
    assert (f["reconduites"], f["taux_reconduction_aires"], f["nouvelles"], f["abandonnees"]) == (2, 67, 1, 1)
    assert (f["observateurs_gagnes"], f["observateurs_perdus"], f["taux_reconduction_observateurs"]) == (0, 0, 100)
    assert (f["cumul_aires"], f["cumul_observateurs"], f["anciennete_moyenne"]) == (4, 3, 2.0)
    assert f["plus_ancienne"]["premiere"] == 2023 and f["plus_ancienne"]["annees"] == 3


def test_especes():
    e = communes.especes(jeu_factice(), 2025, n=None)
    assert [(r["nom"], r["freq_aires"], r["freq_unites"], r["effectif"]) for r in e] == [
        ("Merle noir", 67, 75, 6), ("Pinson des arbres", 67, 50, 6), ("Rouge-gorge familier", 33, 25, 1)]
    evo = communes.evolution_especes(jeu_factice(), 2025, n=2, annees=2)
    assert evo[0]["nom"] == "Merle noir" and evo[0][2024] == 33 and evo[0][2025] == 67


def test_observateurs_multi_protocoles():
    j = jeu_factice()
    assert communes.observateurs_multi_protocoles({"a": j, "b": j}, {"a": 2025, "b": 2025}) == 3


# --------------------------------------------------------------------------------------------- textes et figures
def test_ecart():
    assert textes.ecart(24, 18) == "+6 (+33 %)"
    assert textes.ecart(3, 3) == "="
    assert textes.ecart(18, 20) == "−2 (−10 %)"
    assert textes.ecart(5, None) == "—"
    assert textes.ecart(5, 0) == "+5"


def test_nombre():
    assert textes.nombre(81561) == "81\u202f561" and textes.nombre(10.5) == "10,5"


def test_textes_sans_aire():
    vide = {"aires": 0, "observateurs": 0, "donnees": 0, "heures": 0, "heures_estimees": False}
    t = textes.texte_participation("STOM", "site", "2025", vide, None, "")
    assert t == "Aucun site suivi en 2025 dans la zone."
    assert textes.texte_participation("POP Reptile", "aire", "2025", vide, None, "").startswith("Aucune aire suivie")


def test_figures(tmp_path):
    j = jeu_factice()
    assert figures.chart_aires(communes.serie(j, 2023, 2025, TEMPS_MESURE), tmp_path / "a.png", "site").exists()
    assert figures.chart_observateurs(communes.series_categories(j, 2023, 2025), tmp_path / "o.png").exists()
