"""crop_legendes.py <dossier maps> <sortie.png> <carte>... : bandeau du titre et bandeau de légende de chaque carte,
empilés (contrôle des chevauchements titre / légende / échelle)."""
import sys
from pathlib import Path

from PIL import Image

dossier, noms = Path(sys.argv[1]), sys.argv[3:]
ims = []
for n in noms:
    im = Image.open(dossier / f"{n}.png").convert("RGB")
    w, h = im.size
    ims.append(im.crop((0, 0, w, int(h * 0.1))))
    ims.append(im.crop((0, int(h * 0.81), w, h)))
out = Image.new("RGB", (max(i.size[0] for i in ims), sum(i.size[1] for i in ims)), "white")
y = 0
for i in ims:
    out.paste(i, (0, y))
    y += i.size[1]
out.save(sys.argv[2])
