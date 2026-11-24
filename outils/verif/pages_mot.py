"""pages_mot.py <pdf> <mot>... : pages contenant chaque mot (texte du PDF)."""
import sys
try:
    import pymupdf as fitz
except ImportError:  # anciennes versions
    import fitz
d = fitz.open(sys.argv[1])
for mot in sys.argv[2:]:
    print(mot, [i + 1 for i, p in enumerate(d) if mot in p.get_text()])
