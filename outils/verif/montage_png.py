"""montage_png.py <dossier> <out.png> <nom1> <nom2> ... : planche 4 colonnes des PNG (sans extension)."""
import sys
from pathlib import Path
from PIL import Image
d = Path(sys.argv[1])
ims = [Image.open(d / f"{n}.png").convert("RGB") for n in sys.argv[3:]]
w, h = 420, int(420 * ims[0].size[1] / ims[0].size[0])
cols = 4
rows = (len(ims) + cols - 1) // cols
out = Image.new("RGB", (w * cols, h * rows), "white")
for i, im in enumerate(ims):
    out.paste(im.resize((w, h)), ((i % cols) * w, (i // cols) * h))
out.save(sys.argv[2])
