from pathlib import Path

import matplotlib.font_manager as fm
from matplotlib import pyplot as plt
from matplotlib.font_manager import FontProperties

print("Chargement du thème LPO...")

FONT_DIR = Path(__file__).parent.parent.parent / "templates" / "fonts"

fm.fontManager.addfont(str(FONT_DIR / "LPO-Regular.otf"))

fm.fontManager.addfont(str(FONT_DIR / "LPO-Bold.otf"))

font_path = FONT_DIR / "LPO-Regular.otf"
prop = FontProperties(fname=str(font_path))
print("Proprietes de la police:", prop.get_name())
fm.fontManager.addfont(str(font_path))


TAXO_COLORS = {
    "Oiseaux": "#4a90c4",             # bleu ciel
    "Papillons de jour": "#f2a900",   # orange/jaune vif
    "Mammifères": "#7a5230",          # brun
    "Poissons": "#1f5c7a",            # bleu profond
    "Odonates": "#00a8a0",            # cyan/turquoise
    "Papillons de nuit": "#4b2e5a",   # violet sombre
    "Chauves-souris": "#8c7fa8",      # gris-mauve
    "Orthoptères": "#6faa2c",         # vert vif
    "Amphibiens": "#4f7942",          # vert olive
    "Reptiles": "#a68b5b",            # kaki
}

TAXO_DEFAULT_COLOR = "#999999"  # gris neutre pour tout taxon non listé

TAXO_POOL_COLOR = "#F0F0EB"  # gris neutre pour tout taxon non listé

def get_taxo_color(group_name: str) -> str:
    return TAXO_COLORS.get(group_name, TAXO_DEFAULT_COLOR)

LPO_COLORS = {
    "blue": "#0088cc",
    "orange": "#eb5f1a",
    "green": "#007e85",
    "red": "#e62328",
    "yellow": "#ffc33c",
    "black": "#323232",
    "dark": "#191919",
    "white": "#F0F0EB",
}


def apply_lpo_theme():
    """
    Applique la charte graphique LPO à Matplotlib.
    """
    plt.rcParams.update(
        {
            "font.family": "LPO",
            "font.size": 11,
            "axes.titlesize": 16,
            "axes.titleweight": "bold",
            "axes.labelsize": 12,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#AAAAAA",
            "axes.linewidth": 1,
            "grid.color": "#DDDDDD",
            "grid.linestyle": "--",
            "grid.linewidth": 0.8,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.1,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
