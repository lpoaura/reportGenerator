"""Jeu factice du dossier Indicateurs, construit à la main (plan, tâche 3) : les valeurs attendues des tests en
découlent. Quatre aires sur 2023-2025, deux départements, trois observateurs (un par catégorie), un passage sans
observateur et un passage sans durée."""

from datetime import date

import pandas as pd

from reportgenerator.analysis.indicateurs.modele import Jeu, verifier


def _carre(x, y, cote=1000):
    return f"POLYGON(({x} {y},{x + cote} {y},{x + cote} {y + cote},{x} {y + cote},{x} {y}))"


def _rect(x0, y0, x1, y1):
    return f"MULTIPOLYGON((({x0} {y0},{x1} {y0},{x1} {y1},{x0} {y1},{x0} {y0})))"


ZONE_WKT = _rect(900000, 6400000, 960000, 6500000)
DEPARTEMENTS = [
    {"code": "73", "nom": "Savoie", "wkt": _rect(900000, 6450000, 960000, 6500000)},
    {"code": "38", "nom": "Isère", "wkt": _rect(900000, 6400000, 960000, 6450000)},
]

AIRES = [  # id, département, zone biogéographique, commune, x, y, unités
    ("A1", "Savoie", "Zone alpine", "Chambéry", 910000, 6460000, ["U1a", "U1b"]),
    ("A2", "Savoie", "Zone alpine", "Albertville", 930000, 6470000, ["U2a"]),
    ("A3", "Isère", "Zone alpine", "Grenoble", 920000, 6420000, ["U3a"]),
    ("A4", "Isère", "Plaine rhodanienne", "Vienne", 940000, 6410000, ["U4a", "U4b", "U4c", "U4d", "U4e"]),
]
PASSAGES = [  # id, aire, unité, date, données, durée (min), estimée, observateurs
    ("P1", "A1", "U1a", date(2023, 5, 20), 10, 60, False, ["O1"]),
    ("P2", "A3", "U3a", date(2023, 6, 1), 5, 30, False, ["O2"]),
    ("P3", "A1", "U1a", date(2024, 5, 20), 8, 60, False, ["O1"]),
    ("P4", "A2", "U2a", date(2024, 6, 10), 4, 45, False, ["O3"]),
    ("P5", "A3", "U3a", date(2024, 6, 2), 6, 30, False, ["O2"]),
    ("P6", "A1", "U1a", date(2025, 5, 21), 12, 60, False, ["O1", "O2"]),
    ("P7", "A1", "U1b", date(2025, 5, 21), 3, 30, True, ["O1"]),
    ("P8", "A2", "U2a", date(2025, 6, 11), 7, 45, False, ["O3"]),
    ("P9", "A4", "U4a", date(2025, 7, 1), 2, None, False, []),
]
OBSERVATEURS = {  # id -> (id_observateur, nom, organisme, catégorie)
    "O1": ("role:1", "Observateur 1", None, "Bénévole"),
    "O2": ("role:2", "Observateur 2", "LPO Auvergne-Rhône-Alpes", "Salarié LPO"),
    "O3": ("role:3", "Observateur 3", "CEN Savoie", "Organisme tiers"),
}
ESPECES = {1001: "Merle noir", 1002: "Pinson des arbres", 1003: "Rouge-gorge familier"}
OBSERVATIONS = [  # passage, cd_ref, effectif
    ("P3", 1001, 2), ("P4", 1002, 1),
    ("P6", 1001, 3), ("P6", 1002, 2), ("P7", 1001, 1), ("P8", 1002, 4), ("P8", 1003, 1), ("P9", 1001, 2),
]


def jeu_factice(code: str = "stom") -> Jeu:
    aires = pd.DataFrame([
        {"id_aire": a, "nom_aire": a, "wkt": _carre(x, y), "x": x + 500, "y": y + 500, "nb_unites": len(u),
         "commune": com, "departement": dep, "zbiog": zb}
        for a, dep, zb, com, x, y, u in AIRES])
    unites = pd.DataFrame([{"id_unite": u, "id_aire": a, "nom_unite": u} for a, *_, us in AIRES for u in us])
    passages = pd.DataFrame([
        {"id_passage": p, "id_aire": a, "id_unite": u, "date": d, "saison": d.year, "nb_donnees": n,
         "duree_min": duree, "duree_estimee": est}
        for p, a, u, d, n, duree, est, _ in PASSAGES])
    observateurs = pd.DataFrame([
        dict(zip(("id_observateur", "nom", "organisme", "categorie"), OBSERVATEURS[o]), id_passage=p)
        for p, *_, obs in PASSAGES for o in obs])
    observations = pd.DataFrame([{"id_passage": p, "cd_ref": c, "nom": ESPECES[c], "effectif": e}
                                 for p, c, e in OBSERVATIONS])
    return verifier(Jeu(code, aires, unites, passages, observateurs, observations))


def _png(taille=(40, 40)) -> bytes:
    from io import BytesIO

    from PIL import Image
    tampon = BytesIO()
    Image.new("RGB", taille, "white").save(tampon, "PNG")
    return tampon.getvalue()


# PNG valide (rendu QGIS factice)
PNG_1PX = _png()


def rendu_factice(project_path, output_dir, config=None):
    """Remplace le rendu QGIS : un PNG d'un pixel par mise en page du projet."""
    import re
    from pathlib import Path
    texte = Path(project_path).read_text(encoding="utf-8", errors="ignore")
    voulues = (config or {}).get("layouts")   # comme qgis_render : seulement ces mises en page si la liste est donnée
    for nom in re.findall(r'<Layout\b[^>]*\bname="([^"]+)"', texte):
        if voulues is not None and nom not in voulues:
            continue
        (Path(output_dir) / f"{nom}.png").write_bytes(PNG_1PX)
