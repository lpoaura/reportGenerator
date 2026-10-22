"""Copie un projet QGIS construit hors du dépôt vers le dépôt, sans chemin vers le dossier de construction.

Usage : poetry run python outils/qgis/integrer_projet.py <projet_construit.qgs> <destination.qgs>
  Sources « <dossier de construction>/data/<couche>.gpkg » (absolues ou relatives) -> ./data/<couche>.gpkg.
  Refuse d'écrire s'il reste un chemin vers le dossier de construction ou un dossier temporaire.
  Copie aussi <projet>_attachments.zip.
"""
import re
import shutil
import sys
from pathlib import Path

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
s = src.read_text(encoding="utf-8")
build = src.parent.name
# chemins absolus (C:/.../<build>/data/) ou relatifs (../<build>/data/) ; ./data/ déjà bon
s, n = re.subn(r'[^"<>|=]*?[/\\]' + re.escape(build) + r'[/\\]data[/\\]', "./data/", s)
dossiers = [src.parent.resolve().as_posix(), src.parent.as_posix(), "AppData/Local/Temp", "/tmp/"]
restes = sorted({m for d in dossiers for m in re.findall(r"[^\"<>|=]{0,60}" + re.escape(d) + r"[^\"<>|]{0,60}", s)})
assert not restes, f"chemins vers le dossier de construction restants : {restes}"
dst.write_text(s, encoding="utf-8")
att = src.with_name(src.stem + "_attachments.zip")
if att.exists():
    shutil.copy2(att, dst.with_name(dst.stem + "_attachments.zip"))
print(f"{n} chemins réécrits -> {dst}")
print("sources ./data :", sorted(set(re.findall(r"\./data/([A-Za-z0-9_]+)\.gpkg", s))))
