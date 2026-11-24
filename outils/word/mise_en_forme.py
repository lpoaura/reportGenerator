"""Mise en forme générale d'un template Word : interligne du texte et saut de page avant les grands titres.

Usage : poetry run python outils/word/mise_en_forme.py <template.docx> <sortie.docx> [interligne] [niveaux]
  interligne : 1.15 par défaut (styles « Normal » et « Corps de texte ») ;
  niveaux    : niveaux de titre précédés d'un saut de page, ex. « 1,2 » (défaut : titres X. et X.X).
Le saut de page est réglé sur les paragraphes de titre du template, pas sur les styles : les styles du sommaire
(toc 1...) héritent de « Heading 1 » et prendraient eux aussi le saut de page. Les titres insérés à la génération
(atlas, niveaux 3 et 4) ne sont pas concernés.
"""
import sys

from docx import Document

STYLES_TEXTE = ("Normal", "Body Text")


def appliquer(doc, interligne=1.15, niveaux=(1, 2)):
    """Applique la mise en forme à un document python-docx ; retourne le nombre de titres avec saut de page."""
    for nom in STYLES_TEXTE:
        try:
            doc.styles[nom].paragraph_format.line_spacing = interligne
        except KeyError:
            pass
    styles = {f"Heading {n}" for n in niveaux} | {f"Titre {n}" for n in niveaux}
    titres = [p for p in doc.paragraphs if p.style is not None and p.style.name in styles and p.text.strip()]
    for p in titres:
        p.paragraph_format.page_break_before = True
    return len(titres)


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    interligne = float(sys.argv[3]) if len(sys.argv) > 3 else 1.15
    niveaux = tuple(int(n) for n in sys.argv[4].split(",")) if len(sys.argv) > 4 else (1, 2)
    document = Document(src)
    n = appliquer(document, interligne, niveaux)
    document.save(dst)
    print(f"interligne {interligne:g}, saut de page avant {n} titres (niveaux {niveaux}) -> {dst}")
