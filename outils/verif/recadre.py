"""recadre.py <image.png> <sortie.png> <x0> <y0> <x1> <y1> : extrait une zone (fractions 0-1 de la largeur et de la
hauteur), pour regarder un détail en pleine résolution (contours, étiquettes)."""
import sys

from PIL import Image

im = Image.open(sys.argv[1])
w, h = im.size
x0, y0, x1, y1 = (float(v) for v in sys.argv[3:7])
im.crop((int(w * x0), int(h * y0), int(w * x1), int(h * y1))).save(sys.argv[2])
