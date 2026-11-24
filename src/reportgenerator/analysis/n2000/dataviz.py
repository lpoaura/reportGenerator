"""Graphiques du dossier Natura 2000."""

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from reportgenerator.analysis.common.theme import apply_lpo_theme

# couleurs des types de donnée : les mêmes que sur les cartes de l'atlas (outils/qgis/atlas_n2000_temporalite.py)
COULEURS_TYPES = {"Nicheur certain": "#e31a1c", "Nicheur probable": "#fd8d3c", "Nicheur possible": "#fecc5c",
                  "Autres données": "#2b8cbe"}
NIDIFICATION = ("Nicheur certain", "Nicheur probable", "Nicheur possible")   # du plus haut au plus bas


def graphique_fiche(fiche: dict, output_path) -> None:
    """Données par année de la fiche d'une espèce (tables.fiche_espece) : barres empilées par type de donnée (nicheur
    certain en bas, autres données en haut), total au-dessus de chaque barre. Oiseaux : point au sommet de la barre,
    de la couleur du niveau de nidification maximal de l'année (les données de nidification, peu nombreuses, sont
    souvent invisibles dans la barre). Un seul type (autres groupes) : barres simples « Données »."""
    apply_lpo_theme()
    annees, series = fiche["annees"], fiche["series"]
    fig, ax = plt.subplots(figsize=(6.3, 2.6))
    x = range(len(annees))
    bas = [0] * len(annees)
    seul = len(series) == 1
    for type_donnee, valeurs in series.items():
        ax.bar(x, valeurs, bottom=bas, width=0.65, color=COULEURS_TYPES.get(type_donnee, "#999999"),
               edgecolor="white", linewidth=0.4, label="Données" if seul else type_donnee)
        bas = [b + v for b, v in zip(bas, valeurs)]
    haut = max(bas, default=0) or 1
    # niveau de nidification maximal de chaque année : point au sommet de la barre
    niveaux = [next((ty for ty in NIDIFICATION if series.get(ty, [0] * len(annees))[i]), None)
               for i in range(len(annees))]
    for i, (total, niveau) in enumerate(zip(bas, niveaux)):
        y = total + haut * 0.05
        if niveau:
            ax.scatter(i, y, s=38, color=COULEURS_TYPES[niveau], edgecolor="#555555", linewidth=0.5, zorder=3)
        if total:
            ax.text(i, y + haut * (0.06 if niveau else -0.03), str(total), ha="center", va="bottom", fontsize=7)
    ax.set_xticks(list(x), [str(a) for a in annees], fontsize=8)
    ax.tick_params(axis="y", labelsize=8)
    ax.set_ylabel("Nombre de données", fontsize=8)
    ax.set_ylim(0, haut * 1.28)
    ax.grid(True, axis="y")
    ax.set_axisbelow(True)
    if not seul:
        poignees, libelles = ax.get_legend_handles_labels()
        if any(niveaux):
            poignees.append(Line2D([], [], marker="o", linestyle="", markersize=6, markerfacecolor="white",
                                   markeredgecolor="#555555"))
            libelles.append("Point : nidification maximale de l'année")
        ax.legend(poignees, libelles, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=3, fontsize=7,
                  frameon=False)
    plt.savefig(output_path, dpi=200)
    plt.close(fig)
