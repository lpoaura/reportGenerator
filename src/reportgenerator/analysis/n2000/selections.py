"""
Règles du dossier Natura 2000, écrites une seule fois (SQL sur la VM, alias « s »).
Cf. dossiers/natura2000/METHODO.md.
"""

from reportgenerator.analysis.eolien.selections import MIGRATION
from reportgenerator.queries import sql_literals

__all__ = ["MIGRATION"]

ESPECE = "s.id_rang in ('ES', 'SSES')"
PROCHE = "s.anneau_ordre <= 1"   # site et premier anneau (le kilomètre autour)
OISEAU = "s.tx_group2_inpn_v2 = 'Oiseaux'"

# n2k de taxonomie.mv_c_statut : « Annexe I », « Annexes II, IV », « Annexe II/2, Annexe III/2 »...
# Oiseaux : annexe I de la directive Oiseaux (les annexes II/1, II/2 et III de la colonne sont les annexes
# « chasse » de cette même directive). Autres groupes : annexe II de la directive Habitats.
N2K_ANNEXE_I_RE = "(^|, )Annexe I(,|$)"
N2K_ANNEXE_II_RE = "(^|, )Annexes? II(,|$)"
N2000_ESPECE = (f"(({OISEAU} and s.n2k ~ '{N2K_ANNEXE_I_RE}') "
                f"or (not {OISEAU} and s.n2k ~ '{N2K_ANNEXE_II_RE}'))")

STATUT_NIDIF_RANG = ("case s.oiso_status_nidif when 'Certain' then 3 when 'Probable' then 2 "
                     "when 'Possible' then 1 else 0 end")
# hivernage : du 1er décembre au 31 janvier
HIVERNANT = "to_char(s.date_max, 'MMDD') not between '0201' and '1130'"
# catégorie d'une donnée sur les cartes de l'atlas (légende)
TYPE_DONNEE = ("case s.oiso_status_nidif when 'Certain' then 'Nicheur certain' when 'Probable' then 'Nicheur probable' "
               "when 'Possible' then 'Nicheur possible' else 'Autres données' end")
CHIRO_COLONIE = "coalesce(s.bat_breed_colo, false)"
CHIRO_GITE = "(coalesce(s.bat_is_gite, false) or coalesce(s.bat_breed_colo, false))"


def _cd_refs(values) -> str:
    return ", ".join(str(int(v)) for v in values) or "null"


def n2000_sql(complexes=(), exclus=()) -> str:
    """Taxon Natura 2000 : espèce aux annexes, ou genre / complexe retenu (cf. complexes_n2000), hors exclus."""
    return f"(({N2000_ESPECE} or s.cd_ref in ({_cd_refs(complexes)})) and not ({exclus_sql(exclus)}))"


def retenu_sql(complexes=()) -> str:
    """Taxons analysés : les espèces, plus les genres et complexes Natura 2000."""
    return f"({ESPECE} or s.cd_ref in ({_cd_refs(complexes)}))"


LR_ENJEU = "('CR', 'EN', 'VU', 'NT')"


def enjeu_sql(oiseaux_nicheurs_seulement=True) -> str:
    """Espèce à enjeux (cartes de connaissance) : Natura 2000, ou liste rouge régionale CR/EN/VU/NT (nationale
    si la régionale manque). Oiseaux : seulement avec un statut de nicheur (sinon presque toutes les mailles
    comptent des dizaines d'espèces à enjeux de passage)."""
    lr = (f"(s.lr_aura in {LR_ENJEU} or (s.lr_aura is null and coalesce(s.lr_fr_nich, s.lr_france) in {LR_ENJEU}))")
    base = f"({N2000_ESPECE} or {lr})"
    if oiseaux_nicheurs_seulement:
        return f"({base} and (not {OISEAU} or s.oiso_status_nidif in ('Possible', 'Probable', 'Certain')))"
    return base


def exclus_sql(noms=()) -> str:
    """Taxons écartés de la liste Natura 2000 (statut erroné dans mv_c_statut, donnée échappée...),
    par nom scientifique (binôme : sous-espèces comprises)."""
    if not noms:
        return "false"
    return f"split_part(s.vn_nom_sci, ' ', 1) || ' ' || split_part(s.vn_nom_sci, ' ', 2) in ({sql_literals(noms)})"


# Le rayon de prise en compte selon le taxon est appliqué dans la VM (paramètres rayon_defaut_km et
# [params.rayons_km], cf. SyntheseQueries._rayon_par_taxon_sql) : toutes les données de la VM sont retenues.


def both(*conds: str) -> str:
    return " and ".join(f"({c})" for c in conds)
