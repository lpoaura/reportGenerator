"""Texte de la section « État des connaissances par maille » des templates Word (natura2000, generique, eolien).

paragraphes(...) -> liste de (type, texte) : "titre", "question" (intertitre en gras), "texte", "jaune" (texte
d'expert à rédiger), "carte" (placeholder d'image seul dans son paragraphe), "legende" (Figure n : ...),
"bloc" (placeholder de tableau ou d'atlas seul dans son paragraphe).
Les chiffres et seuils viennent des briques communes (placeholders) : rien n'est écrit en dur ici.
"""


def paragraphes(titre="État des connaissances par groupe taxonomique", zone="le site", de_la_zone="du site",
                groupes="", porter_a_connaissance=True, legendes_cartes=True):
    """zone : « le site » / « la zone d'étude » ; groupes : précision sur les groupes étudiés (éolien...)."""
    p = [("titre", titre)]
    if porter_a_connaissance:
        p.append(("jaune", "[Section destinée au porter à connaissance : à supprimer si elle n'est pas transmise au "
                           "client.]"))
    p += [
        ("texte", f"Cette section ne mesure pas la biodiversité {de_la_zone} : elle décrit ce que les données "
                  "disponibles permettent d'en dire. Une maille sans donnée, ou avec peu d'espèces, n'est pas "
                  "forcément pauvre : elle peut simplement avoir été peu prospectée. "
                  + (f"Les analyses portent sur {groupes}. " if groupes else "")
                  + "Elles reposent sur une grille de mailles de 1 km × 1 km couvrant {{CONNAISSANCE_EMPRISE}}, "
                  "identique sur toutes les cartes, et répondent à trois questions : où a-t-on prospecté ? "
                  "connaît-on bien chaque groupe à cet endroit ? où se trouvent les espèces à enjeux ?"),
        ("question", "Où a-t-on prospecté ?"),
        ("texte", "Deux indicateurs décrivent l'effort de prospection, tous groupes étudiés confondus. Le nombre de "
                  "données par maille reflète l'activité d'observation, mais il est gonflé par les inventaires "
                  "intensifs ou les comptages répétés en un même lieu. Le nombre de jours d'observation (nombre de "
                  "dates différentes avec au moins une donnée) mesure mieux l'effort réel : une maille visitée "
                  "30 jours différents est mieux connue qu'une maille où 100 données ont été saisies lors d'une "
                  "seule sortie. "
                  "Les mailles grises ne comptent qu'une donnée (ou un seul jour d'observation) : leur connaissance "
                  "est jugée insuffisante. Les mailles blanches n'ont aucune donnée."),
        ("carte", "Connaissance_effort_donnees"),
    ]
    if legendes_cartes:
        p.append(("legende", "Nombre de données par maille de 1 km"))
    p.append(("carte", "Connaissance_effort_jours"))
    if legendes_cartes:
        p.append(("legende", "Nombre de jours d'observation par maille de 1 km"))
    p += [
        ("question", "Connaît-on bien chaque groupe ?"),
        ("texte", "Pour chaque groupe taxonomique, le nombre d'espèces observées dans une maille est rapporté au "
                  "nombre d'espèces du même groupe connues dans un rayon de {{POOL_LOCAL_KM}} km autour "
                  f"{de_la_zone} (« espèces locales »). Cette référence est réaliste : elle ne compte que des espèces "
                  "présentes dans le même contexte géographique, alors qu'une référence régionale inclurait des "
                  "espèces de montagne ou de plaine absentes du secteur et pénaliserait les groupes riches en espèces "
                  "localisées. Le tableau suivant donne, par groupe, le nombre d'espèces connues dans "
                  f"{zone} et dans l'emprise des mailles, et la part qu'elles représentent des espèces locales ; le "
                  "nombre d'espèces connues en région est donné pour mémoire. Il indique aussi le nombre de mailles "
                  "renseignées (dont celles avec moins de {{SEUIL_PEU_DONNEES}} données), le nombre médian de jours "
                  "d'observation par maille et si le groupe est cartographié."),
        ("bloc", "TABLE_CONNAISSANCE_GROUPES"),
        ("texte", "{{TEXTE_GROUPES_CARTOGRAPHIES}}"),
        ("question", "Comment lire les cartes par groupe ?"),
        ("texte", "Deux cartes sont présentées pour chaque groupe cartographié, sur la même emprise et la même "
                  "grille."),
        ("texte", "La carte « Part des espèces locales » colore chaque maille selon la part des espèces locales du "
                  "groupe qui y ont été observées, du violet (moins de 10 %) au jaune (plus de 75 %). Une maille "
                  "jaune réunit une grande partie des espèces connues du secteur ; une maille violette n'en compte "
                  "qu'une petite part, soit parce qu'elle est peu favorable au groupe, soit parce que le groupe y a "
                  "été peu recherché."),
        ("texte", "Les mailles hachurées comptent moins de {{SEUIL_PEU_DONNEES}} données du groupe : leur valeur "
                  "repose sur une observation isolée et doit être lue avec prudence."),
        ("texte", "Le chiffre dans un rond rouge indique le nombre d'espèces à enjeux observées dans la maille : "
                  "espèces Natura 2000 (annexe I de la directive Oiseaux, annexe II de la directive Habitats Faune "
                  "Flore) ou espèces quasi menacées à en danger critique (NT, VU, EN, CR) sur la liste rouge "
                  "régionale, à défaut nationale. Pour les oiseaux, seules les espèces nicheuses (nidification "
                  "possible, probable ou certaine) sont comptées."),
        ("texte", "La carte « Richesse et prospection » croise, grâce à une légende à double entrée, la part des "
                  "espèces locales et l'effort de prospection du groupe dans la maille (nombre de jours avec au moins "
                  "une donnée du groupe). {{TEXTE_LECTURE_CROISEE}} Les quatre coins de la légende correspondent à "
                  "quatre situations :"),
        ("texte", "– gris clair (peu d'espèces, peu de jours) : la maille a été peu prospectée pour ce groupe, la "
                  "connaissance est à compléter ;"),
        ("texte", "– bleu (peu d'espèces malgré une prospection régulière) : la maille est probablement peu "
                  "favorable au groupe, ou les prospections y ont ciblé d'autres espèces ;"),
        ("texte", "– rouge (beaucoup d'espèces avec peu de jours) : la maille est riche mais sa connaissance repose "
                  "sur peu de sorties, des prospections complémentaires y apporteraient sans doute de nouvelles "
                  "espèces ;"),
        ("texte", "– brun foncé (beaucoup d'espèces et prospection régulière) : la maille est riche et bien connue."),
        ("texte", "Ces cartes décrivent l'état de la connaissance et non la valeur écologique des mailles. Elles se "
                  "lisent avec les cartes d'effort ci-dessus : une zone peu prospectée ne peut pas être jugée "
                  "pauvre. Les suivis ciblés (comptages, protocoles) concentrent aussi l'effort sur quelques "
                  "mailles."),
        ("bloc", "ATLAS_CONNAISSANCE_GROUPES"),
        ("jaune", "[Commentaire de l'expert : groupes et secteurs les moins connus, prospections à prévoir.]"),
    ]
    return p
