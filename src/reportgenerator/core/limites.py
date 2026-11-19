"""
limites.py

Limites de génération communes à tous les dossiers et bilan d'une génération (docs/limites/conception.md).
Fonctions pures : l'écriture en base est dans reportgenerator/suivi.py.
"""

from dataclasses import dataclass, field
from datetime import datetime

# Seuils par défaut, surchargeables dans le [params] d'un dossier (limite_donnees, limite_comptage_min, limite_vue_min)
LIMITE_DONNEES = 1_000_000  # données de la vue de synthèse (comptées avant dédoublonnage des sources)
LIMITE_COMPTAGE_MIN = 5  # délai du comptage : au-delà, la zone est jugée trop lourde
LIMITE_VUE_MIN = 30  # délai de construction de la vue de synthèse

LANCEMENT_MANUEL = "Lancement manuel : cli.py run ... --sans-limite"
ERREUR_MAX_CAR = 500


@dataclass(frozen=True)
class Limites:
    """None = pas de limite (dossier sans vue de synthèse, ou lancement manuel --sans-limite)."""
    donnees: int | None = LIMITE_DONNEES
    comptage_min: float | None = LIMITE_COMPTAGE_MIN
    vue_min: float | None = LIMITE_VUE_MIN

    @classmethod
    def du_dossier(cls, params: dict, sans_limite: bool = False) -> "Limites":
        if sans_limite:
            return cls(None, None, None)
        return cls(int(params.get("limite_donnees", LIMITE_DONNEES)),
                   float(params.get("limite_comptage_min", LIMITE_COMPTAGE_MIN)),
                   float(params.get("limite_vue_min", LIMITE_VUE_MIN)))


def statement_timeout_ms(minutes: float | None) -> int:
    """Valeur de statement_timeout (ms) ; 0 = sans délai."""
    return 0 if minutes is None else int(minutes * 60_000)


class LimiteDepassee(Exception):
    """Demande refusée sans construire la vue : relançable à la main avec --sans-limite."""


class TropDeDonnees(LimiteDepassee):
    def __init__(self, nb: int, seuil: int):
        self.nb, self.seuil = nb, seuil
        super().__init__(f"Trop de données : {nombre(nb)} > {nombre(seuil)}")


class ComptageTropLong(LimiteDepassee):
    def __init__(self, delai_min: float):
        self.delai_min = delai_min
        super().__init__(f"Comptage des données trop long (> {duree(delai_min * 60)})")


class VueTropLongue(Exception):
    """Construction de la vue de synthèse annulée par la base (statement_timeout)."""

    def __init__(self, delai_min: float, nb_donnees: int | None = None):
        self.delai_min, self.nb_donnees = delai_min, nb_donnees
        super().__init__(f"Temps de calcul trop long : vue arrêtée après {duree(delai_min * 60)}")


@dataclass
class Bilan:
    statut: str  # en_cours, ok, refuse, erreur (cf. src_gestion.update_reportgenerator_bilan)
    commentaire: str  # ref_geo.l_areas.comment
    details: dict = field(default_factory=dict)  # additional_data.reportgenerate


def nombre(n: int) -> str:
    return f"{int(n):,}".replace(",", " ")


def duree(secondes: float) -> str:
    s = int(round(secondes))
    h, reste = divmod(s, 3600)
    m, s = divmod(reste, 60)
    if h:
        return f"{h} h {m} min" if m else f"{h} h"
    if m:
        return f"{m} min {s} s" if s else f"{m} min"
    return f"{s} s"


def _quand(dt: datetime) -> str:
    return f"{dt:%d/%m/%Y %H:%M}"


def bilan_en_cours(debut: datetime, dossier: str) -> Bilan:
    return Bilan("en_cours", f"EN COURS depuis le {_quand(debut)}", {"dossier": dossier})


def bilan_ok(fin: datetime, duree_s: float, dossier: str, nb_donnees: int | None = None,
             duree_vue_s: float | None = None) -> Bilan:
    details = {"dossier": dossier, "duree_s": round(duree_s)}
    texte = f"OK le {_quand(fin)} : {duree(duree_s)}"
    if duree_vue_s is not None:
        details["duree_vue_s"] = round(duree_vue_s)
        texte += f" (vue {duree(duree_vue_s)})"
    if nb_donnees is not None:
        details["nb_donnees"] = int(nb_donnees)
        texte += f", {nombre(nb_donnees)} données"
    return Bilan("ok", texte, details)


def bilan_echec(exc: BaseException, fin: datetime, duree_s: float, dossier: str) -> Bilan:
    details = {"dossier": dossier, "duree_s": round(duree_s)}
    if isinstance(exc, TropDeDonnees):
        details.update(motif="trop_de_donnees", nb_donnees=exc.nb, seuil_donnees=exc.seuil)
        return Bilan("refuse", f"REFUSÉ le {_quand(fin)} : trop de données, {nombre(exc.nb)} > {nombre(exc.seuil)}. "
                               f"{LANCEMENT_MANUEL}", details)
    if isinstance(exc, ComptageTropLong):
        details.update(motif="comptage_trop_long", delai_min=exc.delai_min)
        return Bilan("refuse", f"REFUSÉ le {_quand(fin)} : comptage des données trop long "
                               f"(> {duree(exc.delai_min * 60)}). {LANCEMENT_MANUEL}", details)
    if isinstance(exc, VueTropLongue):
        details.update(motif="temps_de_calcul", delai_min=exc.delai_min)
        if exc.nb_donnees is not None:
            details["nb_donnees"] = exc.nb_donnees
        return Bilan("erreur", f"ÉCHEC le {_quand(fin)} : temps de calcul trop long, vue arrêtée après "
                               f"{duree(exc.delai_min * 60)}", details)
    erreur = f"{type(exc).__name__}: {exc}"
    if len(erreur) > ERREUR_MAX_CAR:
        erreur = erreur[:ERREUR_MAX_CAR] + "…"
    brique = getattr(exc, "brique", None)
    details.update(motif="erreur", erreur=erreur)
    texte = f"ÉCHEC le {_quand(fin)} : erreur {erreur}"
    if brique:
        details["brique"] = brique
        texte += f" (brique {brique})"
    return Bilan("erreur", texte, details)


def bilan_interrompu(quand: datetime) -> Bilan:
    return Bilan("erreur", f"ÉCHEC le {_quand(quand)} : génération interrompue (processus arrêté)",
                 {"motif": "interrompue"})
