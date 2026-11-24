"""Graphiques du dossier éolien."""

import matplotlib.pyplot as plt

from reportgenerator.analysis.common.theme import apply_lpo_theme
from reportgenerator.analysis.eolien.vulnerabilite import couleur, fmt_note

GRIS = "#C8C8C8"


def histogramme_vulnerabilite(data: list[dict], output_path: str):
    """Nombre d'espèces par valeur d'indice de vulnérabilité (data : vulnerabilite.histogramme),
    barres colorées comme les cellules des tableaux (gris sous 2,5)."""
    apply_lpo_theme()
    valeurs = [row["vulnerabilite"] for row in data]
    nombres = [row["nb_especes"] for row in data]
    couleurs = [f"#{couleur(v)}" if couleur(v) else GRIS for v in valeurs]

    fig, ax = plt.subplots(figsize=(9, 4.5))
    bars = ax.bar([fmt_note(v) for v in valeurs], nombres, color=couleurs, edgecolor="#8C8C8C", linewidth=0.5)
    ax.set_xlabel("Indice de vulnérabilité")
    ax.set_ylabel("Nombre d'espèces")
    ax.grid(True, axis="y")
    ax.set_axisbelow(True)
    haut = max(nombres) if nombres else 0
    for bar, n in zip(bars, nombres):
        if n:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + haut * 0.01, str(n),
                    ha="center", va="bottom", fontsize=9)
    plt.savefig(output_path, dpi=150)
    plt.close(fig)
