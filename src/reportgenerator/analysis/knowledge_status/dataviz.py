import matplotlib.pyplot as plt

from reportgenerator.analysis.common.theme import (
    LPO_COLORS,
    apply_lpo_theme,
)

def safe_int(value):
    if value is None:
        return 0
    return int(value)


def create_temporal_evolution_chart(
    data,
    output_path: str
):
    print("Création du graphique d'évolution temporelle...")

    apply_lpo_theme()

    years = [safe_int(row["annee"]) for row in data]
    nb_data = [safe_int(row["nb_data_tot"]) for row in data]
    nb_species = [safe_int(row["nb_espece"]) for row in data]

    fig, ax1 = plt.subplots(
        figsize=(14, 7)
    )

    # -------------------------
    # Axe gauche : données
    # -------------------------
    line1 = ax1.plot(
        years,
        nb_data,
        marker="o",
        linewidth=3,
        color=LPO_COLORS["blue"],
        label="Nombre de données",
    )
    
    ax1.scatter(
        years,
        nb_data,
        s=80,
        color=LPO_COLORS["blue"],
        edgecolors="white",
        linewidth=1,
        zorder=10,
    )

    ax1.set_xlabel("Année")
    ax1.set_ylabel(
        "Nombre de données",
        color=LPO_COLORS["blue"]
    )

    ax1.tick_params(
        axis="y",
        labelcolor=LPO_COLORS["blue"]
    )

    ax1.grid(
        True,
        axis="y"
    )


    # -------------------------
    # Axe droit : espèces
    # -------------------------

    ax2 = ax1.twinx()

    line2 = ax2.plot(
        years,
        nb_species,
        marker="o",
        linewidth=3,
        color=LPO_COLORS["orange"],
        label="Nombre d'espèces",
    )

    ax2.set_ylabel(
        "Nombre d'espèces",
        color=LPO_COLORS["orange"]
    )

    ax2.tick_params(
        axis="y",
        labelcolor=LPO_COLORS["orange"]
    )

    # -------------------------
    # Titre
    # -------------------------

    plt.title(
        "Évolution temporelle des connaissances",
        loc="left",
        pad=20,
    )

    # -------------------------
    # Légende combinée
    # -------------------------

    lines = line1 + line2
    labels = [l.get_label() for l in lines]

    ax1.legend(
        lines,
        labels,
        loc="upper left",
        frameon=False,
    )



    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    ax2.spines["top"].set_visible(False)
    #ax2.spines["left"].set_visible(False)

    # -------------------------
    # Export
    # -------------------------

    plt.savefig(
        output_path,
        dpi=150
    )

    plt.close(fig)
    print(f"Graphique enregistré : {output_path}")