"""Graphiques et cartes du rapport PLSOC (matplotlib, charte LPO). Les cartes sont dessinées sans fond de carte
(communes, secteurs, mesures et couples) : version de travail en attendant le projet QGIS du rapport."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from shapely import wkt  # noqa: E402

from reportgenerator.analysis.common.theme import LPO_COLORS, apply_lpo_theme  # noqa: E402

COULEURS_SUCCES = {
    "succes_certain": "#1a9850",
    "succes_probable": "#91cf60",
    "echec_probable": "#fc8d59",
    "echec_certain": "#d73027",
    "autre": "#bdbdbd",
}
COULEURS_STATUT = {"Nicheur certain": "#762a83", "Nicheur probable": "#af8dc3", "Nicheur possible": "#e7d4e8"}


def _fin(fig, path: Path) -> Path:
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def chart_population(serie, path: Path) -> Path:
    apply_lpo_theme()
    annees = [r["annee"] for r in serie]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    w = 0.38
    ax.bar(
        [a - w / 2 for a in annees],
        [r["couples"] for r in serie],
        w,
        label="Couples cantonnés",
        color=LPO_COLORS["blue"],
    )
    ax.bar(
        [a + w / 2 for a in annees], [r["nids"] for r in serie], w, label="Nids / nichées", color=LPO_COLORS["orange"]
    )
    ax.plot(annees, [r["jeunes"] for r in serie], color=LPO_COLORS["green"], marker="o", label="Jeunes à l'envol")
    ax.set_xticks(annees)
    ax.set_xticklabels([str(a) for a in annees], rotation=0)
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    ax.set_ylabel("Effectif")
    return _fin(fig, path)


def chart_succes_historique(serie, path: Path) -> Path:
    apply_lpo_theme()
    annees = [r["annee"] for r in serie if r["nids"]]
    rows = [r for r in serie if r["nids"]]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    bas = [0] * len(rows)
    for code, lib in (
        ("succes_certain", "Succès certain"),
        ("succes_probable", "Succès probable"),
        ("echec_probable", "Échec probable"),
        ("echec_certain", "Échec certain"),
        ("issue_inconnue", "Issue inconnue"),
    ):
        vals = [100 * r[code] / r["nids"] for r in rows]
        ax.bar(annees, vals, 0.7, bottom=bas, label=lib, color=COULEURS_SUCCES.get(code, COULEURS_SUCCES["autre"]))
        bas = [b + v for b, v in zip(bas, vals)]
    ax.set_ylabel("% des nids")
    ax.set_ylim(0, 100)
    ax.set_xticks(annees)
    ax.legend(frameon=False, ncol=5, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    return _fin(fig, path)


def chart_ligne(points, path: Path, ylabel: str, ymax=None) -> Path:
    apply_lpo_theme()
    fig, ax = plt.subplots(figsize=(8, 3.2))
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    ax.plot(xs, ys, marker="o", color=LPO_COLORS["green"])
    for x, y in points:
        ax.annotate(f"{y}", (x, y), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=8)
    ax.set_xticks(xs)
    ax.set_ylabel(ylabel)
    if ymax:
        ax.set_ylim(0, ymax)
    return _fin(fig, path)


def chart_barres(valeurs: dict, path: Path, xlabel="Nombre de couples", couleur=None) -> Path:
    apply_lpo_theme()
    items = list(valeurs.items())[::-1]
    fig, ax = plt.subplots(figsize=(7, 0.45 * max(len(items), 2) + 1))
    ax.barh([k for k, _ in items], [v for _, v in items], color=couleur or LPO_COLORS["blue"])
    for i, (_, v) in enumerate(items):
        ax.text(v, i, f" {v}", va="center", fontsize=9)
    ax.set_xlabel(xlabel)
    return _fin(fig, path)


def chart_phenologie(lignes, annee, path: Path) -> Path:
    apply_lpo_theme()
    fig, ax = plt.subplots(figsize=(9, 3.6))
    x = range(len(lignes))
    ax.bar(x, [r["n"] for r in lignes], color=LPO_COLORS["blue"], label=str(annee))
    if any(r["moyenne"] is not None for r in lignes):
        ax.plot(
            x,
            [r["moyenne"] or 0 for r in lignes],
            color=LPO_COLORS["orange"],
            marker="o",
            ms=3,
            label="Moyenne des années précédentes",
        )
    ax.set_xticks(list(x))
    ax.set_xticklabels([r["decade"] for r in lignes], rotation=70, fontsize=7)
    ax.set_ylabel("Couples présents")
    ax.legend(frameon=False)
    return _fin(fig, path)


def chart_rassemblements(historique: dict, path: Path) -> Path | None:
    series = {s: v for s, v in historique.items() if len(v) >= 2}
    if not series:
        return None
    apply_lpo_theme()
    fig, ax = plt.subplots(figsize=(8, 3.6))
    for site, v in series.items():
        ax.plot(list(v), list(v.values()), marker="o", label=site)
    ax.set_ylabel("Effectif maximal")
    ax.legend(frameon=False, fontsize=8)
    return _fin(fig, path)


# ---------------------------------------------------------------------------------------------------- cartes
def _poly(ax, geom, **kw):
    for g in getattr(geom, "geoms", [geom]):
        if g.geom_type == "Polygon":
            x, y = g.exterior.xy
            if kw.get("facecolor") not in (None, "none"):
                ax.fill(
                    x, y, facecolor=kw["facecolor"], edgecolor="none", alpha=kw.get("alpha", 1), zorder=kw.get("z", 1)
                )
            ax.plot(
                x,
                y,
                color=kw.get("edgecolor", "#333"),
                lw=kw.get("lw", 0.5),
                ls=kw.get("ls", "-"),
                zorder=kw.get("z", 1) + 0.1,
            )
        elif g.geom_type in ("MultiPolygon", "GeometryCollection"):
            _poly(ax, g, **kw)


def carte(
    path: Path,
    zone_wkt,
    communes,
    secteurs,
    mesures,
    couples,
    titre_legende="Couples",
    emprise=None,
    etiquettes_secteurs=True,
) -> Path:
    """Couples de l'année (couleur = statut de nidification), secteurs, mesures, communes, emprise du rapport."""
    apply_lpo_theme()
    zone = wkt.loads(zone_wkt)
    xmin, ymin, xmax, ymax = emprise or zone.bounds
    rapport = (ymax - ymin) / max(xmax - xmin, 1)
    fig, ax = plt.subplots(figsize=(8, max(4, min(11, 8 * rapport))))
    for c in communes:
        _poly(ax, wkt.loads(c["wkt"]), edgecolor="#bdbdbd", lw=0.4)
    for m in mesures:
        _poly(ax, wkt.loads(m["wkt"]), facecolor="#5aae61", edgecolor="#1b7837", lw=0.6, alpha=0.6, z=2)
    for s in secteurs:
        g = wkt.loads(s["wkt"])
        _poly(ax, g, edgecolor="#252525", lw=0.9, ls="--", z=3)
        if etiquettes_secteurs:
            p = g.representative_point()
            if xmin <= p.x <= xmax and ymin <= p.y <= ymax:
                ax.text(
                    p.x,
                    p.y,
                    s["nom_secteur"],
                    fontsize=8,
                    ha="center",
                    weight="bold",
                    zorder=6,
                    bbox={"facecolor": "white", "alpha": 0.7, "edgecolor": "none", "pad": 1},
                )
    _poly(ax, zone, edgecolor="#000000", lw=1.4, z=4)
    for statut, coul in COULEURS_STATUT.items():
        pts = [c for c in couples if c.get("statut_nidification") == statut and c.get("x") is not None]
        taille = 22 if (xmax - xmin) > 20000 else 55  # cartes de détail (secteur, mesure) : points plus gros
        ax.scatter(
            [c["x"] for c in pts], [c["y"] for c in pts], s=taille, c=coul, edgecolors="#333", linewidths=0.5, zorder=5
        )
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    ax.axis("off")
    # échelle
    longueur = 5000 if (xmax - xmin) > 15000 else 1000
    x0, y0 = xmin + (xmax - xmin) * 0.04, ymin + (ymax - ymin) * 0.04
    ax.plot([x0, x0 + longueur], [y0, y0], color="black", lw=2)
    ax.text(x0 + longueur / 2, y0 + (ymax - ymin) * 0.015, f"{longueur // 1000} km", ha="center", fontsize=8)
    legende = [
        Line2D([0], [0], marker="o", ls="", markerfacecolor=c, markeredgecolor="#333", label=s)
        for s, c in COULEURS_STATUT.items()
    ]
    legende += [
        Line2D([0], [0], color="#252525", ls="--", label="Secteur"),
        Line2D(
            [0],
            [0],
            marker="s",
            ls="",
            markerfacecolor="#5aae61",
            markeredgecolor="#1b7837",
            label="Mesure compensatoire",
        ),
        Line2D([0], [0], color="#000000", lw=1.4, label="Emprise du rapport"),
    ]
    ax.legend(handles=legende, loc="upper left", fontsize=7, frameon=True, title=titre_legende, title_fontsize=8)
    return _fin(fig, path)


def emprise_autour(geoms_wkt, marge=0.12, minimum=2500):
    """Rectangle englobant (avec marge) d'une liste de géométries WKT."""
    from shapely.ops import unary_union

    g = unary_union([wkt.loads(w) for w in geoms_wkt if w])
    xmin, ymin, xmax, ymax = g.bounds
    dx, dy = max(xmax - xmin, minimum), max(ymax - ymin, minimum)
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    return (cx - dx * (0.5 + marge), cy - dy * (0.5 + marge), cx + dx * (0.5 + marge), cy + dy * (0.5 + marge))
