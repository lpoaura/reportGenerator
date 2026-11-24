"""Compléments déduits automatiquement quand l'information n'est pas saisie (années Mergin, en attente des compléments
experts du projet QGIS). Chaque valeur déduite est marquée (milieu_deduit, lieu_dit_deduit) et signalée dans le rapport.

- milieu : couple dans une mesure compensatoire → « parcelle_compensatoire » ; dans une parcelle agricole suivie
  (Mergin) → « agricole » ; sinon inconnu. Règle vérifiée sur 2024 : 38 couples agricoles sur 38 et 12 couples en
  mesure sur 12 retrouvés, 2 couples de carrière classés à tort en agricole.
- culture : type de végétation du relevé de parcelle de l'année le plus proche de la date d'installation du couple.
- lieu-dit : lieu-dit VisioNature / Faune-France le plus proche (à moins de distance_max m) ; 47 lieux-dits 2024 sur
  93 identiques au lieu-dit saisi, les autres sont des noms voisins : à vérifier.
"""

from shapely import STRtree, wkt
from shapely.geometry import Point


def _arbre(geoms):
    return STRtree(geoms) if geoms else None


def deduire(couples, nids, parcelles, suivis, lieux, distance_max=1000):
    """Complète en place couples (milieu, culture, lieu_dit) et nids (milieu, agricole). Retourne les compteurs."""
    g_parc = [wkt.loads(p["wkt"]) for p in parcelles if p.get("wkt")]
    t_parc = _arbre(g_parc)
    g_suivi = [wkt.loads(s["wkt"]) for s in suivis if s.get("wkt")]
    suivis_ok = [s for s in suivis if s.get("wkt")]
    t_suivi = _arbre(g_suivi)
    pts_lieux = [Point(lx["x"], lx["y"]) for lx in lieux]
    t_lieux = _arbre(pts_lieux)
    stats = {"milieu": 0, "culture": 0, "lieu_dit": 0}

    for c in couples:
        c.setdefault("milieu_deduit", False)
        c.setdefault("lieu_dit_deduit", False)
        if c.get("x") is None:
            continue
        p = Point(c["x"], c["y"])
        if not c.get("milieu"):
            if c.get("id_mesure_compensatoire"):
                c["milieu"], c["milieu_deduit"] = "parcelle_compensatoire", True
            elif t_parc is not None and any(g_parc[i].intersects(p) for i in t_parc.query(p)):
                c["milieu"], c["milieu_deduit"] = "agricole", True
            if c["milieu_deduit"]:
                stats["milieu"] += 1
        if c.get("milieu") == "agricole" and not c.get("culture") and t_suivi is not None:
            cand = [
                suivis_ok[i]
                for i in t_suivi.query(p)
                if g_suivi[i].intersects(p) and suivis_ok[i].get("type_vegetation")
            ]
            ref = c.get("date_premiere_obs")
            if cand:
                choix = min(
                    cand, key=lambda s: abs((s["date_suivi"] - ref).days) if (ref and s.get("date_suivi")) else 0
                )
                c["culture"] = choix["type_vegetation"]
                stats["culture"] += 1
        if not c.get("lieu_dit") and t_lieux is not None:
            i = t_lieux.nearest(p)
            if i is not None and pts_lieux[i].distance(p) <= distance_max:
                c["lieu_dit"], c["lieu_dit_deduit"] = lieux[i]["nom"], True
                stats["lieu_dit"] += 1

    par_cle = {c["cle_couple"]: c for c in couples}
    for n in nids:
        c = par_cle.get(n.get("cle_couple"))
        if c and not n.get("milieu") and c.get("milieu"):
            n["milieu"] = c["milieu"]
        n["agricole"] = n.get("milieu") == "agricole"
    return stats
