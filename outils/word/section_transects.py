"""Templates générique, éolien et Natura 2000 : phrase de méthode {{TEXTE_GEOMETRIES}} et section « Transects et
placettes de suivi » (brique commune geometries, carte Carte_transects du projet QGIS).

Usage : poetry run python outils/word/section_transects.py <template.docx> <sortie.docx>
  - {{TEXTE_GEOMETRIES}} après le paragraphe des données prises en compte (générique, éolien) ou après
    {{TEXTE_RAYONS}} (Natura 2000) ;
  - section {{#geometries}} ... {{/geometries}} (retirée à la génération sans transect ni placette) après le
    commentaire de l'expert de l'état des connaissances par maille : intertitre, texte, carte, tableau, commentaire.
  Mise en forme copiée des paragraphes de la section « état des connaissances » (intertitre en gras, carte, texte
  surligné). Idempotent (rien n'est fait si les placeholders sont déjà présents).
"""
import sys
from pathlib import Path

from docx import Document

sys.path.insert(0, str(Path(__file__).parent))
import section_docx as sd  # noqa: E402

REPERES_METHODE = ("{{TEXTE_RAYONS}}", "La présente synthèse provient des bases de données VisioNature")
REPERE_SECTION = "[Commentaire de l'expert : groupes et secteurs les moins connus"
TEXTE = ("Certaines données sont localisées par une ligne (transect d'un protocole de suivi : STERF pour les papillons "
         "de jour, POPReptile pour les reptiles...) ou par un petit polygone (placette, site). La carte suivante les "
         "représente, colorées par protocole ou par source ; le tableau détaille, pour chaque jeu de données, le "
         "nombre d'objets (transects ou placettes), de données et d'espèces. Ces données sont comptées dans les "
         "analyses du rapport à leur point central.")
COMMENTAIRE = "[Commentaire de l'expert : apport des protocoles de suivi, secteurs suivis, évolutions notables.]"


def _paragraphe(doc, debut):
    return next(p for p in doc.paragraphs if p.text.strip().startswith(debut) or debut in p.text)


def inserer(doc) -> list[str]:
    fait = []
    textes = [p.text for p in doc.paragraphs]
    if not any("{{TEXTE_GEOMETRIES}}" in t for t in textes):
        ref = next(p for r in REPERES_METHODE for p in doc.paragraphs if r in p.text)
        sd.nouveau(doc, ref._p, ref._p, [("{{TEXTE_GEOMETRIES}}", False)])   # mise en forme du repère (Normal)
        fait.append("TEXTE_GEOMETRIES")
    if not any("{{#geometries}}" in t for t in textes):
        ref = _paragraphe(doc, REPERE_SECTION)
        texte = _paragraphe(doc, "Cette section ne mesure pas la biodiversité")._p
        titre = _paragraphe(doc, "Où a-t-on prospecté ?")._p
        carte = _paragraphe(doc, "{{Connaissance_effort_donnees}}")._p
        el = ref._p
        for modele, parts in [(texte, [("{{#geometries}}", False)]),
                              (titre, [("Transects et placettes de suivi", False)]),
                              (texte, [(TEXTE, False)]),
                              (carte, [("{{Carte_transects}}", False)]),
                              (texte, [("Tableau : données localisées par une ligne ou un polygone, par protocole "
                                        "et jeu de données.", False)]),
                              (texte, [("{{TABLE_GEOMETRIES}}", False)]),
                              (ref._p, [(COMMENTAIRE, True)]),
                              (texte, [("{{/geometries}}", False)])]:
            el = sd.nouveau(doc, el, modele, parts)
        fait.append("section geometries")
    return fait


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    document = Document(src)
    print(inserer(document) or "déjà présent", "->", dst)
    document.save(dst)
