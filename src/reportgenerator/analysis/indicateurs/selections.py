"""Règles métier du rapport Indicateurs de biodiversité, écrites une seule fois (conception §5.3, §5.6, §5.11).

Les seuils, périodes et temps sont dans dossier.toml ; ce module contient les règles qui les appliquent.
"""

import fnmatch
from datetime import date
from typing import Iterable

import pandas as pd

PROTOCOLES = ("stoc", "shoc", "stom", "sterf", "pop_reptile", "pop_amphibien")   # ordre du rapport
PREFIXES = {"stoc": "STOC", "shoc": "SHOC", "stom": "STOM", "sterf": "STERF",
            "pop_reptile": "POPR", "pop_amphibien": "POPA"}
CATEGORIES = ("Salarié LPO", "Organisme tiers", "Bénévole", "Non renseigné")      # ordre = priorité

OFB_NOMS = ("ofb", "office français de la biodiversité")


def _vide(organisme: str | None) -> bool:
    return organisme is None or organisme.strip() in ("", "-")


def categorie_observateur(organisme: str | None, email: str | None, connu: bool = True) -> tuple[str, str | None]:
    """(catégorie, organisme affiché). Salarié LPO : organisme « LPO… » ou email contenant « lpo » (certains salariés
    n'ont pas d'adresse LPO) ; OFB reconnu aussi par son adresse ; tout autre organisme = organisme tiers ; aucun
    organisme (ou « - ») = bénévole. Observateur sans compte GeoNature : « Non renseigné »."""
    if not connu:
        return "Non renseigné", None
    org = None if _vide(organisme) else organisme.strip()
    mail = (email or "").lower()
    if (org and org.lower().startswith("lpo")) or "lpo" in mail:
        return "Salarié LPO", org or "LPO"
    if mail.endswith("@ofb.gouv.fr") or (org and any(n in org.lower() for n in OFB_NOMS)):
        return "Organisme tiers", "OFB"
    if org:
        return "Organisme tiers", org
    return "Bénévole", None


def categorie_prioritaire(categories: Iterable[str]) -> str:
    """Catégorie la plus prioritaire (Salarié LPO > Organisme tiers > Bénévole) ; aucune = « Non renseigné »."""
    presentes = [c for c in categories if c in CATEGORIES]
    return min(presentes, key=CATEGORIES.index) if presentes else "Non renseigné"


def saison(d: date, mode: str) -> int:
    """Saison d'un passage : année civile, ou pour l'hiver (SHOC) l'année du mois de janvier (déc. 2024 et
    janv. 2025 = saison 2025, affichée « 2024-2025 »)."""
    if mode == "hiver":
        return d.year + 1 if d.month >= 7 else d.year
    return d.year


def libelle_saison(s: int, mode: str) -> str:
    return f"{s - 1}-{s}" if mode == "hiver" else str(s)


def annee_par_defaut(aujourdhui: date, fin_saison: str = "10-01") -> int:
    """Dernière saison terminée : l'année en cours à partir de fin_saison (« MM-JJ »), sinon l'année précédente."""
    return aujourdhui.year if aujourdhui.strftime("%m-%d") >= fin_saison else aujourdhui.year - 1


def dans_periode(d: date, periode: list[str]) -> bool:
    """periode = [« MM-JJ » début, « MM-JJ » fin], bornes comprises, dans une même année civile."""
    return periode[0] <= d.strftime("%m-%d") <= periode[1]


def numero_periode(d: date, periodes: list[list[str]]) -> int | None:
    """Numéro (à partir de 1) de la période qui contient la date, sinon None."""
    return next((i for i, p in enumerate(periodes, 1) if dans_periode(d, p)), None)


def est_stoc_site_n2000(nom_site: str | None, motif: str) -> bool:
    """STOC-site Natura 2000 de la LPO : nom reconnu par le motif façon ILIKE (« STOC N2000% »)."""
    if not nom_site:
        return False
    return fnmatch.fnmatchcase(nom_site.lower(), motif.lower().replace("%", "*").replace("_", "?"))


def completer_durees(passages: pd.DataFrame, duree_defaut_min: float | None = None) -> pd.DataFrame:
    """Durée manquante : duree_defaut_min s'il est donné (STERF : 1 h par transect), sinon la moyenne des durées
    connues de la même saison ; la durée complétée est marquée comme estimée."""
    p = passages.copy()
    p["duree_min"] = p["duree_min"].astype(float)
    manquantes = p["duree_min"].isna()
    if duree_defaut_min is not None:
        remplace = pd.Series(float(duree_defaut_min), index=p.index)
    else:
        remplace = p.groupby("saison")["duree_min"].transform("mean")
    p.loc[manquantes, "duree_min"] = remplace[manquantes]
    p["duree_estimee"] = p["duree_estimee"].astype(bool) | (manquantes & p["duree_min"].notna())
    return p
