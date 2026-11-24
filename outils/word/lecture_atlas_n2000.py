"""Template Natura 2000 : paragraphe {{TEXTE_LECTURE_ATLAS}} (lecture des cartes de l'atlas et de la page qui suit
chaque carte), inséré après la présentation de l'atlas des espèces. Le texte est produit à la génération à partir des
paramètres du dossier (brique n2000_atlas, tables.texte_lecture_atlas).

Usage : poetry run python outils/word/lecture_atlas_n2000.py <template.docx> <sortie.docx>
  Idempotent (rien n'est fait si le placeholder est déjà présent).
"""
import sys
from pathlib import Path

from docx import Document

sys.path.insert(0, str(Path(__file__).parent))
import section_docx as sd  # noqa: E402

PLACEHOLDER = "{{TEXTE_LECTURE_ATLAS}}"
REPERE = "chaque espèce fait l'objet d'une carte de localisation des données"


def inserer(doc) -> bool:
    if any(PLACEHOLDER in p.text for p in doc.paragraphs):
        return False
    ref = next(p for p in doc.paragraphs if REPERE in p.text)
    sd.nouveau(doc, ref._p, ref._p, [(PLACEHOLDER, False)])
    return True


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    document = Document(src)
    print("paragraphe inséré" if inserer(document) else "déjà présent", "->", dst)
    document.save(dst)
