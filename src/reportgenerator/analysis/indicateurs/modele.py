"""Modèle commun à tous les protocoles du rapport Indicateurs de biodiversité (conception §5.1).

Aire (carré, site, aire POP) > unité (point, transect, mare) > passage > observateurs et observations. Chaque
adaptateur range sa source dans un `Jeu` ; les analyses communes ne lisent que ce modèle.
"""

from dataclasses import dataclass, field

import pandas as pd

COLONNES = {
    "aires": ["id_aire", "nom_aire", "wkt", "x", "y", "nb_unites", "commune", "departement", "zbiog"],
    "unites": ["id_unite", "id_aire", "nom_unite"],
    "passages": ["id_passage", "id_aire", "id_unite", "date", "saison", "nb_donnees", "duree_min", "duree_estimee"],
    "observateurs": ["id_passage", "id_observateur", "nom", "organisme", "categorie"],
    "observations": ["id_passage", "cd_ref", "nom", "effectif"],
    "etats": ["id_aire", "saison", "etat"],
}


@dataclass
class Jeu:
    code: str                                   # "stoc", "shoc", "stom", "sterf", "pop_reptile", ...
    aires: pd.DataFrame
    unites: pd.DataFrame
    passages: pd.DataFrame                      # date : datetime.date ; saison : int
    observateurs: pd.DataFrame
    observations: pd.DataFrame                  # seulement les saisons de la fenêtre des espèces
    etats: pd.DataFrame | None = None           # état d'aire fourni par la base (POP)
    anomalies: list[dict] = field(default_factory=list)   # {code, libelle, aire, unite, date, nom}


def table_vide(nom: str) -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=object) for c in COLONNES[nom]})


def jeu_vide(code: str) -> Jeu:
    return Jeu(code, *(table_vide(n) for n in ("aires", "unites", "passages", "observateurs", "observations")))


def verifier(jeu: Jeu) -> Jeu:
    """ValueError si une table du jeu n'a pas les colonnes du modèle."""
    for nom, colonnes in COLONNES.items():
        table = getattr(jeu, nom)
        if table is None:
            continue
        manquantes = [c for c in colonnes if c not in table.columns]
        if manquantes:
            raise ValueError(f"Jeu {jeu.code} : colonnes absentes de {nom} : {', '.join(manquantes)}")
    return jeu
