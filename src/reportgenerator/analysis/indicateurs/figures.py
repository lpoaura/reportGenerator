"""Graphiques du rapport Indicateurs (matplotlib, charte LPO). Les cartes passent par le projet QGIS du dossier.

Couleurs : palette catégorielle validée (daltonisme) dans un ordre fixe pour les catégories d'observateurs ; une seule
teinte (bleu) pour les grandeurs, la saison du rapport mise en avant (bleu soutenu, saisons passées en bleu clair) ;
rampe bleue claire -> foncée pour les fréquences (carte de chaleur). Chaque graphique sans donnée affiche « Aucune
donnée » (le Word garde sa légende).
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

from reportgenerator.analysis.common.theme import apply_lpo_theme  # noqa: E402
from reportgenerator.analysis.indicateurs.selections import CATEGORIES  # noqa: E402
from reportgenerator.analysis.indicateurs.textes import NBSP_FINE, ecart, feminin, nombre, pluriel  # noqa: E402

BLEU, BLEU_CLAIR, ORANGE, VERT_EAU, GRIS, ROUGE = "#2a78d6", "#9ec5f4", "#eb6834", "#1baf7a", "#a6a6a6", "#e34948"
ENCRE, ENCRE_2 = "#262626", "#666666"
COULEURS_CATEGORIES = {"Salarié LPO": BLEU, "Organisme tiers": ORANGE, "Bénévole": VERT_EAU, "Non renseigné": GRIS}
RAMPE = LinearSegmentedColormap.from_list("bleus", ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])


def _n(x) -> str:
    """Nombre au format français, espace simple (l'espace fine insécable s'affiche mal dans la police LPO)."""
    return nombre(x).replace(NBSP_FINE, " ")


def _fin(fig, path: Path) -> Path:
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return Path(path)


def _vide(path: Path, largeur=7.5, hauteur=1.2) -> Path:
    apply_lpo_theme()
    fig, ax = plt.subplots(figsize=(largeur, hauteur))
    ax.axis("off")
    ax.text(0.5, 0.5, "Aucune donnée pour cette saison", ha="center", va="center", color=ENCRE_2, fontsize=11)
    return _fin(fig, path)


def _axes_sobres(ax, grille="x"):
    for cote in ("top", "right"):
        ax.spines[cote].set_visible(False)
    ax.spines["left" if grille == "x" else "bottom"].set_color("#cccccc")
    ax.grid(axis=grille, color="#e6e6e6", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=ENCRE_2, labelsize=9)


# ------------------------------------------------------------------------------------------- chiffres clés
def chart_chiffres(indicateurs: list[tuple], path: Path, libelle: str, precedent: str) -> Path:
    """Tuiles « chiffre clé » : (libellé, valeur N, valeur N-1) ; écart avec la saison précédente dessous."""
    apply_lpo_theme()
    colonnes = 3
    lignes = (len(indicateurs) + colonnes - 1) // colonnes
    fig, axes = plt.subplots(lignes, colonnes, figsize=(7.5, 1.25 * lignes + 0.3), squeeze=False)
    for ax in axes.flat:
        ax.set_xticks([])
        ax.set_yticks([])
        for cote in ax.spines.values():
            cote.set_visible(False)
    for ax, (lib, v, v1) in zip(axes.flat, indicateurs):
        ax.set_facecolor("#eef4fc")
        ax.text(0.07, 0.78, lib, transform=ax.transAxes, fontsize=9, color=ENCRE_2, va="center")
        ax.text(0.07, 0.47, _n(v), transform=ax.transAxes, fontsize=18, fontweight="bold", color=ENCRE,
                va="center")
        e = ecart(v, v1).replace(NBSP_FINE, " ")   # le signe porte le sens (la police LPO n'a pas de flèches)
        ax.text(0.07, 0.16, f"{e} par rapport à {precedent}" if v1 is not None else "pas de saison précédente",
                transform=ax.transAxes, fontsize=7.5, color=ENCRE_2, va="center")
    for ax in list(axes.flat)[len(indicateurs):]:
        ax.set_visible(False)
    fig.suptitle(f"Saison {libelle}", x=0.01, ha="left", fontsize=10, color=ENCRE_2)
    fig.tight_layout(w_pad=1.2, h_pad=1.0)
    return _fin(fig, path)


# ----------------------------------------------------------------------------------------------- catégories
def chart_categories(lignes: list[dict], path: Path, label_aires: str) -> Path:
    """Part de chaque catégorie d'observateurs dans les aires, observateurs, données et temps (barres 100 %)."""
    if not lignes:
        return _vide(path)
    apply_lpo_theme()
    mesures = [("aires", label_aires.capitalize()), ("observateurs", "Observateurs"), ("donnees", "Données"),
               ("heures", "Temps")]
    cats = [c for c in CATEGORIES if any(r["categorie"] == c for r in lignes)]
    par_cat = {r["categorie"]: r for r in lignes}
    fig, ax = plt.subplots(figsize=(7.5, 0.55 * len(mesures) + 0.9))
    for i, (cle, lib) in enumerate(mesures):
        total = sum(float(par_cat[c][cle] or 0) for c in cats) or 1
        gauche = 0.0
        for c in cats:
            part = 100 * float(par_cat[c][cle] or 0) / total
            ax.barh(i, part, left=gauche, color=COULEURS_CATEGORIES[c], edgecolor="white", linewidth=1.5,
                    height=0.6, label=c if i == 0 else None)
            if part >= 7:
                ax.text(gauche + part / 2, i, f"{part:.0f} %", ha="center", va="center", fontsize=8, color="white",
                        fontweight="bold")
            gauche += part
    ax.set_yticks(range(len(mesures)), [lib for _, lib in mesures])
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xticks([])
    for cote in ("top", "right", "bottom", "left"):
        ax.spines[cote].set_visible(False)
    ax.tick_params(colors=ENCRE, labelsize=9, length=0)
    ax.legend(frameon=False, ncols=len(cats), loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=9)
    return _fin(fig, path)


# ----------------------------------------------------------------------------------- département, zone
def chart_groupes(lignes: list[dict], cle: str, path: Path, series: list[tuple], xlabel: str) -> Path:
    """Barres horizontales par groupe (département, zone biogéographique), séries empilées ; le total est écrit au
    bout de la barre. series = [(clé, libellé, couleur)] ; la ligne de total est ignorée."""
    lignes = [r for r in lignes if not r.get("total")]
    if not lignes:
        return _vide(path)
    apply_lpo_theme()
    lignes = sorted(lignes, key=lambda r: sum(r[s] for s, _, _ in series), reverse=True)
    fig, ax = plt.subplots(figsize=(7.5, 0.38 * len(lignes) + 1.0))
    y = range(len(lignes))
    gauche = [0] * len(lignes)
    for s, lib, couleur in series:
        valeurs = [r[s] for r in lignes]
        ax.barh(y, valeurs, left=gauche, color=couleur, edgecolor="white", linewidth=1.5, height=0.62, label=lib)
        gauche = [g + v for g, v in zip(gauche, valeurs)]
    for i, total in enumerate(gauche):
        ax.text(total, i, f" {_n(total)}", va="center", fontsize=8, color=ENCRE)
    ax.set_yticks(list(y), [r[cle] for r in lignes])
    ax.invert_yaxis()
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlabel(xlabel, fontsize=9, color=ENCRE_2)
    _axes_sobres(ax)
    if len(series) > 1:
        ax.legend(frameon=False, ncols=len(series), loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=9)
    return _fin(fig, path)


def chart_barres(valeurs: dict, path: Path, xlabel: str, couleur: str = BLEU) -> Path:
    """Barres horizontales simples (une seule série), valeur au bout de la barre."""
    if not valeurs:
        return _vide(path)
    apply_lpo_theme()
    noms, vals = list(valeurs), list(valeurs.values())
    fig, ax = plt.subplots(figsize=(7.5, 0.38 * len(noms) + 0.8))
    ax.barh(range(len(noms)), vals, color=couleur, height=0.62)
    for i, v in enumerate(vals):
        ax.text(v, i, f" {_n(v)}", va="center", fontsize=8, color=ENCRE)
    ax.set_yticks(range(len(noms)), noms)
    ax.invert_yaxis()
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlabel(xlabel, fontsize=9, color=ENCRE_2)
    _axes_sobres(ax)
    return _fin(fig, path)


def chart_objectifs(lignes: list[dict], path: Path, xlabel: str) -> Path:
    """Sites suivis par zone, avec l'objectif de la zone (trait) quand il est renseigné."""
    if not lignes:
        return _vide(path)
    apply_lpo_theme()
    fig, ax = plt.subplots(figsize=(7.5, 0.45 * len(lignes) + 1.0))
    for i, r in enumerate(lignes):
        ax.barh(i, r["sites"], color=BLEU, height=0.6, label="Sites suivis" if i == 0 else None)
        ax.text(r["sites"], i, f" {r['sites']}", va="center", fontsize=8, color=ENCRE)
        if isinstance(r["objectif"], (int, float)):
            ax.plot([r["objectif"]] * 2, [i - 0.38, i + 0.38], color=ENCRE, linewidth=2,
                    label="Objectif" if i == 0 else None)
    ax.set_yticks(range(len(lignes)), [r["zone"] for r in lignes])
    ax.invert_yaxis()
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlabel(xlabel, fontsize=9, color=ENCRE_2)
    _axes_sobres(ax)
    ax.legend(frameon=False, ncols=2, loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=9)
    return _fin(fig, path)


# ---------------------------------------------------------------------------------------------- historique
def chart_historique(serie: list[dict], path: Path, libelles: dict, debut_obs: int) -> Path:
    """Petits multiples (une échelle par graphique) : aires, observateurs, données, temps par saison ; la saison
    du rapport en bleu soutenu, les précédentes en bleu clair."""
    if not serie:
        return _vide(path)
    apply_lpo_theme()
    saisons = [r["saison"] for r in serie]
    panneaux = [("aires", libelles["aires"]), ("observateurs", "Observateurs"), ("donnees", "Données"),
                ("heures", "Temps (h)")]
    fig, axes = plt.subplots(2, 2, figsize=(7.5, 4.6), sharex=True)
    couleurs = [BLEU_CLAIR] * (len(saisons) - 1) + [BLEU]
    for ax, (cle, titre) in zip(axes.flat, panneaux):
        valeurs = [(r[cle] if cle != "observateurs" or r["saison"] >= debut_obs else 0) or 0 for r in serie]
        ax.bar(saisons, valeurs, color=couleurs, width=0.75)
        ax.set_title(titre, fontsize=10, color=ENCRE, loc="left")
        ax.text(saisons[-1], valeurs[-1], f"{_n(round(valeurs[-1]))}", ha="center", va="bottom", fontsize=8,
                color=ENCRE)
        ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=4))
        _axes_sobres(ax, grille="y")
    pas = max(1, len(saisons) // 8)
    for ax in axes[1]:
        ax.set_xticks(saisons[::pas], [libelles["saison"](s) for s in saisons[::pas]], rotation=45, ha="right")
    fig.tight_layout()
    return _fin(fig, path)


def chart_observateurs(series_cat: list[dict], path: Path) -> Path:
    """Observateurs (comptes) par catégorie et par saison, en barres empilées."""
    if not series_cat:
        return _vide(path)
    apply_lpo_theme()
    saisons = [r["saison"] for r in series_cat]
    fig, ax = plt.subplots(figsize=(7.5, 3.2))
    bas = [0] * len(saisons)
    for c in CATEGORIES:
        valeurs = [r.get(c, 0) for r in series_cat]
        if not any(valeurs):
            continue
        ax.bar(saisons, valeurs, bottom=bas, color=COULEURS_CATEGORIES[c], label=c, edgecolor="white",
               linewidth=1, width=0.75)
        bas = [b + v for b, v in zip(bas, valeurs)]
    ax.set_ylabel("Observateurs", fontsize=9, color=ENCRE_2)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xticks(saisons, [str(s) for s in saisons], rotation=45 if len(saisons) > 8 else 0)
    _axes_sobres(ax, grille="y")
    if any(bas):
        ax.legend(frameon=False, ncols=4, loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=9)
    return _fin(fig, path)


# ------------------------------------------------------------------------------------------------- espèces
def chart_especes(especes: list[dict], path: Path, label_aires: str) -> Path:
    """Espèces les plus fréquentes : part des aires où l'espèce est notée (barres), effectif cumulé écrit."""
    if not especes:
        return _vide(path)
    apply_lpo_theme()
    fig, ax = plt.subplots(figsize=(7.5, 0.3 * len(especes) + 0.9))
    y = range(len(especes))
    freqs = [e["freq_aires"] or 0 for e in especes]
    ax.barh(y, freqs, color=BLEU, height=0.65)
    for i, e in enumerate(especes):
        ax.text(freqs[i], i, f" {freqs[i]} %  ·  {_n(e['effectif'])} ind.", va="center", fontsize=7.5,
                color=ENCRE_2)
    ax.set_yticks(list(y), [e["nom"] for e in especes], fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlim(0, 118)
    ax.set_xticks([0, 25, 50, 75, 100], ["0", "25 %", "50 %", "75 %", "100 %"])
    suivis = "suivies" if feminin(label_aires) else "suivis"
    ax.set_xlabel(f"Part des {pluriel(label_aires)} {suivis} où l'espèce est notée", fontsize=9, color=ENCRE_2)
    _axes_sobres(ax)
    return _fin(fig, path)


def chart_evolution(evolution: list[dict], path: Path, libelle) -> Path:
    """Carte de chaleur espèces × saisons : part des aires où l'espèce est notée (indicateur descriptif)."""
    if not evolution:
        return _vide(path)
    apply_lpo_theme()
    saisons = [k for k in evolution[0] if k != "nom"]
    # échelle de couleur sur l'étendue des valeurs présentes (fréquences souvent toutes entre 80 et 100 %)
    valeurs = [e[s] for e in evolution for s in saisons if e[s] is not None] or [0]
    bas, haut = min(valeurs), max(valeurs)
    niveau = (lambda v: 0.15 + 0.85 * (v - bas) / (haut - bas)) if haut > bas else (lambda v: 0.6)
    fig, ax = plt.subplots(figsize=(7.5, 0.32 * len(evolution) + 1.0))
    for i, e in enumerate(evolution):
        for j, s in enumerate(saisons):
            v = e[s]
            if v is None:
                ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, facecolor="#f2f2f2", edgecolor="white", lw=2))
                ax.text(j, i, "—", ha="center", va="center", fontsize=8, color=ENCRE_2)
                continue
            ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, facecolor=RAMPE(niveau(v)), edgecolor="white",
                                       lw=2))
            ax.text(j, i, f"{v} %", ha="center", va="center", fontsize=8,
                    color="white" if niveau(v) >= 0.55 else ENCRE)
    ax.set_xlim(-0.5, len(saisons) - 0.5)
    ax.set_ylim(len(evolution) - 0.5, -0.5)
    ax.set_xticks(range(len(saisons)), [libelle(s) for s in saisons])
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(evolution)), [e["nom"] for e in evolution], fontsize=8.5)
    for cote in ("top", "right", "bottom", "left"):
        ax.spines[cote].set_visible(False)
    ax.tick_params(length=0, colors=ENCRE, labelsize=8.5)
    return _fin(fig, path)
