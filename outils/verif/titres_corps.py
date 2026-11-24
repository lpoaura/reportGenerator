"""titres_corps.py <rapport.pdf> : numéros des titres dans le corps du rapport (après le sommaire), pour vérifier
la numérotation (ex. « 4.1 » sous le chapitre 4). PDF exporté par Word (verif/word_update.ps1)."""
import re
import sys

try:
    import pymupdf as fitz
except ImportError:  # anciennes versions
    import fitz

d = fitz.open(sys.argv[1])
for i, page in enumerate(d):
    if i < 4:
        continue
    lignes = [t.strip() for t in page.get_text().splitlines() if t.strip()]
    for j, s in enumerate(lignes):
        if re.fullmatch(r"\d+(\.\d+)*\.", s) and j + 1 < len(lignes):
            print(i + 1, s, lignes[j + 1][:50])
