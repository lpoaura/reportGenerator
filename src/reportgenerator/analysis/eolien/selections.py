"""
Sélections d'observations (fragments SQL sur lpoaura_afo.vm_reportgenerator_data, alias s).

Reprises des anciens scripts R éoliens (11_vm_nidif, 14_vm_nidif_dortoir,
16_vm_migration_all). Une sélection sert à la fois aux tableaux, aux chiffres
du texte et aux couches GPKG des cartes : on ne l'écrit qu'une fois.
"""

OISEAUX = "s.classe = 'Aves'"

RAPACES = "s.ordre in ('Accipitriformes', 'Falconiformes', 'Strigiformes')"
RAPACES_NOCTURNES = "s.ordre = 'Strigiformes'"
RAPACES_DIURNES = "s.ordre in ('Accipitriformes', 'Falconiformes')"

# "grands voiliers" des scripts R : ardéidés, cigognes, laridés, grues
GRANDS_VOILIERS = "s.famille in ('Ardeidae', 'Ciconiidae', 'Laridae', 'Gruidae')"

GROUPES_ENJEUX = f"(({RAPACES}) or ({GRANDS_VOILIERS}))"

# tcse.breed_status : 'Possible' / 'Probable' / 'Certain'
NICHEUR_PROBABLE_CERTAIN = "s.oiso_status_nidif in ('Probable', 'Certain')"

# comportement (nomenclature) ou remarque de l'observateur
DORTOIR = "(s.behaviour ilike '%dorto%' or s.comment_description ilike '%dorto%')"
MIGRATION = "(s.behaviour ilike '%migr%' or s.comment_description ilike '%migr%')"

# groupe cartographique des nicheurs (champ "groupe" de la couche nidification)
GROUPE_NIDIF_SQL = f"""case when {RAPACES_NOCTURNES} then 'rapace_nocturne'
                            when {RAPACES_DIURNES} then 'rapace_diurne'
                            when s.famille = 'Ardeidae' then 'ardeide'
                            when s.famille = 'Ciconiidae' then 'ciconiide'
                            when s.famille = 'Laridae' then 'laride'
                            when s.famille = 'Gruidae' then 'gruide'
                            else 'autre' end"""


def both(*fragments: str) -> str:
    return " and ".join(f"({f})" for f in fragments)
