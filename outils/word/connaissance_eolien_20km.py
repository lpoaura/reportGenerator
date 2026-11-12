"""Template Word éolien : cartes zoomées sur la zone d'étude et état des connaissances par maille sur les 20 km.

Usage : poetry run python outils/word/connaissance_eolien_20km.py <template.docx> <sortie.docx>
- après {{Carte2_Donnee_disponible}} et {{Carte3_Etat_connaissance_globale}} : leur version zoomée sur la zone
  d'étude ({{Carte2bis_Donnee_zone_etude}}, {{Carte3bis_Etat_connaissance_zone_etude}}), chacune sur sa page ;
- phrase d'annonce des cartes (zoom) ;
- « État des connaissances par maille de 1 km » (textes communs de textes_connaissance.py, adaptés ici pour l'éolien
  seulement) : mailles sur toute l'aire d'étude (20 km = référence locale), donc sans chiffre des espèces à enjeux
  (paragraphe du « rond rouge » retiré, deux questions au lieu de trois) et sans colonnes « emprise » / « part
  locale » dans le tableau (cf. indicateurs.colonnes_synthese).
Refuse un template déjà modifié.
"""
import copy
import sys
from pathlib import Path

from docx import Document

sys.path.insert(0, str(Path(__file__).parent))
import section_docx as sd  # noqa: E402

ZOOMS = {"Carte2_Donnee_disponible": "Carte2bis_Donnee_zone_etude",
         "Carte3_Etat_connaissance_globale": "Carte3bis_Etat_connaissance_zone_etude"}
# (début du paragraphe, ancien passage, nouveau passage) ; None = paragraphe supprimé
TEXTES = [
    ("Les cartes suivantes présentent",
     "Les cartes suivantes présentent la zone d’étude, la répartition générale des données et l’état des "
     "connaissances.",
     "Les cartes suivantes présentent la répartition générale des données et l’état des connaissances sur toute "
     "l’aire d’étude ({{RAYON_MAX_KM}} km), chacune suivie d’un zoom sur la zone d’étude et ses abords immédiats."),
    ("Cette section ne mesure pas",
     "et répondent à trois questions : où a-t-on prospecté ? connaît-on bien chaque groupe à cet endroit ? où se "
     "trouvent les espèces à enjeux ?",
     "et répondent à deux questions : où a-t-on prospecté ? connaît-on bien chaque groupe à cet endroit ? Les "
     "espèces à enjeux sont localisées dans les chapitres suivants."),
    ("Pour chaque groupe taxonomique",
     "le nombre d'espèces connues dans la zone d'étude et dans l'emprise des mailles, et la part qu'elles "
     "représentent des espèces locales ;",
     "le nombre d'espèces connues dans la zone d'étude et le nombre d'espèces locales (les mailles couvrent tout le "
     "rayon de {{POOL_LOCAL_KM}} km) ;"),
    ("Le chiffre dans un rond rouge", None, None),
]

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
doc = Document(src)
assert not any(z in p.text for p in doc.paragraphs for z in ZOOMS.values()), "template déjà modifié"


def para(debut):
    trouves = [p for p in doc.paragraphs if p.text.strip().startswith(debut)]
    assert len(trouves) == 1, f"{debut!r} : {len(trouves)} paragraphe(s)"
    return trouves[0]


for carte, zoom in ZOOMS.items():
    p_carte = para("{{" + carte + "}}")._p
    saut = p_carte.getprevious()        # paragraphe vide avec saut de page, avant chaque carte
    assert saut.find(".//" + sd.W("w:br")) is not None, f"pas de saut de page avant {carte}"
    p_zoom = copy.deepcopy(p_carte)
    sd._set_text(doc, p_zoom, [("{{" + zoom + "}}", False)])
    p_carte.addnext(p_zoom)
    p_carte.addnext(copy.deepcopy(saut))

for debut, ancien, nouveau in TEXTES:
    p = para(debut)
    if ancien is None:
        p._p.getparent().remove(p._p)
        continue
    texte = p.text
    if ancien not in texte:                 # apostrophes typographiques ou droites selon le paragraphe
        ancien, nouveau = ancien.replace("’", "'"), nouveau.replace("’", "'")
    assert texte.count(ancien) == 1, f"passage introuvable dans {debut!r}"
    sd._set_text(doc, p._p, [(texte.replace(ancien, nouveau), False)])

doc.save(dst)
print("template modifié :", dst)
