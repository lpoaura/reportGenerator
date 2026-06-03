from pathlib import Path
from matplotlib import pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.font_manager import FontProperties

print("Chargement du thème LPO...")

FONT_DIR = Path(__file__).parent.parent.parent / "templates" / "fonts"

fm.fontManager.addfont(
    str(FONT_DIR / "LPO-Regular.otf")
)

fm.fontManager.addfont(
    str(FONT_DIR / "LPO-Bold.otf")
)

font_path = FONT_DIR / "LPO-Regular.otf"
prop = FontProperties(fname=str(font_path))
print('Proprietes de la police:', prop.get_name())
fm.fontManager.addfont(str(font_path))

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
