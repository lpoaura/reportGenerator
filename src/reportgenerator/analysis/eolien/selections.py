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

# Comportement saisi dans VisioNature (s.comportement : "Dortoir / reposoir", "Migration active"),
# la nomenclature GeoNature (s.behaviour, presque toujours "Inconnu"), et en complément la remarque
# de l'observateur, hors mentions négatives ("aucun dortoir", "pas de migration"...).
DORTOIR = """(s.comportement ilike '%dortoir%' or s.behaviour ilike '%dorto%'
              or (s.comment_description ilike '%dorto%'
                  and s.comment_description !~* '(aucun|pas de|sans|plus de) +(pr[ée]-?)?dorto'))"""
MIGRATION = """(s.comportement ilike '%migration%' or s.behaviour ilike '%migr%'
                or (s.comment_description ilike '%migr%'
                    and s.comment_description !~* '(aucune?|pas de|sans) +migr'))"""

# groupe cartographique des nicheurs (champ "groupe" de la couche nidification)
GROUPE_NIDIF_SQL = f"""case when {RAPACES_NOCTURNES} then 'rapace_nocturne'
                            when {RAPACES_DIURNES} then 'rapace_diurne'
                            when s.famille = 'Ardeidae' then 'ardeide'
                            when s.famille = 'Ciconiidae' then 'ciconiide'
                            when s.famille = 'Laridae' then 'laride'
                            when s.famille = 'Gruidae' then 'gruide'
                            else 'autre' end"""


# --- chiroptères (champs bat_* de src_lpodatas.t_c_synthese_extended, DBchiro compris) ---
CHIROPTERES = "s.ordre = 'Chiroptera'"
CHIRO_ESPECE = "s.id_rang in ('ES', 'SSES')"
CHIRO_COLONIE = "coalesce(s.bat_breed_colo, false)"
CHIRO_GITE = "(coalesce(s.bat_is_gite, false) or coalesce(s.bat_breed_colo, false))"
CHIRO_TRANSIT = "s.bat_period ilike 'transit%'"
TYPE_GITE_SQL = (
    "case when coalesce(s.bat_breed_colo, false) then 'Colonie de reproduction' else 'Gîte' end"
)


def both(*fragments: str) -> str:
    return " and ".join(f"({f})" for f in fragments)
