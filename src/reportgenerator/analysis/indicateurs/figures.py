"""Graphiques du rapport Indicateurs (matplotlib, charte LPO). Les cartes passent par le projet QGIS du dossier."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

from reportgenerator.analysis.common.theme import LPO_COLORS, apply_lpo_theme  # noqa: E402
from reportgenerator.analysis.indicateurs.selections import CATEGORIES  # noqa: E402
from reportgenerator.analysis.indicateurs.textes import pluriel  # noqa: E402

COULEURS_CATEGORIES = {
    "Salarié LPO": LPO_COLORS["blue"],
    "Organisme tiers": LPO_COLORS["green"],
    "Bénévole": LPO_COLORS["orange"],
    "Non renseigné": "#bdbdbd",
}


def _fin(fig, path: Path) -> Path:
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return Path(path)


def _axe_saisons(ax, saisons):
    ax.set_xticks(saisons)
    ax.set_xticklabels([str(s) for s in saisons], rotation=45 if len(saisons) > 8 else 0)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.grid(axis="y")


def chart_aires(serie: list[dict], path: Path, label_aire: str) -> Path:
    """Aires suivies par saison depuis le début de la série."""
    apply_lpo_theme()
    saisons = [r["saison"] for r in serie]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    barres = ax.bar(saisons, [r["aires"] for r in serie], color=LPO_COLORS["blue"])
    ax.bar_label(barres, fontsize=8)
    ax.set_ylabel(f"{pluriel(label_aire)} suivi(e)s".capitalize())
    _axe_saisons(ax, saisons)
    return _fin(fig, path)


def chart_observateurs(series_cat: list[dict], path: Path) -> Path:
    """Observateurs (comptes) par catégorie et par saison, en barres empilées."""
    apply_lpo_theme()
    saisons = [r["saison"] for r in series_cat]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    bas = [0] * len(saisons)
    for c in CATEGORIES:
        valeurs = [r.get(c, 0) for r in series_cat]
        if not any(valeurs):
            continue
        ax.bar(saisons, valeurs, bottom=bas, color=COULEURS_CATEGORIES[c], label=c)
        bas = [b + v for b, v in zip(bas, valeurs)]
    ax.set_ylabel("Observateurs")
    if any(bas):
        ax.legend(frameon=False, ncols=4, loc="upper left", bbox_to_anchor=(0, -0.18))
    _axe_saisons(ax, saisons)
    return _fin(fig, path)
