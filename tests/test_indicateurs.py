"""Tests du dossier Indicateurs de biodiversité (sans base ni QGIS : données factices)."""

import dataclasses
import re
from datetime import date

import pandas as pd
import pytest
from docx import Document

from reportgenerator.analysis.common.filesystem import create_analysis_dirs
from reportgenerator.analysis.indicateurs import cartes, chargement, communes, figures, participants, textes
from reportgenerator.analysis.indicateurs import selections as s
from reportgenerator.analysis.indicateurs import specifiques as sp
from reportgenerator.analysis.indicateurs.adaptateurs import jeu_monitoring, jeu_vigienature
from reportgenerator.analysis.indicateurs.modele import jeu_vide, verifier
from reportgenerator.analysis.indicateurs.queries import IndicateursQueries
from reportgenerator.analysis.indicateurs.selections import PROTOCOLES
from reportgenerator.bricks import indicateurs as bricks_indicateurs
from reportgenerator.bricks.indicateurs import cles_protocole
from reportgenerator.core.context import ReportContext
from reportgenerator.core.dossier import load_dossier
from reportgenerator.core.pipeline import check_dossier, run_pipeline
from reportgenerator.core.registry import get_brick
from tests.indicateurs_factice import DEPARTEMENTS, ZONE_WKT, jeu_factice, rendu_factice


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


def test_par_organisme_tiers():
    """Participation des organismes tiers en N : aires où l'un de leurs observateurs a fait un relevé, observateurs,
    données de ces relevés ; tri par aires décroissantes. Les autres catégories et saisons sont ignorées."""
    j = jeu_factice()
    ofb = {"id_observateur": "role:4", "nom": "Observateur 4", "organisme": "OFB", "categorie": "Organisme tiers"}
    j.observateurs = pd.concat([j.observateurs, pd.DataFrame([{**ofb, "id_passage": "P6"},
                                                              {**ofb, "id_passage": "P9"},
                                                              {**ofb, "id_passage": "P3"}])], ignore_index=True)
    assert communes.par_organisme(j, 2025) == [
        {"organisme": "OFB", "aires": 2, "observateurs": 1, "donnees": 14},
        {"organisme": "CEN Savoie", "aires": 1, "observateurs": 1, "donnees": 7},
    ]
    assert communes.par_organisme(j, 2023) == []


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
    c, c1 = communes.chiffres(j, 2025, TEMPS_MESURE), communes.chiffres(j, 2024, TEMPS_MESURE)
    tuiles = [("Sites suivis", c["aires"], c1["aires"]), ("Données", c["donnees"], None)]
    libelles = {"aires": "Sites", "saison": str}
    dep = communes.couverture(j, 2025, {}, par="departement")
    graphiques = [
        figures.chart_chiffres(tuiles, tmp_path / "c.png", "2025", "2024"),
        figures.chart_categories(communes.par_categorie(j, 2025, TEMPS_MESURE), tmp_path / "k.png", "sites"),
        figures.chart_organismes([{"organisme": "OFB", "aires": 2, "observateurs": 1, "donnees": 14},
                                  {"organisme": "Syndicat mixte d'aménagement des gorges de la Loire " * 2, "aires": 1,
                                   "observateurs": 1, "donnees": 7}], tmp_path / "org.png", "site"),
        figures.chart_groupes(dep, "departement", tmp_path / "g.png",
                              [("aires", "Suivis", figures.BLEU), ("nouvelles", "Nouveaux", figures.ORANGE)], "Sites"),
        figures.chart_barres({"1 passage": 2, "2 passages": 1}, tmp_path / "b.png", "Carrés"),
        figures.chart_objectifs([{"zone": "Zone alpine", "sites": 2, "objectif": 10},
                                 {"zone": "Plaine", "sites": 1, "objectif": "à définir"}], tmp_path / "z.png", "Sites"),
        figures.chart_historique(communes.serie(j, 2023, 2025, TEMPS_MESURE), tmp_path / "h.png", libelles, 2023),
        figures.chart_observateurs(communes.series_categories(j, 2023, 2025), tmp_path / "o.png"),
        figures.chart_especes(communes.especes(j, 2025, 20), tmp_path / "e.png", "site"),
        figures.chart_evolution(communes.evolution_especes(j, 2025, 3, 3), tmp_path / "v.png", str),
    ]
    jb = _avec_benevoles()
    graphiques += [
        figures.chart_renouvellement(participants.serie_statuts(jb, 2023, 2025, "Bénévole"), tmp_path / "r.png", str),
        figures.chart_statuts_departements(participants.statuts_par_departement(jb, 2025, "Bénévole"),
                                           tmp_path / "sd.png"),
        figures.chart_anciennete_engagement(participants.anciennete(jb, 2025, "Bénévole"),
                                            participants.engagement(jb, 2025, "Bénévole"), tmp_path / "ae.png", "site"),
        figures.chart_combinaisons([(("stoc", "shoc"), 12), (("stom", "sterf", "pop_reptile"), 2)], tmp_path / "cb.png",
                                   {"stoc": "STOC-EPS", "shoc": "SHOC", "stom": "STOM", "sterf": "STERF",
                                    "pop_reptile": "POP Reptile"}),
        figures.chart_reseau([{"saison": 2024, "participants": 300}, {"saison": 2025, "participants": 320}],
                             tmp_path / "rs.png", str),
    ]
    assert all(g.exists() and g.stat().st_size > 1000 for g in graphiques)
    vides = [
        figures.chart_categories([], tmp_path / "k0.png", "sites"),
        figures.chart_organismes([], tmp_path / "org0.png", "site"),
        figures.chart_renouvellement([{"saison": 2025, "fidèle": 0, "revenant": 0, "nouveau": 0, "parti": 0}],
                                     tmp_path / "r0.png", str),
        figures.chart_statuts_departements([], tmp_path / "sd0.png"),
        figures.chart_anciennete_engagement({"1 saison": 0}, {"1": 0}, tmp_path / "ae0.png", "site"),
        figures.chart_combinaisons([], tmp_path / "cb0.png", {}),
        figures.chart_reseau([], tmp_path / "rs0.png", str),
        figures.chart_especes([], tmp_path / "e0.png", "site"),
        figures.chart_evolution([], tmp_path / "v0.png", str),
        figures.chart_historique([], tmp_path / "h0.png", libelles, 2023),
        figures.chart_groupes([], "departement", tmp_path / "g0.png", [("aires", "x", "#000")], "x"),
    ]
    assert all(g.exists() for g in vides)


def test_tuiles_textes_dans_le_cadre():
    """Aucun texte d'une tuile ne dépasse de son fond, même avec de grands nombres et une saison d'hiver."""
    tuiles = [("Transects visités", 1480, 1295), ("Données", 123456, 98794), ("Temps (h), estimé", 12728, 10642),
              ("Observateurs", 127, 112), ("Espèces", 116, None), ("Carrés suivis", 148, 130)]
    f = figures.figure_chiffres(tuiles, "2025-2026", "2024-2025")
    rendu = f.canvas.get_renderer()
    for ax in f.axes:
        if not ax.get_visible():
            continue
        cadre = ax.get_window_extent(rendu)
        for t in ax.texts:
            b = t.get_window_extent(rendu)
            assert cadre.x0 <= b.x0 and b.x1 <= cadre.x1, f"« {t.get_text()} » dépasse de la tuile"
            assert cadre.y0 <= b.y0 and b.y1 <= cadre.y1, f"« {t.get_text()} » dépasse de la tuile"
    figures.plt.close(f)


# ------------------------------------------------------------------------------------------------ participants
def _avec_benevoles(code="stom"):
    """Jeu factice + bénévoles : b2 revenant (2023, 2025), b3 nouveau sur deux aires (2025), b4 parti (2024 seul),
    ff:9 sans compte (Non renseigné). role:1 est bénévole fidèle (2023-2025)."""
    j = jeu_factice(code)

    def obs(ident, cat, *passages):
        return [{"id_passage": p, "id_observateur": ident, "nom": ident, "organisme": None, "categorie": cat}
                for p in passages]
    ajout = (obs("b2", "Bénévole", "P2", "P9") + obs("b3", "Bénévole", "P6", "P8") + obs("b4", "Bénévole", "P5")
             + obs("ff:9", "Non renseigné", "P7"))
    j.observateurs = pd.concat([j.observateurs, pd.DataFrame(ajout)], ignore_index=True)
    return j


def test_statuts_participants():
    j = _avec_benevoles()
    assert participants.statuts(j, 2025, "Bénévole") == {"role:1": "fidèle", "b2": "revenant", "b3": "nouveau",
                                                         "b4": "parti"}
    assert participants.serie_statuts(j, 2023, 2025, "Bénévole") == [
        {"saison": 2023, "fidèle": 0, "revenant": 0, "nouveau": 2, "parti": 0},
        {"saison": 2024, "fidèle": 1, "revenant": 0, "nouveau": 1, "parti": 1},
        {"saison": 2025, "fidèle": 1, "revenant": 1, "nouveau": 1, "parti": 1},
    ]
    assert participants.statuts_par_departement(j, 2025, "Bénévole") == [
        {"departement": "Savoie", "fidèle": 1, "revenant": 0, "nouveau": 1, "parti": 0, "total": 2},
        {"departement": "Isère", "fidèle": 0, "revenant": 1, "nouveau": 0, "parti": 1, "total": 1},
    ]


def test_statuts_premiere_saison():
    """Première saison de la série : tous nouveaux, ni fidèle, ni revenant, ni parti."""
    j = _avec_benevoles()
    assert participants.statuts(j, 2023, "Bénévole") == {"role:1": "nouveau", "b2": "nouveau"}


def test_participants_hors_categorie():
    """Les « Non renseigné » et les autres catégories ne sont jamais comptés comme bénévoles."""
    j = _avec_benevoles()
    assert participants.participants(j, 2025, "Bénévole") == {"role:1", "b2", "b3"}
    assert participants.participants(j, 2025, "Organisme tiers") == {"role:3"}
    assert participants.participants(j, 2025, "Non renseigné") == {"ff:9"}


def test_anciennete_engagement_travail():
    j = _avec_benevoles()
    assert participants.anciennete(j, 2025, "Bénévole") == {"1 saison": 1, "2 à 4 saisons": 2, "5 à 9 saisons": 0,
                                                            "10 saisons et plus": 0}
    assert participants.engagement(j, 2025, "Bénévole") == {"1": 2, "2": 1, "3+": 0}
    t = participants.travail(j, 2025, "Bénévole", TEMPS_MESURE)
    assert (t["participants"], t["part_observateurs"]) == (3, 50)               # 3 bénévoles sur 6 observateurs
    assert (t["aires"], t["part_aires"]) == (2, 67)                             # A1 et A4 sur 3 aires suivies
    assert (t["releves"], t["donnees"]) == (2, 5)                               # P7 (3) et P9 (2)
    assert t["heures"] == communes.temps_heures(j, 2025, TEMPS_MESURE)["par_categorie"].get("Bénévole", 0)


def test_reseau_benevoles():
    """Réseau entre protocoles : comptes role: seulement (b2, b3 du STOM ignorés), chacun à la saison du protocole."""
    sterf = jeu_factice("sterf")
    role7 = {"id_passage": "P4", "id_observateur": "role:7", "nom": "x", "organisme": None, "categorie": "Bénévole"}
    sterf.observateurs = pd.concat([sterf.observateurs, pd.DataFrame([role7])], ignore_index=True)
    jeux = {"stom": _avec_benevoles("stom"), "sterf": sterf}
    saisons = {"stom": 2025, "sterf": 2025}
    assert participants.reseau(jeux, saisons, "Bénévole") == {
        "participants": 1, "multi": 1, "combinaisons": [(("stom", "sterf"), 1)]}
    assert participants.serie_reseau(jeux, 2023, 2025, "Bénévole") == [
        {"saison": 2023, "participants": 1}, {"saison": 2024, "participants": 2}, {"saison": 2025, "participants": 1}]
    assert participants.reseau_par_departement(jeux, saisons, "Bénévole") == [
        {"departement": "Savoie", "participants": 1}]


def test_aires_jamais_visitees():
    """Aires de la zone sans aucune visite, par catégorie du créateur et année de création ; créateur inconnu ou
    absent : « Non renseigné » ; aires visitées ignorées ; aucun email dans le résultat."""
    j = jeu_factice()
    nouvelles = pd.DataFrame([{**j.aires.iloc[0].to_dict(), "id_aire": a, "nom_aire": a} for a in ("A5", "A6", "A7")])
    j.aires = pd.concat([j.aires, nouvelles], ignore_index=True)
    createurs = [
        {"id_aire": "A1", "annee_creation": 2019, "organisme": None, "email": "a@exemple.fr", "connu": True},
        {"id_aire": "A5", "annee_creation": 2021, "organisme": None, "email": "b@exemple.fr", "connu": True},
        {"id_aire": "A6", "annee_creation": 2022, "organisme": None, "email": None, "connu": False},
    ]
    assert participants.aires_jamais_visitees(j, createurs) == [
        {"categorie": "Bénévole", "annee_creation": 2021, "aires": 1},
        {"categorie": "Non renseigné", "annee_creation": 2022, "aires": 1},
        {"categorie": "Non renseigné", "annee_creation": None, "aires": 1},
    ]


# ------------------------------------------------------------------------------------------ briques et dossier
def _ctx(tmp_path, monkeypatch, list_analyse, jeux):
    monkeypatch.setattr(chargement, "charger", lambda code, *a, **k: jeux.get(code, jeu_vide(code)))
    monkeypatch.setattr(IndicateursQueries, "zone", lambda self: {"wkt": ZONE_WKT, "surface_ha": 600000})
    monkeypatch.setattr(IndicateursQueries, "departements", lambda self: DEPARTEMENTS)
    monkeypatch.setattr(IndicateursQueries, "zones_biogeo", lambda self: [])
    monkeypatch.setattr(IndicateursQueries, "createurs_aires_monitoring", lambda self, module: [])
    d = load_dossier("indicateurs")
    enabled, _ = d.select_analyses(list_analyse)
    return ReportContext(service_name="factice", id_area=1, area_name="Test", referee="t", buffer=0, dossier=d,
                         enabled=enabled, output_dirs=create_analysis_dirs(tmp_path / "sortie"), queries=None,
                         params=d.params_for(list_analyse))


def test_section_benevoles(tmp_path, monkeypatch):
    """Sous-partie Bénévoles : texte, graphiques (tuiles, renouvellement, départements, ancienneté), annexes ;
    aucun nom ni identifiant de compte dans les blocs."""
    ctx = _ctx(tmp_path, monkeypatch, "indicateurs, stom, annee_2025", {"stom": _avec_benevoles("stom")})
    ctx.results["ind_socle"] = get_brick("ind_socle").run(ctx)
    r = get_brick("stom").run(ctx)
    texte = r.texts["STOM_TEXTE_BENEVOLES"]
    assert "3 bénévoles" in texte and "€" not in texte                       # valorisation absente (taux = 0)
    genres = [b[0] for b in r.tables["STOM_BLOCS_BENEVOLES"].data]
    assert genres.count("image") == 4 and "tableau" not in genres
    titres = [b[2] for b in r.data["annexe"] if b[0] == "titre"]
    assert {"Bénévoles : renouvellement par saison", "Bénévoles par département",
            "Bénévoles : ancienneté et engagement"} <= set(titres)
    assert not any(x in repr(r.tables["STOM_BLOCS_BENEVOLES"].data) + repr(r.data["annexe"])
                   for x in ("role:", "b2", "Observateur 1"))
    ctx.params["taux_horaire_benevolat"] = 12.5
    assert "€" in get_brick("stom").run(ctx).texts["STOM_TEXTE_BENEVOLES"]


def test_section_sans_benevole(tmp_path, monkeypatch):
    """Protocole sans bénévole : une phrase, pas de graphique, pas d'erreur."""
    j = jeu_factice("stom")
    j.observateurs = j.observateurs[j.observateurs["categorie"] != "Bénévole"]
    ctx = _ctx(tmp_path, monkeypatch, "indicateurs, stom, annee_2025", {"stom": j})
    ctx.results["ind_socle"] = get_brick("ind_socle").run(ctx)
    r = get_brick("stom").run(ctx)
    assert r.texts["STOM_TEXTE_BENEVOLES"].startswith("Aucun bénévole")
    assert [b[0] for b in r.tables["STOM_BLOCS_BENEVOLES"].data if b[0] == "image"] == []


def test_reseau_synthese(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path, monkeypatch, "indicateurs, stom, sterf, annee_2025",
               {"stom": _avec_benevoles("stom"), "sterf": jeu_factice("sterf")})
    ctx.results["ind_socle"] = get_brick("ind_socle").run(ctx)
    for code in ("stom", "sterf"):
        ctx.results[code] = get_brick(code).run(ctx)
    r = get_brick("ind_synthese").run(ctx)
    assert "1 bénévole" in r.texts["TEXTE_RESEAU_BENEVOLE"] and "deux protocoles" in r.texts["TEXTE_RESEAU_BENEVOLE"]
    assert [b[0] for b in r.tables["BLOCS_RESEAU_BENEVOLE"].data].count("image") >= 2


def test_titre_et_contexte_suivent_les_protocoles_demandes(tmp_path, monkeypatch):
    """Rapport limité à certains protocoles (list_analyse) : titre complété, contexte sans les autres protocoles."""
    seul = get_brick("ind_socle").run(_ctx(tmp_path, monkeypatch, "indicateurs, pop_reptile, annee_2025", {})).texts
    assert seul["TITRE_RAPPORT"] == "Indicateurs de biodiversité en Auvergne-Rhône-Alpes : POP Reptile"
    assert "POP Reptile" in seul["TEXTE_PROTOCOLES"] and "STOC" not in seul["TEXTE_PROTOCOLES"]
    tous = get_brick("ind_socle").run(_ctx(tmp_path, monkeypatch, "indicateurs, annee_2025", {})).texts
    assert tous["TITRE_RAPPORT"] == "Indicateurs de biodiversité en Auvergne-Rhône-Alpes"
    assert all(n in tous["TEXTE_PROTOCOLES"] for n in ("STOC-EPS", "SHOC", "STOM", "STERF", "POP Amphibien"))


def test_section_masquee_sans_aire(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path, monkeypatch, "indicateurs, annee_2025", {"stom": jeu_factice("stom")})
    ctx.results["ind_socle"] = get_brick("ind_socle").run(ctx)
    r = get_brick("sterf").run(ctx)
    assert r.meta == {"sans_section": True} and set(r.texts) == set(cles_protocole("sterf"))
    r = get_brick("stom").run(ctx)
    assert not (r.meta or {}).get("sans_section")
    assert "3 sites" in r.texts["STOM_TEXTE_PARTICIPATION"]
    assert set(r.texts) | set(r.tables) | set(r.images) == set(cles_protocole("stom"))


def test_annee_sans_passage_texte_explicite(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path, monkeypatch, "indicateurs, annee_2026", {"stom": jeu_factice("stom")})
    ctx.results["ind_socle"] = get_brick("ind_socle").run(ctx)
    r = get_brick("stom").run(ctx)
    texte = " ".join(str(v) for v in r.texts.values())
    assert "Aucun site suivi en 2026" in texte and "nan" not in texte


def test_dossier_indicateurs_declenchement():
    d = load_dossier("indicateurs")
    assert d.select_analyses("indicateurs")[0][-6:] == list(PROTOCOLES)
    assert d.select_analyses("indicateurs, stoc, annee_2024")[0] == list(d.required) + ["stoc"]
    assert d.params_for("indicateurs, annee_2024")["annee"] == 2024


def test_queries_refuse_vue_inconnue():
    q = IndicateursQueries("factice", 1)
    with pytest.raises(ValueError):
        q.etats_pop("v_autre; drop table x")
    with pytest.raises(ValueError):
        q.anomalies_pop("v_popreptiles_aire_annee", 2025)


def test_jeu_borne_a_la_saison_du_rapport():
    j = chargement.borner(jeu_factice(), annee_min=2025, saison=2024)
    assert j.passages["saison"].max() == 2024 and "A4" not in set(j.aires["id_aire"])   # A4 : première visite en 2025
    assert j.observations.empty and set(j.observateurs["id_passage"]) <= set(j.passages["id_passage"])


# ------------------------------------------------------------------------------------- analyses propres (STOC)
REGLE_P = {"periodes": [["05-01", "05-31"], ["06-01", "06-30"]], "periode_optionnelle": ["07-01", "07-31"],
           "libelle_optionnelle": "juillet"}


def test_passages_par_aire():
    # A1 (21/05) et A2 (11/06) : une période chacune ; A4 (01/07) : seulement la période optionnelle
    assert sp.passages_par_aire(jeu_factice(), 2025, REGLE_P) == {"1 passage": 2, "juillet seul": 1}


def test_part_organisme_et_aires_communes():
    j = jeu_factice()
    assert sp.part_organisme(j, 2025, "CEN Savoie") == (1, 33)
    assert sp.part_aires_communes(j, j, 2025, 2025) == (3, 100)


def test_stoc_sites_n2000():
    sites = jeu_factice()
    sites.aires["nom_aire"] = ["STOC N2000 A", "STOC N2000 B", "Autre", "STOC N2000 D"]
    regle_sites = {"motif_n2000": "STOC N2000%", "nb_especes_rang": 2, "debut_n2000": 2024}
    r = sp.stoc_sites_n2000(sites, jeu_factice(), 2025, regle_sites)
    assert (r["sites_suivis"], r["sites_total"], r["taxons_cumul"]) == (3, 3, 3)
    assert [x["nom"] for x in r["rangs"]] == ["Merle noir", "Pinson des arbres"]
    assert sp.autres_stoc_sites(sites, 2024, "STOC N2000%") == 1


def test_briques_stoc_shoc_blocs(tmp_path, monkeypatch):
    jeux = {"stoc": jeu_factice("stoc"), "shoc": jeu_factice("shoc")}
    monkeypatch.setattr(chargement, "charger_stoc_sites", lambda *a, **k: jeu_factice("stoc_sites"))
    ctx = _ctx(tmp_path, monkeypatch, "indicateurs, stoc, shoc, annee_2025", jeux)
    ctx.results["ind_socle"] = get_brick("ind_socle").run(ctx)
    titres = [b[2] for b in get_brick("stoc").run(ctx).tables["STOC_BLOCS_SPECIFIQUES"].data if b[0] == "titre"]
    assert titres == ["Passages réalisés", "STOC-sites", "Tendances MNHN"]   # 3 autres STOC-sites, aucun N2000
    blocs_shoc = get_brick("shoc").run(ctx).tables["SHOC_BLOCS_SPECIFIQUES"].data
    assert "3 carrés SHOC" in blocs_shoc[1][1]


# ---------------------------------------------------------------------------- analyses propres (STOM, STERF, POP)
def test_stom_liste():
    liste = sp.liste_sites_stom(jeu_factice(), 2025)
    assert liste[0] == {"date": "21/05/2025", "site": "A1", "departement": "Savoie",
                        "observateurs": "Observateur 1, Observateur 2"}
    assert len(liste) == 3


def test_sterf():
    j = jeu_factice()
    assert sp.classer_sterf(j, 2025, 5) == {"A1": "Site type STERF", "A2": "Site type STERF", "A4": "STERF vrai"}
    tot = sp.tableau_sterf(j, 2025, 5)[-1]
    assert (tot["sterf_vrais"], tot["sites_type"], tot["transects"], tot["donnees"]) == (1, 2, 4, 24)
    assert sp.unites_non_suivies(j, 2025) == 4                       # U4b à U4e
    assert sp.tableau_zbiog(j, 2025, {})[0]["objectif"] == "à définir"


def test_pop():
    j = jeu_factice()
    j.etats = pd.DataFrame({"id_aire": ["A1", "A2"], "saison": [2025, 2025], "etat": ["Complète", "Incomplète"]})
    assert sp.etats_pop(j, 2025) == {"Complète": 1, "Incomplète": 1}
    assert sp.avancement(j, 2025, {"objectif": 50, "objectif_sur": "aires"}) == (3, 50, 6)
    assert sp.avancement(j, 2025, {"objectif": 500, "objectif_sur": "unites"}) == (8, 500, 2)


def test_briques_monitoring_blocs(tmp_path, monkeypatch):
    jeux = {c: jeu_factice(c) for c in ("stom", "sterf", "pop_reptile", "pop_amphibien")}
    ctx = _ctx(tmp_path, monkeypatch, "indicateurs, stom, sterf, pop_reptile, pop_amphibien, annee_2025", jeux)
    ctx.results["ind_socle"] = get_brick("ind_socle").run(ctx)
    for code, prefixe, titre in (("stom", "STOM", "Sites suivis"),
                                 ("sterf", "STERF", "STERF vrais et sites type STERF"),
                                 ("pop_reptile", "POPR", "État des aires"), ("pop_amphibien", "POPA", "Objectif")):
        blocs_ = get_brick(code).run(ctx).tables[f"{prefixe}_BLOCS_SPECIFIQUES"].data
        assert titre in [b[2] for b in blocs_ if b[0] == "titre"]


# ------------------------------------------------------------------------------------------------------ synthèse
def test_synthese_ignore_protocole_vide(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path, monkeypatch, "indicateurs, annee_2025", {"stom": jeu_factice("stom")})
    ctx.results["ind_socle"] = get_brick("ind_socle").run(ctx)
    for code in ("stom", "sterf"):
        ctx.results[code] = get_brick(code).run(ctx)
    r = get_brick("ind_synthese").run(ctx)
    lignes = r.tables["TABLE_CHIFFRES_CLES"].data
    assert [ligne["protocole"] for ligne in lignes] == ["STOM"]
    assert "nan" not in r.texts["TEXTE_CONCLUSION"] and "STOM" in r.texts["TEXTE_CONCLUSION"]


def test_organismes_tiers_section_et_synthese(tmp_path, monkeypatch):
    """Chaque section montre les organismes tiers participants (graphique + tableau en annexe) ; la synthèse les
    croise avec les protocoles. Sans organisme tiers : une phrase à la place du graphique."""
    sans_tiers = jeu_factice("sterf")
    sans_tiers.observateurs = sans_tiers.observateurs[sans_tiers.observateurs["categorie"] != "Organisme tiers"]
    ctx = _ctx(tmp_path, monkeypatch, "indicateurs, stom, sterf, annee_2025",
               {"stom": jeu_factice("stom"), "sterf": sans_tiers})
    ctx.results["ind_socle"] = get_brick("ind_socle").run(ctx)
    for code in ("stom", "sterf"):
        ctx.results[code] = get_brick(code).run(ctx)
    stom = ctx.results["stom"]
    assert [b[0] for b in stom.tables["STOM_BLOCS_ORGANISMES"].data] == ["image", "legende"]
    assert ("titre", 3, "Organismes tiers participants") in stom.data["annexe"]
    assert [b[0] for b in ctx.results["sterf"].tables["STERF_BLOCS_ORGANISMES"].data] == ["texte"]
    synthese = get_brick("ind_synthese").run(ctx).tables["BLOCS_ORGANISMES"].data
    lignes, colonnes = synthese[0][1], synthese[0][2]
    assert synthese[0][0] == "tableau"
    assert [c for c, _ in colonnes] == ["organisme", "stom", "sterf"]
    assert lignes == [{"organisme": "CEN Savoie", "stom": "1 site · 1 obs.", "sterf": "—"}]


# ---------------------------------------------------------------------------------------------------------- cartes
def test_couches_cartes():
    c = cartes.couches_cartes({"stom": jeu_factice("stom")}, {"stom": 2025}, {"wkt": ZONE_WKT, "nom": "Test"},
                              DEPARTEMENTS, [])
    aires = {r["id_aire"]: r for r in c["ind_aires"]}
    attendu = {"A1": "suivie", "A2": "suivie", "A3": "non suivie", "A4": "nouvelle"}
    assert {a: r["statut"] for a, r in aires.items()} == attendu
    assert all(r["protocole"] == "stom" and r["geom"] is not None for r in c["ind_aires"])
    assert len(c["ind_departements"]) == 2 and c["ind_zbiog"] == []


def test_brique_cartes_sans_qgis(tmp_path, monkeypatch):
    projet = tmp_path / "p.qgs"
    projet.write_text('<Layout name="STOM_CARTE"/><Layout name="STOC_CARTE"/>', encoding="utf-8")
    monkeypatch.setattr(bricks_indicateurs, "launch_qgis_render", rendu_factice)
    ctx = _ctx(tmp_path, monkeypatch, "indicateurs, stom, annee_2025", {"stom": jeu_factice("stom")})
    ctx.dossier = dataclasses.replace(ctx.dossier, qgis_project=projet)
    for nom in ("ind_socle", "stom"):
        ctx.results[nom] = get_brick(nom).run(ctx)
    r = get_brick("ind_cartes").run(ctx)
    assert set(r.images) == {"STOM_CARTE"}   # protocole non demandé (STOC) : carte non rendue
    assert (ctx.output_dirs["data"] / "ind_aires.gpkg").exists()


def test_couches_cartes_aire_sans_contour():
    j = jeu_factice("pop_amphibien")
    j.aires.loc[0, "wkt"] = float("nan")             # site « sans aire » : pas de contour
    c = cartes.couches_cartes({"pop_amphibien": j}, {"pop_amphibien": 2025}, {"wkt": ZONE_WKT}, DEPARTEMENTS, [])
    assert "A1" not in {r["id_aire"] for r in c["ind_aires"]} and len(c["ind_aires"]) == 3


# ------------------------------------------------------------------------------------------------- rendu complet
def test_rendu_complet_donnees_factices(tmp_path, monkeypatch):
    jeux = {c: jeu_factice(c) for c in PROTOCOLES}
    monkeypatch.setattr(chargement, "charger_stoc_sites", lambda *a, **k: jeu_factice("stoc_sites"))
    monkeypatch.setattr(bricks_indicateurs, "launch_qgis_render", rendu_factice)   # un PNG par mise en page
    ctx = _ctx(tmp_path, monkeypatch, "indicateurs, annee_2025", jeux)
    sortie = tmp_path / "rapport.docx"
    assert run_pipeline(ctx, output_file=sortie) == set()
    d = Document(sortie)
    texte = "\n".join(p.text for p in d.paragraphs)
    cellules = "\n".join(c.text for t in d.tables for row in t.rows for c in row.cells)
    assert "{{" not in texte and not re.search(r"\b(nan|None|NaN)\b", texte + cellules)
    assert "3 sites ont été suivis" in texte and "2024-2025" in texte


def test_dossier_indicateurs_pret():
    assert check_dossier(load_dossier("indicateurs")).ok


def test_couverture_compte_les_departements_des_aires(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path, monkeypatch, "indicateurs, stom, annee_2025", {"stom": jeu_factice("stom")})
    trois = DEPARTEMENTS + [{"code": "01", "nom": "Ain", "wkt": DEPARTEMENTS[0]["wkt"]}]
    monkeypatch.setattr(IndicateursQueries, "departements", lambda self: trois)
    ctx.results["ind_socle"] = get_brick("ind_socle").run(ctx)
    assert "sur 2 départements" in get_brick("stom").run(ctx).texts["STOM_TEXTE_COUVERTURE"]


def test_texte_couverture_un_seul_departement():
    c, fid = {"aires": 3}, {"nouvelles": 0, "abandonnees": 0}
    assert textes.texte_couverture("site", c, fid, True, 1).startswith("Les 3 sites suivis sont tous dans le même")
    assert "sur 2 départements" in textes.texte_couverture("site", c, fid, True, 2)


# ------------------------------------------------------------------------------ relecture finale (cas dégradés)
def test_completude_saison_vide_ne_plante_pas():
    regle = {"passages_par_unite": 4, "periode_unite": ["05-01", "08-31"]}
    assert communes.completude(jeu_factice("sterf"), 2026, regle) == {}


def test_rendu_annee_sans_passage_tous_protocoles(tmp_path, monkeypatch):
    jeux = {c: jeu_factice(c) for c in PROTOCOLES}
    monkeypatch.setattr(chargement, "charger_stoc_sites", lambda *a, **k: jeu_factice("stoc_sites"))
    monkeypatch.setattr(bricks_indicateurs, "launch_qgis_render", rendu_factice)
    ctx = _ctx(tmp_path, monkeypatch, "indicateurs, annee_2026", jeux)
    sortie = tmp_path / "rapport_2026.docx"
    assert run_pipeline(ctx, output_file=sortie) == set()
    d = Document(sortie)
    texte = "\n".join(p.text for p in d.paragraphs) + "\n".join(
        c.text for t in d.tables for row in t.rows for c in row.cells)
    assert not re.search(r"\b(nan|None|NaN)\b", texte)


def test_blocs_shoc_sans_carre_en_n():
    assert sp.blocs_shoc(jeu_factice("shoc"), jeu_factice("stoc"), 2026) == []


def test_table_zbiog_colonnes_par_zone_pour_un_departement(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path, monkeypatch, "indicateurs, stom, annee_2025", {"stom": jeu_factice("stom")})
    monkeypatch.setattr(IndicateursQueries, "departements", lambda self: DEPARTEMENTS[:1])
    deux_zones = [{"nom": "Zone alpine", "wkt": ZONE_WKT}, {"nom": "Plaine rhodanienne", "wkt": ZONE_WKT}]
    monkeypatch.setattr(IndicateursQueries, "zones_biogeo", lambda self: deux_zones)
    ctx.results["ind_socle"] = get_brick("ind_socle").run(ctx)
    r = get_brick("stom").run(ctx)
    couverture = r.tables["STOM_BLOCS_COUVERTURE"].data
    assert [b[0] for b in couverture] == ["tableau", "legende", "image", "legende"]   # liste des aires + graphique
    annexe = r.data["annexe"]
    i = annexe.index(("titre", 3, "Couverture par zone biogéographique"))
    colonnes = [c for c, _ in annexe[i + 1][2]]
    assert colonnes[:2] == ["zbiog", "aires"] and "commune" not in colonnes


def test_anomalies_observateur_inconnu_par_saison():
    aires = [{"id_aire": "C1", "nom_aire": "Carré 1", "wkt": None, "x": 0, "y": 0, "nb_unites": 1}]
    releves = [{"id_passage": i, "id_aire": "C1", "id_unite": "C1/1", "nom_unite": "1", "date": d,
                "observateur": "99", "nb_donnees": 1, "passage_mnhn": 1}
               for i, d in ((1, date(2023, 12, 10)), (2, date(2024, 12, 10)))]
    j = jeu_vigienature("shoc", aires, releves, [], [], [], REGLE_V)
    assert sorted(a["saison"] for a in j.anomalies if a["code"] == "observateur_inconnu") == [2024, 2025]


def test_template_sans_nom_de_collegue_dans_les_proprietes():
    props = Document(load_dossier("indicateurs").template).core_properties
    assert props.author == "LPO Auvergne-Rhône-Alpes" and props.last_modified_by == "LPO Auvergne-Rhône-Alpes"


def test_couches_cartes_categories_et_reconduction():
    c = cartes.couches_cartes({"stom": jeu_factice("stom")}, {"stom": 2025}, {"wkt": ZONE_WKT}, DEPARTEMENTS, [])
    aires = {r["id_aire"]: r for r in c["ind_aires"]}
    categories = {"A1": "Bénévole", "A2": "Organisme tiers", "A3": None, "A4": "Non renseigné"}
    assert {a: r["categorie"] for a, r in aires.items()} == categories
    # A3 : suivie en 2024, pas en 2025 (à reprendre) ; A1, A2, A4 : suivies en 2025
    reconduction = {"A1": "suivie", "A2": "suivie", "A3": "abandon", "A4": "suivie"}
    assert {a: r["reconduction"] for a, r in aires.items()} == reconduction


def test_analyses_propres_en_graphiques(tmp_path):
    j = jeu_factice("sterf")
    regle = {"seuil_sterf_vrai": 5, "objectif": 100, "objectifs_zbiog": {"Zone alpine": 10}}
    b = sp.blocs_sterf(j, 2025, regle, sortie=tmp_path)
    genres = [x[0] for x in b]
    assert "tableau" not in genres and genres.count("image") == 2 and genres.count("annexe") == 2
    assert all(x[1].exists() for x in b if x[0] == "image")
    # sans objectif chiffré : pas de graphique des objectifs (il répéterait la couverture par zone)
    b = sp.blocs_sterf(j, 2025, {**regle, "objectifs_zbiog": {}}, sortie=tmp_path)
    assert [x[0] for x in b].count("image") == 1
