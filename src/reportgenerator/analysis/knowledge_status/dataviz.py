import matplotlib.pyplot as plt

from reportgenerator.analysis.common.theme import LPO_COLORS, apply_lpo_theme
from reportgenerator.analysis.common.theme import (
    LPO_COLORS,
    apply_lpo_theme,
    get_taxo_color,
)

def safe_int(value):
    if value is None:
        return 0
    return int(value)


def create_temporal_evolution_chart(data, output_path: str):
    print("Création du graphique d'évolution temporelle...")

    apply_lpo_theme()

    years = [safe_int(row["annee"]) for row in data]
    nb_data = [safe_int(row["nb_data_tot"]) for row in data]
    nb_species = [safe_int(row["nb_espece"]) for row in data]

    fig, ax1 = plt.subplots(figsize=(14, 7))

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
    ax1.set_ylabel("Nombre de données", color=LPO_COLORS["blue"])

    ax1.tick_params(axis="y", labelcolor=LPO_COLORS["blue"])

    ax1.grid(True, axis="y")

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

    ax2.set_ylabel("Nombre d'espèces", color=LPO_COLORS["orange"])

    ax2.tick_params(axis="y", labelcolor=LPO_COLORS["orange"])

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
    # ax2.spines["left"].set_visible(False)

    # -------------------------
    # Export
    # -------------------------

    plt.savefig(output_path, dpi=150)

    plt.close(fig)
    print(f"Graphique enregistré : {output_path}")

def create_species_by_group_chart(data, output_path: str):
    print("Création du graphique du nombre d'espèces par groupe taxonomique...")

    apply_lpo_theme()

    data_sorted = sorted(data, key=lambda row: safe_int(row["nb_espece"]), reverse=True)
    groups = [row["group_taxo"] for row in data_sorted]
    values = [safe_int(row["nb_espece"]) for row in data_sorted]
    colors = [get_taxo_color(group) for group in groups]

    fig, ax = plt.subplots(figsize=(10, 6))

    bars = ax.barh(groups, values, color=colors)
    ax.invert_yaxis()

    ax.set_xlabel("Nombre d'espèces")
    ax.grid(True, axis="x")

    plt.title("Nombre d'espèces par groupe taxonomique", loc="left", pad=20)

    max_value = max(values) if values else 0
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_width() + max_value * 0.01,
            bar.get_y() + bar.get_height() / 2,
            str(value),
            va="center",
            fontsize=9,
        )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"Graphique enregistré : {output_path}")

def create_data_by_group_chart(data, output_path: str):
    print("Création du graphique du nombre de données par groupe taxonomique...")

    apply_lpo_theme()

    data_sorted = sorted(data, key=lambda row: safe_int(row["nb_data_tot"]), reverse=True)
    groups = [row["group_taxo"] for row in data_sorted]
    values = [safe_int(row["nb_data_tot"]) for row in data_sorted]
    colors = [get_taxo_color(group) for group in groups]

    fig, ax = plt.subplots(figsize=(10, 6))

    bars = ax.barh(groups, values, color=colors)
    ax.invert_yaxis()

    ax.set_xlabel("Nombre de données")
    ax.grid(True, axis="x")

    plt.title("Nombre de données par groupe taxonomique", loc="left", pad=20)

    max_value = max(values) if values else 0
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_width() + max_value * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"{value:,}".replace(",", " "),
            va="center",
            fontsize=9,
        )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"Graphique enregistré : {output_path}")


    print("Création du graphique du nombre de données par groupe taxonomique...")

    apply_lpo_theme()

    data_sorted = sorted(data, key=lambda row: safe_int(row["nb_data_tot"]), reverse=True)
    groups = [row["group_taxo"] for row in data_sorted]
    values = [safe_int(row["nb_data_tot"]) for row in data_sorted]

    fig, ax = plt.subplots(figsize=(10, 6))

    bars = ax.barh(groups, values, color=LPO_COLORS["blue"])
    ax.invert_yaxis()  # groupe avec le plus de données en haut

    ax.set_xlabel("Nombre de données")
    ax.grid(True, axis="x")

    plt.title(
        "Nombre de données par groupe taxonomique",
        loc="left",
        pad=20,
    )

    max_value = max(values) if values else 0
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_width() + max_value * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"{value:,}".replace(",", " "),
            va="center",
            fontsize=9,
        )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"Graphique enregistré : {output_path}")
    print("Création du graphique du nombre de données par groupe taxonomique...")

    apply_lpo_theme()

    data_sorted = sorted(data, key=lambda row: safe_int(row["nb_data_tot"]), reverse=True)
    groups = [row["group_taxo"] for row in data_sorted]
    values = [safe_int(row["nb_data_tot"]) for row in data_sorted]

    fig, ax = plt.subplots(figsize=(10, 6))

    bars = ax.barh(groups, values, color=LPO_COLORS["blue"])
    ax.invert_yaxis()  # groupe avec le plus de données en haut

    ax.set_xlabel("Nombre de données")
    ax.grid(True, axis="x")

    plt.title(
        "Nombre de données par groupe taxonomique",
        loc="left",
        pad=20,
    )

    max_value = max(values) if values else 0
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_width() + max_value * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"{value:,}".replace(",", " "),
            va="center",
            fontsize=9,
        )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"Graphique enregistré : {output_path}")