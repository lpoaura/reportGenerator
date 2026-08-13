# analysis/environmental_zones/zone_presentation.py

ZONE_PRESENTATION = {
    "ZNIEFF1": {
        "titre": "Secteur à forte valeur biologique reconnue",
        "texte": (
            "Un secteur de taille généralement restreinte, homogène du point "
            "de vue écologique, identifié pour la présence d'espèces ou "
            "d'habitats remarquables, rares ou menacés. C'est souvent un "
            "véritable noyau de biodiversité pour le secteur : zone de "
            "reproduction, station botanique, habitat refuge..."
        ),
    },
    "ZNIEFF2": {
        "titre": "Grand ensemble naturel fonctionnel",
        "texte": (
            "Un ensemble naturel de plus grande taille, riche et peu modifié, "
            "ou offrant des potentialités biologiques importantes. Il joue "
            "souvent un rôle de continuité écologique entre plusieurs "
            "secteurs à enjeux (corridors, zones tampons, mosaïque "
            "d'habitats)."
        ),
    },
    "APB": {
        "titre": "Site géré pour la survie d'une ou plusieurs espèces précises",
        "texte": (
            "Un périmètre délimité autour de ce qui est indispensable à "
            "l'alimentation, la reproduction, le repos ou la survie d'une ou "
            "plusieurs espèces ciblées (colonie de chauves-souris, site de "
            "nidification, frayère...). L'enjeu est concret et localisé : "
            "préserver ce lieu précis, pas l'ensemble du territoire."
        ),
    },
    "RNN": {
        "titre": "Sanctuaire de préservation à l'échelle nationale",
        "texte": (
            "Un espace jugé d'intérêt national pour la conservation de la "
            "faune, la flore, le sol, les eaux ou le patrimoine géologique. "
            "La tranquillité du site est souvent l'enjeu central : c'est un "
            "lieu où la présence humaine et les activités sont volontairement "
            "limitées pour permettre à la faune de s'y maintenir durablement."
        ),
    },
    "RNR": {
        "titre": "Sanctuaire de préservation à l'échelle régionale",
        "texte": (
            "Même logique que la réserve naturelle nationale, portée cette "
            "fois par la Région : préserver un espace naturel remarquable et "
            "sa tranquillité, à une échelle plus locale."
        ),
    },
    "Natura 2000": {
        "titre": "Site du réseau écologique européen",
        "texte": (
            "Un site reconnu pour la présence d'habitats ou d'espèces "
            "d'intérêt communautaire (Directive Habitats-Faune-Flore ou "
            "Directive Oiseaux), intégré à un réseau écologique à l'échelle "
            "européenne. L'objectif est de maintenir ces habitats et "
            "espèces dans un bon état de conservation sur le long terme."
        ),
    },
    "PNR": {
        "titre": "Territoire habité au projet de préservation partagé",
        "texte": (
            "Un territoire vivant, souvent vaste, où population, activités "
            "économiques et patrimoine naturel/paysager coexistent. "
            "L'enjeu n'est pas la mise sous cloche mais un projet de "
            "territoire partagé entre préservation et développement local."
        ),
    },
}


def build_zone_presentation_text(pivoted_data):
    """Génère un texte de présentation (objectif/réalité) des zonages
    effectivement présents dans la zone d'étude ou le buffer."""
    present_types = [
        entry["type_code"]
        for entry in pivoted_data
        if entry.get("zone_etude", 0) > 0 or entry.get("buffer", 0) > 0
    ]

    if not present_types:
        return ""

    blocs = []
    for type_code in present_types:
        info = ZONE_PRESENTATION.get(type_code)
        if not info:
            continue
        blocs.append(f"{type_code} : {info['titre']} \n{info['texte']}")

    if not blocs:
        return ""

    return "\n\n".join(blocs)