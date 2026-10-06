"""
Chiroptères du dossier éolien : vulnérabilité par espèce et mises en forme
(sans base de données : testable).

Méthode (document « partie chiroptères », d'après le SRE, Le Bret et Letscher 2010) :
  NP  note patrimoniale = note liste rouge AuRA (CR 6 … LC/NA 1) + 4 si annexe II DHFF
  NE  note éolien  = arrondi((2 × NSE + NP) / 3)   NSE : sensibilité directe à l'éolien
  NH  note habitat = arrondi((2 × NHab + NP) / 3)  NHab : sensibilité à la perte d'habitat
NSE, NHab et la distance d'influence autour des gîtes sont dans ref_chiropteres.csv.
"""

import csv
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from reportgenerator.analysis.eolien.tables import ALL, _max, phrases_anneaux

LR_NOTES = {"CR": 6, "EN": 5, "VU": 4, "DD": 3, "NT": 2, "LC": 1, "NA": 1}
DHFF_ANNEXE_II = 4
CLASS_SCORES = {"Faible": 1, "Moyenne": 2, "Forte": 3, "Très forte": 4}
ESPECE_RANGS = ("ES", "SSES")

GENRES_GROUPES = {
    "Pipistrellus": "pipistrelles",
    "Nyctalus": "noctules",
    "Eptesicus": "serotines_vespere",
    "Vespertilio": "serotines_vespere",
    "Hypsugo": "serotines_vespere",
    "Myotis": "murins",
    "Rhinolophus": "rhinolophes",
    "Plecotus": "oreillards",
}

PERIODES = ["Transit printanier", "Estivage", "Transit automnal", "Hivernant"]


def _int_or_none(value):
    return int(value) if value not in (None, "") else None


def load_referentiel(path: Path) -> dict[int, dict]:
    """ref_chiropteres.csv -> {cd_ref: {lb_nom, nom_vern, nse, nhab, dist_gite_m}}."""
    with Path(path).open(encoding="utf-8") as f:
        return {
            int(row["cd_ref"]): {
                "lb_nom": row["lb_nom"],
                "nom_vern": row["nom_vern"],
                "nse": _int_or_none(row["nse"]),
                "nhab": _int_or_none(row["nhab"]),
                "dist_gite_m": _int_or_none(row["dist_gite_m"]),
            }
            for row in csv.DictReader(f, delimiter=";")
        }


def _round(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def note_patrimoniale(lr_aura, n2k) -> int:
    """LR AuRA (CR 6, EN 5, VU 4, DD 3, NT 2, LC/NA 1, absente 1) + 4 si annexe II DHFF."""
    code = re.sub(r"[^A-Z]", "", str(lr_aura or "").upper())[:2]
    note_lr = LR_NOTES.get(code, 1)
    annexe_ii = bool(re.search(r"\bII\b", str(n2k or "")))
    return note_lr + (DHFF_ANNEXE_II if annexe_ii else 0)


def classe(note, seuils) -> str:
    """seuils : [[10, "Très forte"], [7, "Forte"], [5, "Moyenne"]] -> sinon "Faible"."""
    if note is None:
        return ""
    for minimum, libelle in sorted(seuils, key=lambda s: -s[0]):
        if note >= minimum:
            return libelle
    return "Faible"


def vulnerabilite(sp: dict, referentiel: dict, seuils_ne, seuils_nh) -> dict:
    """Ajoute np, ne, nh et leurs classes à une ligne espèce (clés cd_ref, lr_aura, n2k)."""
    ref = referentiel.get(sp.get("cd_ref"), {})
    np_ = note_patrimoniale(sp.get("lr_aura"), sp.get("n2k"))
    ne = _round((2 * ref["nse"] + np_) / 3) if ref.get("nse") is not None else None
    nh = _round((2 * ref["nhab"] + np_) / 3) if ref.get("nhab") is not None else None
    ne_classe = classe(ne, seuils_ne)
    return {
        **sp,
        "np": np_,
        "nse": ref.get("nse"),
        "nhab": ref.get("nhab"),
        "ne": ne,
        "ne_classe": ne_classe,
        "ne_score": CLASS_SCORES.get(ne_classe, 0),
        "nh": nh,
        "nh_classe": classe(nh, seuils_nh),
        "dhff_ii": "Oui" if re.search(r"\bII\b", str(sp.get("n2k") or "")) else "",
        "dist_gite_m": ref.get("dist_gite_m"),
    }


def est_espece(sp: dict) -> bool:
    return sp.get("id_rang") in ESPECE_RANGS


def groupe(lb_nom: str | None) -> str:
    genre = (lb_nom or "").split(" ")[0]
    return GENRES_GROUPES.get(genre, "autres")


def tri_vulnerabilite(species):
    return sorted(species, key=lambda sp: (-(sp.get("ne") or 0), -(sp.get("nh") or 0), sp.get("nom_vern") or ""))


def liste_vulnerables(species, cle_classe: str, classes=("Très forte", "Forte")) -> str:
    """« Minioptère de Schreibers (très forte), Petit Murin (forte) » ou « aucune »."""
    retenues = [sp for sp in tri_vulnerabilite(species) if sp.get(cle_classe) in classes]
    if not retenues:
        return "aucune"
    return ", ".join(f"{sp['nom_vern']} ({sp[cle_classe].lower()})" for sp in retenues)


def _fmt(n) -> str:
    return f"{n:,}".replace(",", " ")


def texte_connaissance_chiro(resume: list[dict], anneaux_km, nb_non_especes: int, nb_contacts: int = 0) -> str:
    """resume est compté en observations (un taxon, un jour, un lieu) ; nb_contacts = données brutes."""
    par_anneau = {ligne["anneau"]: ligne for ligne in resume}
    total = par_anneau[ALL]
    phrases = [
        f"Les bases de données (VisioNature, DBchiro et partenaires) font état de {_fmt(nb_contacts)} "
        f"données de chiroptères dans un rayon de {max(anneaux_km):g} km autour de la zone du projet, "
        f"soit {_fmt(total['nb_obs'])} observations distinctes (un taxon, un jour, un lieu), concernant "
        f"{total['nb_especes']} espèces. Les suivis acoustiques produisent de nombreux contacts répétés au "
        f"même endroit : c'est le nombre d'observations qui est utilisé dans la suite de ce chapitre."
    ]
    if nb_non_especes:
        phrases.append(
            f"{_fmt(nb_non_especes)} observations ne sont pas précisées à l'espèce "
            f"(complexes d'espèces ou genres)."
        )
    phrases += phrases_anneaux(par_anneau, anneaux_km, "contactées", "observations", unite_anneaux="observation")
    return " ".join(phrases)


def pivot_gites(rows) -> list[dict]:
    """Lignes (taxon, type de gîte, anneau) -> une ligne par taxon et type de gîte."""
    out: dict = {}
    for row in rows:
        key = (row["cd_ref"], row["type_gite"])
        item = out.get(key)
        if item is None:
            item = {k: row.get(k) for k in ("cd_ref", "nom_vern", "lb_nom", "id_rang", "type_gite")}
            item.update({f"nb_sites__{ALL}": 0, f"derniere_annee__{ALL}": None, "effectif_max": None})
            out[key] = item
        i = row["anneau_ordre"]
        item[f"nb_sites__{i}"] = row["nb_sites"]
        item[f"derniere_annee__{i}"] = row["derniere_annee"]
        item[f"nb_sites__{ALL}"] += row["nb_sites"] or 0
        item[f"derniere_annee__{ALL}"] = _max(item[f"derniere_annee__{ALL}"], row["derniere_annee"])
        item["effectif_max"] = _max(item["effectif_max"], row["effectif_max"])
    return sorted(
        out.values(),
        key=lambda r: (r["type_gite"] != "Colonie de reproduction", -r[f"nb_sites__{ALL}"], r["nom_vern"] or ""),
    )


def texte_gites(resume_gites: dict, gites: list[dict], rayon_km) -> str:
    """Phrase de synthèse des colonies et gîtes connus (resume_gites : nb_colonies, nb_gites,
    annee_min_colonies, annee_max_colonies)."""
    colonies = [g for g in gites if g["type_gite"] == "Colonie de reproduction"]
    if not resume_gites.get("nb_colonies"):
        phrase = f"Aucune colonie de reproduction n'est connue dans un rayon de {rayon_km:g} km."
    elif resume_gites["nb_colonies"] == 1:
        detail = ", ".join(g["nom_vern"] for g in colonies)
        phrase = (f"1 site de colonie de reproduction est connu dans un rayon de {rayon_km:g} km ({detail}), "
                  f"observé en {resume_gites['annee_max_colonies']}.")
    else:
        detail = ", ".join(f"{g['nom_vern']} ({g[f'nb_sites__{ALL}']})" for g in colonies)
        phrase = (
            f"{resume_gites['nb_colonies']} sites de colonies de reproduction sont connus dans un rayon de "
            f"{rayon_km:g} km : {detail}. Ces données datent de {resume_gites['annee_min_colonies']} "
            f"à {resume_gites['annee_max_colonies']}."
        )
    nb_gites = resume_gites.get("nb_gites") or 0
    if nb_gites == 0:
        phrase += " Aucun gîte hors reproduction n'est connu."
    elif nb_gites == 1:
        phrase += " 1 site de gîte hors reproduction est connu."
    else:
        phrase += f" {nb_gites} sites de gîte hors reproduction sont connus."
    return phrase


def resume_periodes(rows) -> list[dict]:
    """Lignes (periode, nb_donnees, nb_especes, nb_non_especes, principales) dans l'ordre du cycle."""
    par_periode = {r["periode"]: r for r in rows}
    ordre = PERIODES + sorted(p for p in par_periode if p not in PERIODES)
    return [par_periode[p] for p in ordre if p in par_periode]
