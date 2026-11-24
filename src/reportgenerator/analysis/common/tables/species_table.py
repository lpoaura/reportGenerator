import unicodedata

from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt  # noqa: F401

from reportgenerator.analysis.common.tables.utils import (
    apply_status_style_species, italicize_cell_species, set_cell_background,
    set_cell_font, set_cell_text_color)
from reportgenerator.analysis.connaissance.indicateurs import ordre_groupe

CHAMP_GROUPE = "tx_group2_inpn_v2"


def _sans_accents(texte) -> str:
    return unicodedata.normalize("NFKD", str(texte or "")).encode("ascii", "ignore").decode().casefold()


def trier_par_groupe(data, champ_groupe=CHAMP_GROUPE):
    """Espèces triées par groupe taxonomique (ordre de l'état des connaissances : oiseaux, mammifères, chauves-souris,
    amphibiens..., autres groupes par ordre alphabétique), puis par nom vernaculaire (accents ignorés : « Écureuil »
    avec les E), puis nom scientifique."""
    return sorted(data, key=lambda r: (ordre_groupe(r.get(champ_groupe)), _sans_accents(r.get(champ_groupe)),
                                       _sans_accents(r.get("nom_vern")), _sans_accents(r.get("lb_nom"))))


# =========================================================
# CONFIGURATION STANDARD DU TABLEAU ESPÈCES
# =========================================================

SPECIES_COLUMNS = [
    ("nom_vern", "Nom vernaculaire"),
    ("lb_nom", "Nom scientifique"),
    ("prot_nat", "Protection nationale"),
   # ("lr_france", "LR\nFrance"),
    ("lr_fr_nich", "LR France\nN"),
    ("lr_fr_hiv", "LR France\nHivernant"),
    ("lr_fr_migr", "LR France\nMigration"),
    ("lr_aura", "LR AuRA"),
    ("nb_annees_observation", "Nb\nannées obs."),
    ("nb_observations", "Nb\ndonnées"),
    ("derniere_annee_observation", "Dernière\nobs."),
]

STATUS_FIELDS = [
    "lr_fr_nich",
    "lr_fr_hiv",
    "lr_fr_migr",
    "lr_aura",
    "lr_france",
]

SCIENTIFIC_FIELDS = [
    "lb_nom",
]

CENTER_FIELDS = [
    "lr_fr_nich",
    "lr_fr_hiv",
    "lr_fr_migr",
    "lr_aura",
    "lr_france",
    "nb_observations",
    "derniere_annee_observation",
    "nb_annees_observation",
]

# Largeurs des colonnes
COLUMN_WIDTHS = {
    "nom_vern": Inches(2.2),
    "lb_nom": Inches(2.3),
    "prot_nat": Inches(1.4),
    "lr_france": Inches(0.7),
    "lr_fr_nich": Inches(0.7),
    "lr_fr_hiv": Inches(0.9),
    "lr_fr_migr": Inches(0.9),
    "lr_aura": Inches(0.7),
    "lr_ra": Inches(0.7),
    "lr_auv": Inches(0.7),
    "nb_annees_observation": Inches(0.9),
    "nb_observations": Inches(1.0),
    "derniere_annee_observation": Inches(1.0),
}

# =========================================================
# COULEURS LPO
# =========================================================

LPO_BLUE = "0088CC"
LPO_WHITE = "FFFFFF"
ROW_BORDER = "D9D9D9"
LPO_GREY = "626a6e"
GROUPE_FOND = "D6EAF5"   # ligne d'intertitre d'un groupe (bleu LPO très clair)

# =========================================================
# INSERTION TABLEAU
# =========================================================


def _ligne_groupe(table, groupe, nb):
    """Ligne d'intertitre « Groupe — n espèces » sur toute la largeur, gardée avec l'espèce qui suit."""
    cells = table.add_row().cells
    cell = cells[0].merge(cells[-1])
    cell.text = f"{groupe or 'Autres'} — {nb} espèce{'s' if nb > 1 else ''}"
    set_cell_background(cell, GROUPE_FOND)
    set_cell_font(cell, bold=True, size=10)
    cell.paragraphs[0].paragraph_format.keep_with_next = True


def _entete_repete(row):
    tr_pr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    tr_pr.append(el)


def insert_species_table(document, placeholder, data, par_groupe=True):
    """Tableau des espèces. par_groupe : espèces triées par groupe taxonomique puis par nom (trier_par_groupe), une
    ligne d'intertitre par groupe ; sinon dans l'ordre de data. L'en-tête est répété en haut de chaque page."""
    if par_groupe:
        data = trier_par_groupe(data)
        effectifs = {}
        for item in data:
            effectifs[item.get(CHAMP_GROUPE)] = effectifs.get(item.get(CHAMP_GROUPE), 0) + 1

    for paragraph in document.paragraphs:

        if placeholder not in paragraph.text:
            continue

        paragraph.text = paragraph.text.replace(placeholder, "")

        # =====================================================
        # CREATION TABLE
        # =====================================================

        table = document.add_table(rows=1, cols=len(SPECIES_COLUMNS))

        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False

        # =====================================================
        # HEADER
        # =====================================================

        header_cells = table.rows[0].cells
        _entete_repete(table.rows[0])

        for idx, (field, label) in enumerate(SPECIES_COLUMNS):

            cell = header_cells[idx]

            cell.text = label

            # largeur
            cell.width = COLUMN_WIDTHS[field]

            # style fond
            set_cell_background(cell, LPO_BLUE)

            # texte
            set_cell_text_color(cell, LPO_WHITE)

            # police
            set_cell_font(cell, bold=True, size=10)

            # alignement
            paragraph_header = cell.paragraphs[0]
            paragraph_header.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

        # =====================================================
        # DONNÉES
        # =====================================================

        groupe_courant = object()
        for item in data:

            if par_groupe and item.get(CHAMP_GROUPE) != groupe_courant:
                groupe_courant = item.get(CHAMP_GROUPE)
                _ligne_groupe(table, groupe_courant, effectifs[groupe_courant])

            row_cells = table.add_row().cells

            for idx, (field, _) in enumerate(SPECIES_COLUMNS):

                cell = row_cells[idx]

                value = item.get(field, "")

                # sécurité None
                if value is None:
                    value = ""

                cell.text = str(value)

                # largeur
                cell.width = COLUMN_WIDTHS[field]

                # police générale
                set_cell_font(cell, size=10)

                # centrage
                if field in CENTER_FIELDS:

                    cell.paragraphs[0].alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

                # italique scientifique
                if field in SCIENTIFIC_FIELDS:

                    italicize_cell_species(cell)

                # couleurs statuts
                if field in STATUS_FIELDS:

                    apply_status_style_species(cell, str(value))

        # =====================================================
        # INSERTION
        # =====================================================

        paragraph._element.addnext(table._element)

        break
