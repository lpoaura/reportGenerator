import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from reportgenerator.analysis.common.theme import (
    LPO_COLORS,
    apply_lpo_theme,
    get_taxo_color,
    TAXO_COLORS,
    TAXO_DEFAULT_COLOR,
    TAXO_POOL_COLOR,
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


def merge_taxo_data(observed_data, reference_data):
    """Associe le nombre d'espèces observées sur la zone (observed_data)
    au pool régional de référence (reference_data), par taxon."""
    ref_map = {
        row["tx_group2_inpn_v2"]: safe_int(row["nb_esp"])
        for row in reference_data
    }

    merged = []
    for row in observed_data:
        group = row["group_taxo"]
        nb_obs = safe_int(row["nb_espece"])
        nb_ref = ref_map.get(group)

        if nb_ref is None:
            print(f"Attention : pas de pool régional trouvé pour le taxon '{group}'")

        merged.append({"group": group, "nb_obs": nb_obs, "nb_ref": nb_ref})

    return merged


def create_species_by_group_chart(data, output_path: str):
    """Graphique existant : richesse brute par taxon (couleur par taxon)."""
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


def create_species_double_bar_chart(observed_data, reference_data, output_path: str):
    """Graphique B : espèces observées vs pool régional, par taxon."""
    print("Création du graphique observé / pool régional par taxon...")

    apply_lpo_theme()

    merged = merge_taxo_data(observed_data, reference_data)
    merged_sorted = sorted(merged, key=lambda d: d["nb_obs"], reverse=True)

    groups = [d["group"] for d in merged_sorted]
    obs_values = [d["nb_obs"] for d in merged_sorted]
    ref_values = [d["nb_ref"] or 0 for d in merged_sorted]
    colors = [get_taxo_color(g) for g in groups]

    fig, ax = plt.subplots(figsize=(10, 7))

    y_pos = list(range(len(groups)))
    bar_height = 0.38

    ax.barh(
        [y - bar_height / 2 for y in y_pos],
        ref_values,
        height=bar_height,
        color=TAXO_POOL_COLOR,
    )
    ax.barh(
        [y + bar_height / 2 for y in y_pos],
        obs_values,
        height=bar_height,
        color=colors,
    )

    ax.set_yticks(y_pos)
    ax.set_yticklabels(groups)
    ax.invert_yaxis()

    ax.set_xlabel("Nombre d'espèces")
    ax.grid(True, axis="x")
    plt.title("Espèces observées vs pool régional par taxon", loc="left", pad=20)

    handles = [
        Patch(color=TAXO_POOL_COLOR, label="Pool régional (référence, 20 ans)"),
        Patch(color=LPO_COLORS["blue"], label="Observé sur la zone (couleur = taxon)"),
    ]
    ax.legend(handles=handles, loc="lower right", frameon=False, fontsize=9)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"Graphique enregistré : {output_path}")

def create_species_coverage_chart(observed_data, reference_data, output_path: str):
    """Graphique A : taux de connaissance (% du pool régional observé), par taxon."""
    print("Création du graphique du taux de connaissance par taxon...")

    apply_lpo_theme()

    merged = merge_taxo_data(observed_data, reference_data)
    merged = [d for d in merged if d["nb_ref"]]  # exclut les taxons sans référence

    for d in merged:
        d["pct"] = round(d["nb_obs"] / d["nb_ref"] * 100, 1)

    merged_sorted = sorted(merged, key=lambda d: d["pct"], reverse=True)

    groups = [d["group"] for d in merged_sorted]
    pct_values = [d["pct"] for d in merged_sorted]
    colors = [get_taxo_color(g) for g in groups]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(groups, pct_values, color=colors)
    ax.invert_yaxis()

    ax.set_xlim(0, 100)
    ax.set_xlabel("Taux de connaissance (%)")
    ax.grid(True, axis="x")
    plt.title(
        "Taux de connaissance par taxon (espèces observées / pool régional)",
        loc="left",
        pad=20,
    )

    for bar, value in zip(bars, pct_values):
        ax.text(
            bar.get_width() + 1,
            bar.get_y() + bar.get_height() / 2,
            f"{value:.0f}%",
            va="center",
            fontsize=9,
        )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"Graphique enregistré : {output_path}")

def safe_year(value):
    return int(value) if value is not None else None


def create_disparition_chart(data, output_path: str, max_species=30):
    print("Création de la frise des espèces en régression / disparues...")

    if not data:
        print("Aucune espèce en régression ou disparue à afficher.")
        return

    apply_lpo_theme()

    # priorité : disparues d'abord, puis les plus anciennes, limité à max_species
    data_sorted = sorted(
        data,
        key=lambda r: (r["statut_disparition"] != "Disparue", r["derniere_annee"]),
    )[:max_species]

    # ordre d'affichage : la plus préoccupante en haut
    data_sorted = list(reversed(data_sorted))

    fig, ax = plt.subplots(figsize=(12, max(4, 0.35 * len(data_sorted))))

    status_colors = {
        "Disparue": LPO_COLORS["red"],
        "En régression": LPO_COLORS["orange"],
    }

    for i, row in enumerate(data_sorted):
        premiere = safe_year(row["premiere_annee"])
        derniere = safe_year(row["derniere_annee"])
        color = status_colors.get(row["statut_disparition"], LPO_COLORS["black"])

        ax.plot([premiere, derniere], [i, i], color=color, linewidth=3,
                solid_capstyle="round", zorder=1, alpha=0.7)
        ax.scatter(premiere, i, color=LPO_COLORS["blue"], s=45,
                   edgecolors="white", linewidth=1, zorder=3)
        ax.scatter(derniere, i, color=color, s=70,
                   edgecolors="white", linewidth=1, zorder=3)

    labels = [f"{r['nom_vern']} ({r['lb_nom']})" for r in data_sorted]
    ax.set_yticks(range(len(data_sorted)))
    ax.set_yticklabels(labels, fontsize=9, style="italic")

    ax.set_xlabel("Année")
    ax.set_title("Espèces en régression ou disparues du territoire", loc="left", pad=20)

    ax.grid(True, axis="x")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)

    # légende manuelle
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=LPO_COLORS["blue"],
               label="Première observation", markersize=8),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=LPO_COLORS["orange"],
               label="Dernière obs. (en régression)", markersize=8),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=LPO_COLORS["red"],
               label="Dernière obs. (disparue)", markersize=8),
    ]
    ax.legend(handles=legend_elements, loc="upper right", frameon=False)

    plt.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"Frise disparition enregistrée : {output_path}")