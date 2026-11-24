"""Sélections SQL de l'état des connaissances (alias s = VM principale)."""

from reportgenerator.analysis.n2000.selections import ESPECE, N2000_ESPECE, OISEAU  # noqa: F401 (ESPECE réexporté)

LR_ENJEU = "('CR', 'EN', 'VU', 'NT')"


def enjeu_sql(oiseaux_nicheurs_seulement=True) -> str:
    """Espèce à enjeux (chiffre rouge des cartes) : Natura 2000 (oiseaux : annexe I DO, autres : annexe II DHFF),
    ou liste rouge régionale CR/EN/VU/NT (nationale si la régionale manque). Même définition pour tous les dossiers.
    Oiseaux : seulement avec un statut de nicheur (sinon presque toutes les mailles comptent des dizaines
    d'espèces à enjeux de passage)."""
    lr = (f"(s.lr_aura in {LR_ENJEU} or (s.lr_aura is null and coalesce(s.lr_fr_nich, s.lr_france) in {LR_ENJEU}))")
    base = f"({N2000_ESPECE} or {lr})"
    if oiseaux_nicheurs_seulement:
        return f"({base} and (not {OISEAU} or s.oiso_status_nidif in ('Possible', 'Probable', 'Certain')))"
    return base
