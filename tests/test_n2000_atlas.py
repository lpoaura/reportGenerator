"""Atlas des espèces Natura 2000 : ancienneté des données, fiche annuelle par espèce (2e page), sans base."""

from datetime import date

import matplotlib
from docx import Document

from reportgenerator.analysis.common.figures import insert_figure_list
from reportgenerator.analysis.n2000 import tables as t
from reportgenerator.analysis.n2000.dataviz import graphique_fiche

matplotlib.use("Agg")


def test_classe_anciennete():
    # 2026 : saison en cours et précédente / 2 à 5 ans / 6 à 10 ans / au-delà
    assert [t.classe_anciennete(a, 2026) for a in (2026, 2025, 2024, 2021, 2020, 2016, 2015)] == \
        ["tres_recent", "tres_recent", "recent", "recent", "ancien", "ancien", "tres_ancien"]
    assert t.classe_anciennete(None, 2026) is None
    assert t.classe_anciennete(2023, 2026, seuils=(3, 5, 10)) == "tres_recent"   # seuils du dossier.toml


def test_ordre_dessin_statut_puis_anciennete():
    o = t.ordre_dessin
    # le statut prime : un nicheur certain ancien passe au-dessus d'un nicheur possible récent
    assert o("ancien", "Nicheur certain") > o("tres_recent", "Nicheur possible") > o("tres_ancien", "Autres données")
    # à statut égal : les plus récentes au-dessus
    rangs = [o(a, "Nicheur probable") for a in ("tres_ancien", "ancien", "recent", "tres_recent")]
    assert rangs == sorted(rangs) and len(set(rangs)) == 4
    assert o(None, "Nicheur certain") < o("tres_ancien", "Nicheur certain")   # ancienneté inconnue : dessous


POINTS = [
    {"annee": 2024, "type_donnee": "Nicheur certain", "count_max": 2},
    {"annee": 2024, "type_donnee": "Nicheur possible", "count_max": 1},
    {"annee": 2025, "type_donnee": "Nicheur probable", "count_max": 3},
    {"annee": 2025, "type_donnee": "Autres données", "count_max": 30, "date": date(2025, 4, 14),
     "comportement": "Migration active", "behaviour": "Migration"},
    {"annee": 2026, "type_donnee": "Autres données", "count_max": None},
]


def test_fiche_oiseau():
    f = t.fiche_espece("Milan noir", POINTS, range(2016, 2027), nb_sites_recurrents=2, oiseau=True)
    lignes = {r["ligne"]: r for r in f["lignes"]}
    assert lignes["Données"]["2024"] == 2 and lignes["Données"]["2016"] == ""
    assert lignes["Données de nidification"]["2024"] == 2 and lignes["Données de nidification"]["2026"] == ""
    assert lignes["Nidification maximale"]["2024"] == "C" and lignes["Nidification maximale"]["2025"] == "Pr"
    assert lignes["Effectif max nidif."]["2025"] == 3 and lignes["Effectif max autres"]["2025"] == 30
    assert lignes["Effectif max autres"]["2026"] == ""                       # effectif non renseigné
    assert [c for c, _ in f["colonnes"]] == ["ligne", *map(str, range(2016, 2027))]
    assert f["titre"] == "Milan noir"
    assert f["texte"] == (
        "Espèce observée 3 années sur 11, de 2024 à 2026. "
        "La nidification est certaine 1 année et probable 1 année ; la dernière nidification certaine date de 2024. "
        "2 sites de nidification récurrents sont identifiés (cercles blancs sur la carte). "
        "L'effectif le plus élevé est de 30 individus, le 14/04/2025 (Migration active).")
    assert list(f["series"]) == ["Nicheur certain", "Nicheur probable", "Nicheur possible", "Autres données"]
    assert f["series"]["Autres données"][-2:] == [1, 1]


def test_phrases_nidification():
    tous = [{"annee": a, "type_donnee": "Nicheur certain"} for a in range(2016, 2027)]
    texte = t.fiche_espece("X", tous, range(2016, 2027), 0, True)["texte"]
    assert "La nidification est certaine chaque année." in texte
    sans = [{"annee": 2020, "type_donnee": "Nicheur probable"}, {"annee": 2022, "type_donnee": "Nicheur possible"}]
    texte = t.fiche_espece("X", sans, range(2016, 2027), 0, True)["texte"]
    assert ("La nidification est probable 1 année et possible 1 année, sans preuve de nidification certaine ; "
            "le dernier indice date de 2022.") in texte
    assert "Aucun site de nidification récurrent n'est identifié." in texte
    assert t.contexte_effectif({"comportement": "", "behaviour": "Inconnu", "type_donnee": "Nicheur certain"}) == \
        "nicheur certain"


def test_texte_lecture_atlas():
    texte = t.texte_lecture_atlas()
    assert "rond : 2 dernières saisons ; carré : 2 à 5 ans ; triangle : 6 à 10 ans ; losange : plus de 10 ans" in texte
    assert "moins de 50 m les uns des autres et notés au moins 3 années différentes" in texte
    assert "année par année (graphique et tableau)" in texte
    assert "année par année (tableau)" in t.texte_lecture_atlas((2, 5, 10), 30, 4, ("tableau",))


def test_fiche_autre_groupe():
    f = t.fiche_espece("Sonneur à ventre jaune", [{"annee": 2020, "type_donnee": "Autres données", "count_max": 1}],
                       range(2016, 2027))
    assert [r["ligne"] for r in f["lignes"]] == ["Données", "Effectif max"]   # pas de lignes de nidification
    assert f["texte"] == "Espèce observée 1 année sur 11, en 2020."            # effectif de 1 : pas de phrase
    assert list(f["series"]) == ["Autres données"]


def test_fiche_insere_sur_une_deuxieme_page(tmp_path):
    import matplotlib.pyplot as plt
    png = tmp_path / "carte.png"
    plt.figure(figsize=(2, 3)).savefig(png)
    doc = Document()
    doc.add_paragraph("{{ATLAS}}")
    fiche = t.fiche_espece("Milan noir", POINTS, range(2024, 2027), oiseau=True)
    fiche["graphique"] = tmp_path / "fiche.png"
    graphique_fiche(fiche, fiche["graphique"])
    insert_figure_list(doc, "{{ATLAS}}", [{"titre": "Oiseaux nicheurs", "figures": [
        {"path": png, "legende": "Répartition – Milan noir", "fiche": fiche}]}], note="[Commentaire]")
    textes = [p.text for p in doc.paragraphs]
    # titre, carte, légende, texte (nouvelle page), graphique, puis le texte à rédiger après le tableau
    assert textes[3].startswith("Milan noir. Espèce observée") and textes[-1] == "[Commentaire]"
    assert doc.paragraphs[3].paragraph_format.page_break_before
    assert doc.paragraphs[4]._p.xpath(".//pic:pic")                          # graphique
    assert len(doc.tables) == 1 and len(doc.tables[0].rows) == 6          # en-tête + 5 lignes
    assert [c.text for c in doc.tables[0].rows[0].cells] == ["", "2024", "2025", "2026"]
    corps = doc.element.body
    assert corps.index(doc.paragraphs[4]._p) < corps.index(doc.tables[0]._tbl) < corps.index(doc.paragraphs[-1]._p)


def test_fiche_sans_tableau(tmp_path):
    import matplotlib.pyplot as plt
    png = tmp_path / "carte.png"
    plt.figure(figsize=(2, 3)).savefig(png)
    doc = Document()
    doc.add_paragraph("{{ATLAS}}")
    fiche = {**t.fiche_espece("Milan noir", POINTS, range(2024, 2027), oiseau=True), "lignes": []}
    insert_figure_list(doc, "{{ATLAS}}", [{"titre": None, "figures": [
        {"path": png, "legende": "Répartition – Milan noir", "fiche": fiche}]}], note="[Commentaire]")
    assert not doc.tables and doc.paragraphs[-1].text == "[Commentaire]"
