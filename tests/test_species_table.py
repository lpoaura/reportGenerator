"""Tableau des espèces du rapport générique : tri par groupe taxonomique puis par nom, intertitres de groupe."""

from docx import Document
from docx.oxml.ns import qn

from reportgenerator.analysis.common.tables.species_table import insert_species_table, trier_par_groupe

ESPECES = [
    {"nom_vern": "Vipère aspic", "lb_nom": "Vipera aspis", "tx_group2_inpn_v2": "Reptiles"},
    {"nom_vern": "Merle noir", "lb_nom": "Turdus merula", "tx_group2_inpn_v2": "Oiseaux"},
    {"nom_vern": "Écureuil roux", "lb_nom": "Sciurus vulgaris", "tx_group2_inpn_v2": "Mammifères"},
    {"nom_vern": "Aigle royal", "lb_nom": "Aquila chrysaetos", "tx_group2_inpn_v2": "Oiseaux"},
    {"nom_vern": "Fouine", "lb_nom": "Martes foina", "tx_group2_inpn_v2": "Mammifères"},
    {"nom_vern": "Criquet", "lb_nom": "X", "tx_group2_inpn_v2": "Groupe inconnu"},
]


def test_tri_groupe_puis_nom_sans_accents():
    noms = [r["nom_vern"] for r in trier_par_groupe(ESPECES)]
    # oiseaux, mammifères (« Écureuil » avec les E, avant « Fouine »), reptiles, puis groupes hors liste
    assert noms == ["Aigle royal", "Merle noir", "Écureuil roux", "Fouine", "Vipère aspic", "Criquet"]


def test_tableau_avec_intertitres_de_groupe():
    doc = Document()
    doc.add_paragraph("{{TABLE_ESP}}")
    insert_species_table(doc, "{{TABLE_ESP}}", ESPECES)
    rows = doc.tables[0].rows
    premieres = [r.cells[0].text for r in rows]
    assert premieres == ["Nom vernaculaire", "Oiseaux — 2 espèces", "Aigle royal", "Merle noir",
                         "Mammifères — 2 espèces", "Écureuil roux", "Fouine", "Reptiles — 1 espèce", "Vipère aspic",
                         "Groupe inconnu — 1 espèce", "Criquet"]
    assert rows[1].cells[0]._tc is rows[1].cells[-1]._tc                       # intertitre sur toute la largeur
    assert rows[0]._tr.trPr.find(qn("w:tblHeader")) is not None                 # en-tête répété à chaque page


def test_tableau_sans_groupes_garde_l_ordre():
    doc = Document()
    doc.add_paragraph("{{T}}")
    insert_species_table(doc, "{{T}}", ESPECES[:2], par_groupe=False)
    assert [r.cells[0].text for r in doc.tables[0].rows] == ["Nom vernaculaire", "Vipère aspic", "Merle noir"]
