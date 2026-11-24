"""montage_pages.py <pdf> <out.png> <premiere> <derniere> [dpi] : planche des pages (numéros 1-based), 4 colonnes."""
import io
import sys
try:
    import pymupdf as fitz
except ImportError:  # anciennes versions
    import fitz
from PIL import Image
d = fitz.open(sys.argv[1])
a, b = int(sys.argv[3]), int(sys.argv[4])
dpi = int(sys.argv[5]) if len(sys.argv) > 5 else 40
ims = [Image.open(io.BytesIO(d[i - 1].get_pixmap(dpi=dpi).tobytes("png"))) for i in range(a, b + 1)]
w, h = ims[0].size
cols = 4
rows = (len(ims) + cols - 1) // cols
out = Image.new("RGB", (w * cols, h * rows), "white")
for i, im in enumerate(ims):
    out.paste(im, ((i % cols) * w, (i // cols) * h))
out.save(sys.argv[2])
