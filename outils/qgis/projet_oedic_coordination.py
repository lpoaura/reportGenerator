"""Construit le projet QGIS de coordination et de validation du suivi Œdicnème (PLSOC) sur le schéma pr_oedic_news.

Usage : python-qgis-ltr.bat outils/qgis/projet_oedic_coordination.py <projet_source.qgz> <projet_sortie.qgz>

Part du projet existant (fonds de carte, départements, observations Visionature) et le refait sur pr_oedic_news :
- retire les couches des anciennes vues pr_oedic ;
- ajoute les groupes « À faire », « Validation (saisie) », « Saison », « Mergin – parcelles et mesures »,
  « Historique », « Bilan de la saison », « Référentiels », « Nomenclatures » ;
- formulaires de saisie des vues éditables (v_terrain_validation_nids, v_terrain_complement_couples) : listes de
  valeurs sur les nomenclatures, champs calculés en lecture seule, chronologie du nid / du couple ;
- relations couple → nids → journal pour la consultation ; thèmes de carte par usage.
La saison affichée est celle de pr_oedic_news.f_annee_saison() (paramètre annee_saison de ref_parametre, ou année en
cours) : changer d'année = changer ce paramètre, ou le filtre de la couche. Le projet source n'est pas modifié.
Toutes les couches sont en lecture seule sauf les deux vues de saisie. Connexion : service PostgreSQL « gnlpoaura ».
"""

import os
import sys
from pathlib import Path

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsAttributeEditorContainer,
    QgsAttributeEditorField,
    QgsAttributeEditorRelation,
    QgsAttributeEditorTextElement,
    QgsCategorizedSymbolRenderer,
    QgsDataSourceUri,
    QgsDefaultValue,
    QgsEditorWidgetSetup,
    QgsFillSymbol,
    QgsLayerTreeModel,
    QgsLineSymbol,
    QgsMapThemeCollection,
    QgsMarkerSymbol,
    QgsPalLayerSettings,
    QgsProject,
    QgsRasterLayer,
    QgsReferencedRectangle,
    QgsRelation,
    QgsRendererCategory,
    QgsRuleBasedRenderer,
    QgsSingleSymbolRenderer,
    QgsTextBufferSettings,
    QgsTextFormat,
    QgsVectorLayer,
    QgsVectorLayerSimpleLabeling,
    QgsWkbTypes,
)
from qgis.PyQt.QtGui import QColor, QFont

SCHEMA = "pr_oedic_news"
SAISON = f"{SCHEMA}.f_annee_saison()"
ORTHO_IGN = (
    "contextualWMSLegend=0&crs=EPSG:3857&dpiMode=7&format=image/jpeg&layers=ORTHOIMAGERY.ORTHOPHOTOS"
    "&styles=normal&tileMatrixSet=PM"
    "&url=https://data.geopf.fr/wmts?SERVICE%3DWMTS%26REQUEST%3DGetCapabilities"
)
COULEURS_SUCCES = [
    ("Succès certain", "#1a9850"),
    ("Succès probable", "#91cf60"),
    ("En cours", "#4575b4"),
    ("Indéterminé", "#bdbdbd"),
    ("Échec probable", "#fc8d59"),
    ("Échec certain", "#d73027"),
]

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
assert src.resolve() != dst.resolve(), "la sortie doit être un autre fichier que le projet source"
QgsApplication.setPrefixPath(os.getenv("QGIS_PREFIX_PATH", r"C:\Program Files\QGIS\3_40\apps\qgis-ltr"), True)
app = QgsApplication([], False)
app.initQgis()

P = QgsProject.instance()
assert P.read(str(src)), "lecture du projet impossible"
root = P.layerTreeRoot()


# ------------------------------------------------------------------------------------------------- outils
def couche(table, nom, cle, geom="geom", type_geom=QgsWkbTypes.Point, filtre="", lecture_seule=True, resume=""):
    """Couche PostgreSQL de pr_oedic_news (service gnlpoaura, sans identifiant enregistré)."""
    u = QgsDataSourceUri()
    u.setConnection("gnlpoaura", "", "", "", QgsDataSourceUri.SslRequire)
    u.setDataSource(SCHEMA, table, geom or "", filtre, cle)
    u.setUseEstimatedMetadata(True)
    u.setParam("checkPrimaryKeyUnicity", "0")  # doublons Mergin possibles (signalés par v_ctrl_anomalies)
    if geom:
        u.setSrid("2154")
        u.setWkbType(type_geom)
    lyr = QgsVectorLayer(u.uri(False), nom, "postgres")
    assert lyr.isValid(), f"couche invalide : {table} ({lyr.error().summary()})"
    lyr.setReadOnly(lecture_seule)
    if resume:
        m = lyr.metadata()
        m.setAbstract(resume)
        lyr.setMetadata(m)
    P.addMapLayer(lyr, False)
    return lyr


def groupe(nom, parent=None, replie=False):
    g = (parent or root).addGroup(nom)
    g.setExpanded(not replie)
    return g


def ajouter(g, lyr, visible=True):
    node = g.addLayer(lyr)
    node.setItemVisibilityChecked(visible)
    node.setExpanded(False)
    return node


def point(couleur, taille=2.6, forme="circle", contour="#333333"):
    return QgsMarkerSymbol.createSimple(
        {"name": forme, "color": couleur, "size": str(taille), "outline_color": contour, "outline_width": "0.2"}
    )


def unique(lyr, symbole):
    lyr.setRenderer(QgsSingleSymbolRenderer(symbole))


def surface(remplissage, contour, epaisseur="0.5", style="solid"):
    return QgsFillSymbol.createSimple(
        {"color": remplissage, "outline_color": contour, "outline_width": epaisseur, "outline_style": style}
    )


def categories(lyr, champ, valeurs, symbole=point, autre=None):
    cats = [QgsRendererCategory(v, symbole(c), v) for v, c in valeurs]
    if autre:
        cats.append(QgsRendererCategory(None, symbole(autre), "Autre / vide"))
    lyr.setRenderer(QgsCategorizedSymbolRenderer(champ, cats))


def etiquettes(lyr, expression, taille=8, gras=False, echelle_max=None, couleur="#222222"):
    s = QgsPalLayerSettings()
    s.fieldName = expression
    s.isExpression = True
    fmt = QgsTextFormat()
    police = QFont("Arial", taille)
    police.setBold(gras)
    fmt.setFont(police)
    fmt.setSize(taille)
    fmt.setColor(QColor(couleur))
    buf = QgsTextBufferSettings()
    buf.setEnabled(True)
    buf.setSize(0.8)
    fmt.setBuffer(buf)
    s.setFormat(fmt)
    if echelle_max:
        s.scaleVisibility = True
        s.maximumScale = 1
        s.minimumScale = echelle_max
    lyr.setLabeling(QgsVectorLayerSimpleLabeling(s))
    lyr.setLabelsEnabled(True)


def alias(lyr, noms):
    for champ, libelle in noms.items():
        i = lyr.fields().indexOf(champ)
        if i >= 0:
            lyr.setFieldAlias(i, libelle)


def widget(lyr, champ, type_widget, config=None):
    i = lyr.fields().indexOf(champ)
    assert i >= 0, f"champ absent : {lyr.name()}.{champ}"
    lyr.setEditorWidgetSetup(i, QgsEditorWidgetSetup(type_widget, config or {}))


def liste(lyr, champ, ref, filtre=""):
    widget(
        lyr,
        champ,
        "ValueRelation",
        {
            "Layer": ref.id(),
            "LayerName": ref.name(),
            "LayerSource": ref.source(),
            "LayerProviderName": "postgres",
            "Key": "code",
            "Value": "libelle",
            "AllowNull": True,
            "OrderByValue": False,
            "AllowMulti": False,
            "FilterExpression": filtre,
            "UseCompleter": False,
        },
    )


def formulaire(lyr, onglets, lecture_seule_sauf=None):
    """onglets : [(titre, [éléments])] ; élément = champ, ('texte', titre, expression), ('relation', relation)
    ou ('groupe', titre, [éléments])."""
    cfg = lyr.editFormConfig()
    cfg.setLayout(Qgis.AttributeFormLayout.DragAndDrop)
    racine = cfg.invisibleRootContainer()
    racine.clear()

    def remplir(conteneur, elements):
        for el in elements:
            if isinstance(el, str):
                assert lyr.fields().indexOf(el) >= 0, f"champ absent du formulaire : {lyr.name()}.{el}"
                conteneur.addChildElement(QgsAttributeEditorField(el, lyr.fields().indexOf(el), conteneur))
            elif el[0] == "texte":
                t = QgsAttributeEditorTextElement(el[1], conteneur)
                t.setText(el[2])
                conteneur.addChildElement(t)
            elif el[0] == "relation":
                r = QgsAttributeEditorRelation(el[1], conteneur)
                r.setLabel(el[1].name())
                conteneur.addChildElement(r)
            elif el[0] == "groupe":
                g = QgsAttributeEditorContainer(el[1], conteneur)
                g.setType(Qgis.AttributeEditorContainerType.GroupBox)
                remplir(g, el[2])
                conteneur.addChildElement(g)

    for titre, elements in onglets:
        onglet = QgsAttributeEditorContainer(titre, racine)
        onglet.setType(Qgis.AttributeEditorContainerType.Tab)
        remplir(onglet, elements)
        racine.addChildElement(onglet)
    if lecture_seule_sauf is not None:
        for i, f in enumerate(lyr.fields()):
            cfg.setReadOnly(i, f.name() not in lecture_seule_sauf)
    lyr.setEditFormConfig(cfg)


def chronologie(journal, champ_lien, filtre_parent):
    """Texte de formulaire : événements du journal Mergin rattachés à l'objet (uuid bruts {…} normalisés)."""
    norm = f"lower(trim(replace(replace(\"{champ_lien}\", '{{', ''), '}}', '')))"
    return (
        "[% coalesce(aggregate(layer:='" + journal.id() + "', aggregate:='concatenate', "
        "expression:=format_date(\"date_obs\", 'dd/MM/yyyy') || ' – ' || coalesce(\"type_evenement\", '?') "
        "|| coalesce(' (' || \"nombre\" || ')', '') || coalesce(' – ' || \"observateur\", '') "
        "|| coalesce(' – ' || \"remarque\", ''), "
        f"filter:={norm} = {filtre_parent}, concatenator:='<br>', order_by:=\"date_obs\"), "
        "'Aucun événement') %]"
    )


def relation(nom, enfant, champ_enfant, parent, champ_parent):
    r = QgsRelation()
    r.setId(nom)
    r.setName(nom)
    r.setReferencingLayer(enfant.id())
    r.setReferencedLayer(parent.id())
    r.addFieldPair(champ_enfant, champ_parent)
    assert r.isValid(), f"relation invalide : {nom}"
    P.relationManager().addRelation(r)
    return r


# ------------------------------------------------------------------------------------------------- nettoyage
visionature = None
for lyr in list(P.mapLayers().values()):
    source = lyr.source()
    if "fdw_to_mergin_map" in source:
        visionature = lyr
    elif ('"pr_oedic"' in source or "pr_oedic." in source) and SCHEMA not in source:
        P.removeMapLayer(lyr.id())
# L'arbre est reconstruit. Une couche dont on retire le dernier nœud est retirée du projet (en différé, au prochain
# passage de la boucle d'événements) : les couches gardées reçoivent leur nouveau nœud AVANT le retrait des anciens.
anciens = list(root.children())
fond_couches = [n.layer() for n in root.findLayers() if n.layer() is not None and n.layer() is not visionature]
g_fonds = root.addGroup("Fonds de carte")
g_fonds.setExpanded(False)
for lyr in fond_couches + ([visionature] if visionature else []):
    g_fonds.addLayer(lyr)
    if lyr.type() == Qgis.LayerType.Vector:
        lyr.setReadOnly(True)  # Visionature est une vue sur la base Mergin : jamais d'édition depuis ce projet
for n in anciens:
    root.removeChildNode(n)

# ------------------------------------------------------------------------------------------------- nomenclatures
refs = {}
for table, nom in [
    ("ref_succes_repro", "Succès de reproduction"),
    ("ref_cause_echec", "Causes de fin / d'échec"),
    ("ref_milieu", "Milieux"),
    ("ref_degre_menace", "Degrés de menace"),
    ("ref_type_protection", "Types de protection"),
    ("ref_stade_repro", "Stades de reproduction"),
    ("ref_parametre", "Paramètres (année suivie…)"),
]:
    refs[table] = couche(table, nom, "cle" if table == "ref_parametre" else "code", geom=None)

# ------------------------------------------------------------------------------- journal (utilisé par les formulaires)
journal = couche(
    "v_mergin_observations",
    "Journal des observations et événements",
    "id_journal",
    filtre=f'"annee" = {SAISON}',
    resume="Observations d'individus et événements de nids saisis dans Mergin (saison suivie).",
)
journal.setRenderer(
    QgsCategorizedSymbolRenderer(
        "source",
        [
            QgsRendererCategory("Observation", point("#9e9ac8", 1.6), "Observation d'individus"),
            QgsRendererCategory("Événement de nid", point("#fdae6b", 1.6, "square"), "Événement de nid"),
        ],
    )
)

# ------------------------------------------------------------------------------------------------- saison
couples = couche(
    "v_terrain_couples",
    "Couples de la saison",
    "cle_couple",
    resume="Couples Mergin de la saison suivie : statut, synthèse des nids, secteur, mesure, compléments.",
)
categories(
    couples,
    "statut_nidification",
    [("Nicheur certain", "#762a83"), ("Nicheur probable", "#af8dc3"), ("Nicheur possible", "#e7d4e8")],
    symbole=lambda c: point(c, 3.4, "square"),
    autre="#ffffff",
)
couples.setDisplayExpression('"code_couple"')
nids = couche(
    "v_terrain_nids",
    "Nids de la saison",
    "cle_nid",
    resume="Nids Mergin de la saison suivie : état, succès calculé, protection, validation.",
)
categories(nids, "succes_repro", COULEURS_SUCCES, symbole=lambda c: point(c, 2.8, "triangle"))
nids.setDisplayExpression('"code_nid"')
isolees = couche(
    "v_terrain_observations_isolees",
    "Observations non rattachées à un couple",
    "id_obs",
    filtre=f'extract(year from "date_obs") = {SAISON}',
)
unique(isolees, point("#f16913", 3, "cross2", "#f16913"))
if visionature:
    visionature.setSubsetString(f'"date" >= make_date({SAISON}, 1, 1)')
    visionature.setName("Observations Visionature (saison)")
synthese = couche(
    "mv_synthese_oedicneme",
    "Données Faune-France / GeoNature (saison)",
    "id_synthese",
    filtre=f'"annee" = {SAISON}',
    resume="Données Œdicnème de la synthèse GeoNature autour de la zone d'étude (hors suivi Mergin). "
    "Vue matérialisée : mise à jour par f_rafraichir_analyses().",
)
categories(
    synthese,
    "oiso_statut_nidif",
    [("Certain", "#3f007d"), ("Probable", "#6a51a3"), ("Possible", "#9e9ac8"), ("Espèce absente", "0,0,0,0")],
    symbole=lambda c: point(c, 2, "circle", "#54278f"),
    autre="#dadaeb",
)

alias(
    nids,
    {
        "code_nid": "Code nid",
        "code_couple": "Code couple",
        "etat_nid": "État",
        "succes_repro": "Succès calculé",
        "succes_repro_valide": "Succès validé",
        "est_valide": "Validé",
        "nom_secteur": "Secteur",
        "id_mesure_compensatoire": "Mesure compensatoire",
        "jours_depuis_dernier_passage": "Jours sans passage",
    },
)
alias(
    couples,
    {
        "code_couple": "Code couple",
        "statut_nidification": "Statut",
        "succes_repro": "Meilleur succès",
        "nom_secteur": "Secteur",
        "jours_depuis_dernier_contact": "Jours sans contact",
    },
)
nids.setMapTipTemplate(
    '<b>[% "code_nid" %]</b><br>[% "etat_nid" %] – [% "succes_repro" %]<br>'
    "Dernier passage : [% format_date(\"date_dernier_passage\", 'dd/MM') %]"
    "[% if(\"est_valide\", '<br><b>Validé : ' || \"succes_repro_valide\" || '</b>', '') %]"
)
couples.setMapTipTemplate(
    '<b>[% "code_couple" %]</b> – [% "statut_nidification" %]<br>'
    '[% "nb_nids" %] nid(s) – [% "succes_repro" %]<br>[% "nom_commune" %]'
)

# relations de consultation (uuid bruts des deux côtés)
r_couple_nids = relation("Nids du couple", nids, "uuid_couple", couples, "uuid_couple")
r_couple_journal = relation("Journal du couple", journal, "uuid_couple", couples, "uuid_couple")
r_nid_journal = relation("Événements du nid", journal, "uuid_nid", nids, "uuid_nid")
formulaire(
    couples,
    [
        (
            "Couple",
            [
                "code_couple",
                "annee",
                "nom_commune",
                "nom_secteur",
                "id_mesure_compensatoire",
                "statut_nidification",
                "succes_repro",
                "etat_dernier_nid",
                "date_premiere_obs",
                "date_derniere_obs",
                "jours_depuis_dernier_contact",
                "nb_observations",
                "max_individus_observes",
                "bagues_adultes",
                "protection_en_place",
                "milieu",
                "culture",
                "lieu_dit",
                "degre_menace",
                "remarque",
            ],
        ),
        ("Nids", [("relation", r_couple_nids)]),
        ("Journal", [("relation", r_couple_journal)]),
    ],
)
formulaire(
    nids,
    [
        (
            "Nid",
            [
                "code_nid",
                "code_couple",
                "annee",
                "nom_commune",
                "nom_secteur",
                "id_mesure_compensatoire",
                "milieu",
                "numero_nichee",
                "type_ponte",
                "etat_nid",
                "succes_repro",
                "succes_repro_valide",
                "est_valide",
                "type_protection",
                "protection_en_place",
                "nb_oeufs",
                "nb_eclos_min",
                "nb_poussins_max",
                "nb_jeunes_envol",
                "bagues_poussins",
            ],
        ),
        (
            "Dates",
            [
                "date_decouverte",
                "date_premiere_couvaison",
                "date_derniere_couvaison",
                "date_eclosion_au_plus_tard",
                "date_eclosion_constatee",
                "date_derniere_obs_poussins",
                "date_envol",
                "date_echec",
                "date_dernier_passage",
                "jours_depuis_dernier_passage",
                "mayfield_jours_exposition",
                "mayfield_jours_elevage",
            ],
        ),
        ("Événements", [("relation", r_nid_journal)]),
    ],
)

# ------------------------------------------------------------------------------------------------- validation (saisie)
validation = couche(
    "v_terrain_validation_nids",
    "Validation des nids (saisie)",
    "uuid_nid",
    filtre=f'"annee" = {SAISON}',
    lecture_seule=False,
    resume="Saisie experte du succès, des jeunes à l'envol, des jours d'exposition Mayfield et de la "
    "cause : modifier les champs « validés ». Vider ces champs supprime la validation.",
)
validation.setRenderer(QgsRuleBasedRenderer(QgsRuleBasedRenderer.Rule(None)))
regles = validation.renderer().rootRule()
for titre, expr, coul in [
    ("Validé", '"est_valide"', "#1a9850"),
    ("À valider (saison terminée)", 'NOT "est_valide" AND "saison_terminee"', "#d73027"),
    ("En cours (saison non terminée)", 'NOT "est_valide" AND NOT "saison_terminee"', "#969696"),
]:
    regles.appendChild(QgsRuleBasedRenderer.Rule(point(coul, 3.6, "circle", "#000000"), 0, 0, expr, titre))
validation.setDisplayExpression('"code_nid"')
liste(validation, "val_succes_repro", refs["ref_succes_repro"], "\"code\" <> 'en_cours'")
liste(validation, "val_cause_fin", refs["ref_cause_echec"])
widget(
    validation, "val_nb_jeunes_envol", "Range", {"Min": 0, "Max": 10, "Step": 1, "AllowNull": True, "Style": "SpinBox"}
)
widget(
    validation,
    "val_mayfield_jours",
    "Range",
    {"Min": 0, "Max": 120, "Step": 0.5, "Precision": 1, "AllowNull": True, "Style": "SpinBox"},
)
widget(validation, "val_commentaire", "TextEdit", {"IsMultiline": True})
widget(
    validation,
    "val_date_validation",
    "DateTime",
    {"field_format": "yyyy-MM-dd", "display_format": "dd/MM/yyyy", "calendar_popup": True, "allow_null": True},
)
for champ, expr in [
    ("val_valide_par", 'coalesce("val_valide_par", @user_full_name)'),
    ("val_date_validation", 'coalesce("val_date_validation", now())'),
]:
    validation.setDefaultValueDefinition(validation.fields().indexOf(champ), QgsDefaultValue(expr, True))
alias(
    validation,
    {
        "code_nid": "Code nid",
        "code_couple": "Code couple",
        "nom_commune": "Commune",
        "nom_secteur": "Secteur",
        "numero_nichee": "N° de nichée",
        "etat_nid": "État du nid",
        "saison_terminee": "Saison terminée",
        "succes_repro_calcule": "Succès calculé",
        "nb_jeunes_envol_calcule": "Jeunes à l'envol (calcul)",
        "mayfield_jours_calcule": "Jours d'exposition (incubation, calcul)",
        "mayfield_jours_elevage_calcule": "Jours d'exposition (élevage, calcul)",
        "cause_saisie_mergin": "Cause saisie (Mergin)",
        "val_succes_repro": "Succès VALIDÉ",
        "val_nb_jeunes_envol": "Jeunes à l'envol VALIDÉS",
        "val_mayfield_jours": "Jours d'exposition Mayfield VALIDÉS",
        "val_cause_fin": "Cause de fin VALIDÉE",
        "val_commentaire": "Commentaire",
        "val_valide_par": "Validé par",
        "val_date_validation": "Date de validation",
        "est_valide": "Validé",
        "date_decouverte": "Découverte",
        "date_premiere_couvaison": "1re couvaison",
        "date_derniere_couvaison": "Dernière couvaison",
        "date_eclosion_constatee": "Éclosion constatée",
        "date_derniere_obs_poussins": "Dernière obs. poussins",
        "date_envol": "Envol",
        "date_echec": "Échec",
        "date_dernier_passage": "Dernier passage",
        "type_protection": "Protection",
        "nb_evenements": "Nb d'événements",
    },
)
formulaire(
    validation,
    [
        (
            "Validation",
            [
                (
                    "groupe",
                    "Valeurs calculées (lecture seule)",
                    [
                        "code_nid",
                        "etat_nid",
                        "succes_repro_calcule",
                        "nb_jeunes_envol_calcule",
                        "mayfield_jours_calcule",
                        "mayfield_jours_elevage_calcule",
                        "cause_saisie_mergin",
                    ],
                ),
                (
                    "groupe",
                    "Validation experte",
                    [
                        "val_succes_repro",
                        "val_nb_jeunes_envol",
                        "val_mayfield_jours",
                        "val_cause_fin",
                        "val_commentaire",
                        "val_valide_par",
                        "val_date_validation",
                    ],
                ),
                ("texte", "Chronologie du nid", chronologie(journal, "uuid_nid", "attribute(@parent, 'uuid_nid')")),
            ],
        ),
        (
            "Nid",
            [
                "code_couple",
                "annee",
                "nom_commune",
                "nom_secteur",
                "numero_nichee",
                "saison_terminee",
                "type_protection",
                "nb_evenements",
                "est_valide",
            ],
        ),
        (
            "Dates",
            [
                "date_decouverte",
                "date_premiere_couvaison",
                "date_derniere_couvaison",
                "date_eclosion_constatee",
                "date_derniere_obs_poussins",
                "date_envol",
                "date_echec",
                "date_dernier_passage",
            ],
        ),
    ],
    lecture_seule_sauf={
        "val_succes_repro",
        "val_nb_jeunes_envol",
        "val_mayfield_jours",
        "val_cause_fin",
        "val_commentaire",
        "val_valide_par",
        "val_date_validation",
    },
)
validation.setMapTipTemplate(
    '<b>[% "code_nid" %]</b><br>Calculé : [% "succes_repro_calcule" %]'
    "[% if(\"est_valide\", '<br><b>Validé : ' || \"val_succes_repro\" || '</b>', "
    "'<br><i>non validé</i>') %]"
)

complement = couche(
    "v_terrain_complement_couples",
    "Compléments des couples (saisie)",
    "uuid_couple",
    filtre=f'"annee" = {SAISON}',
    lecture_seule=False,
    resume="Saisie des informations absentes de Mergin : milieu, culture, lieu-dit, degré de menace, "
    "statut validé. Vider ces champs supprime le complément.",
)
complement.setRenderer(QgsRuleBasedRenderer(QgsRuleBasedRenderer.Rule(None)))
regles = complement.renderer().rootRule()
for titre, expr, coul in [("Complété", '"est_complete"', "#2166ac"), ("À compléter", 'NOT "est_complete"', "#f4a582")]:
    regles.appendChild(QgsRuleBasedRenderer.Rule(point(coul, 3.6, "square", "#000000"), 0, 0, expr, titre))
complement.setDisplayExpression('"code_couple"')
liste(complement, "val_milieu", refs["ref_milieu"])
liste(complement, "val_degre_menace", refs["ref_degre_menace"])
widget(
    complement,
    "val_statut_nidification",
    "ValueMap",
    {
        "map": [
            {"Nicheur certain": "Nicheur certain"},
            {"Nicheur probable": "Nicheur probable"},
            {"Nicheur possible": "Nicheur possible"},
        ]
    },
)
widget(complement, "val_commentaire", "TextEdit", {"IsMultiline": True})
complement.setDefaultValueDefinition(
    complement.fields().indexOf("val_saisi_par"), QgsDefaultValue('coalesce("val_saisi_par", @user_full_name)', True)
)
alias(
    complement,
    {
        "code_couple": "Code couple",
        "nom_commune": "Commune",
        "nom_secteur": "Secteur",
        "id_mesure_compensatoire": "Mesure compensatoire",
        "zonage_plu": "Zonage PLU",
        "statut_nidification_calcule": "Statut calculé",
        "nb_nids": "Nb de nids",
        "val_milieu": "Milieu",
        "val_culture": "Culture / couvert",
        "val_lieu_dit": "Lieu-dit",
        "val_degre_menace": "Degré de menace",
        "val_statut_nidification": "Statut VALIDÉ",
        "val_commentaire": "Commentaire",
        "val_saisi_par": "Saisi par",
        "est_complete": "Complété",
    },
)
formulaire(
    complement,
    [
        (
            "Compléments",
            [
                (
                    "groupe",
                    "Couple (lecture seule)",
                    [
                        "code_couple",
                        "nom_commune",
                        "nom_secteur",
                        "id_mesure_compensatoire",
                        "zonage_plu",
                        "statut_nidification_calcule",
                        "nb_nids",
                        "date_premiere_obs",
                        "date_derniere_obs",
                    ],
                ),
                (
                    "groupe",
                    "À compléter",
                    [
                        "val_milieu",
                        "val_culture",
                        "val_lieu_dit",
                        "val_degre_menace",
                        "val_statut_nidification",
                        "val_commentaire",
                        "val_saisi_par",
                    ],
                ),
                (
                    "texte",
                    "Chronologie du couple",
                    chronologie(journal, "uuid_couple", "attribute(@parent, 'uuid_couple')"),
                ),
            ],
        )
    ],
    lecture_seule_sauf={
        "val_milieu",
        "val_culture",
        "val_lieu_dit",
        "val_degre_menace",
        "val_statut_nidification",
        "val_commentaire",
        "val_saisi_par",
    },
)

# ------------------------------------------------------------------------------------------------- à faire / contrôle
a_visiter = couche(
    "v_terrain_a_visiter",
    "À visiter en priorité",
    '"type_objet","cle","motif"',
    resume="Éclosion attendue, nid agricole non protégé, passage en retard, couple sans nid sans "
    "contact récent (délais dans ref_parametre).",
)
categories(
    a_visiter,
    "motif",
    [
        ("Éclosion attendue", "#e41a1c"),
        ("Nid agricole non protégé", "#ff7f00"),
        ("Passage en retard", "#984ea3"),
        ("Couple sans nid, sans contact récent", "#377eb8"),
    ],
    symbole=lambda c: point(c, 5, "star", "#000000"),
)
etiquettes(a_visiter, "\"code\" || coalesce(' – ' || \"jours_sans_passage\" || ' j', '')", taille=7, echelle_max=25000)
anomalies = couche(
    "v_ctrl_anomalies",
    "Anomalies de saisie",
    "id_controle",
    filtre=f'"annee" = {SAISON} OR "annee" IS NULL',
    resume="Contrôles de la saisie Mergin et des validations : BLOQUANT > IMPORTANT > A_VERIFIER.",
)
categories(
    anomalies,
    "gravite",
    [("BLOQUANT", "#b2182b"), ("IMPORTANT", "#ef8a62"), ("A_VERIFIER", "#fddbc7")],
    symbole=lambda c: point(c, 4.2, "diamond", "#000000"),
)
anomalies.setDisplayExpression('"code_anomalie" || \' – \' || "code_lisible"')
anomalies.setMapTipTemplate('<b>[% "gravite" %] – [% "code_anomalie" %]</b><br>[% "message" %]')

# ----------------------------------------------------------------------------------- Mergin parcelles / mesures
parcelles = couche(
    "v_mergin_parcelles",
    "Parcelles Mergin",
    "id_parcelle",
    type_geom=QgsWkbTypes.MultiPolygon,
    resume="Parcelles saisies dans Mergin (affichées à partir du 1:25 000).",
)
unique(parcelles, surface("0,0,0,0", "#8c510a", "0.3"))
parcelles.setScaleBasedVisibility(True)
parcelles.setMinimumScale(25000)
suivis_mesure = couche(
    "v_mergin_suivis_mesure",
    "Suivis des mesures (saison)",
    "id_mesure",
    type_geom=QgsWkbTypes.MultiPolygon,
    filtre=f'"annee" = {SAISON}',
)
unique(suivis_mesure, surface("27,120,55,90", "#1b7837"))
suivis_parcelle = couche(
    "v_mergin_suivis_parcelle",
    "Suivis des parcelles (saison)",
    "id_suivi",
    type_geom=QgsWkbTypes.MultiPolygon,
    filtre=f'"annee" = {SAISON}',
)
categories(
    suivis_parcelle,
    "favorable",
    [("oui", "#a6d96a"), ("moyennement", "#ffffbf"), ("non", "#fdae61")],
    symbole=lambda c: QgsFillSymbol.createSimple({"color": c, "outline_color": "#555555", "outline_width": "0.2"}),
    autre="#e0e0e0",
)
regroupements = couche(
    "v_mergin_regroupements",
    "Regroupements (saison)",
    "id_regroupement",
    type_geom=QgsWkbTypes.MultiPolygon,
    filtre=f'"annee" = {SAISON}',
)
unique(regroupements, surface("117,107,177,120", "#54278f", "0.6"))
etiquettes(
    regroupements,
    "format_date(\"date_regroupement\", 'dd/MM') || ' : ' || " "coalesce(to_string(\"effectif\"), '?')",
    taille=8,
    gras=True,
)

# ------------------------------------------------------------------------------------------------- historique
couples_n1 = couche(
    "mv_ana_couple",
    "Couples de l'année précédente",
    "cle_couple",
    filtre=f'"annee" = {SAISON} - 1',
    resume="Couples de l'année N-1 (historique ou Mergin), utiles pour orienter les prospections. "
    "Vue matérialisée : mise à jour par f_rafraichir_analyses().",
)
unique(couples_n1, point("0,0,0,0", 4.2, "circle", "#525252"))
couples_tous = couche(
    "mv_ana_couple",
    "Couples depuis 2015 (toutes années)",
    "cle_couple",
    resume="Tous les couples 2015 → N (historique + Mergin). Vue matérialisée.",
)
unique(couples_tous, point("#9e9e9e", 1.8))
nids_tous = couche(
    "mv_ana_nid",
    "Nids depuis 2015 (toutes années)",
    "cle_nid",
    resume="Tous les nids 2015 → N, succès validé (historique) ou validé/calculé (Mergin).",
)
categories(
    nids_tous,
    "succes_repro",
    [
        ("succes_certain", "#1a9850"),
        ("succes_probable", "#91cf60"),
        ("en_cours", "#4575b4"),
        ("indetermine", "#bdbdbd"),
        ("echec_probable", "#fc8d59"),
        ("echec_certain", "#d73027"),
    ],
    symbole=lambda c: point(c, 2, "triangle"),
    autre="#ffffff",
)
individus = couche("v_ana_individu", "Individus bagués (toutes années)", "bague", geom=None)

# ------------------------------------------------------------------------------------------------- bilan (tables)
bilan = [
    couche("v_rap_bilan_annuel", "Bilan annuel (toutes années)", "annee", geom=None),
    couche(
        "v_rap_secteur", "Bilan par secteur (saison)", '"annee","nom_secteur"', geom=None, filtre=f'"annee" = {SAISON}'
    ),
    couche(
        "v_rap_succes",
        "Succès de reproduction (saison)",
        '"annee","succes_reproduction"',
        geom=None,
        filtre=f'"annee" = {SAISON}',
    ),
    couche("v_rap_mayfield", "Mayfield (toutes années)", "annee", geom=None),
]

# ------------------------------------------------------------------------------------------------- référentiels
secteurs = couche("ref_secteur", "Secteurs", "id_secteur", type_geom=QgsWkbTypes.MultiPolygon)
unique(secteurs, surface("0,0,0,0", "#252525", "0.6", "dash"))
etiquettes(secteurs, '"nom_secteur"', taille=10, gras=True, couleur="#252525")
mesures = couche("ref_mesure_compensatoire", "Mesures compensatoires", "id_site", type_geom=QgsWkbTypes.MultiPolygon)
unique(mesures, surface("90,174,97,60", "#1b7837", "0.6"))
etiquettes(mesures, 'coalesce("nom_projet", "id_site")', taille=8, echelle_max=50000, couleur="#1b7837")
zone = couche("ref_zone_etude", "Zone d'étude", "id_zone", type_geom=QgsWkbTypes.MultiPolygon)
unique(zone, surface("0,0,0,0", "#000000", "1"))
plu = couche(
    "ref_plu",
    "PLU – zones U et AU",
    "id_plu",
    type_geom=QgsWkbTypes.MultiPolygon,
    filtre="\"zone_simplifiee\" IN ('U', 'AU')",
)
categories(
    plu,
    "zone_simplifiee",
    [("U", "227,26,28,70"), ("AU", "253,141,60,70")],
    symbole=lambda c: surface(c, "0,0,0,0", "0", "no"),
)
prospection = couche("ref_zone_prospection", "Zones de prospection", "id_zone", type_geom=QgsWkbTypes.MultiPolygon)
unique(prospection, surface("0,0,0,0", "#6a51a3", "0.4", "dot"))
itineraires = couche(
    "ref_itineraire", "Itinéraires de prospection", "id_itineraire", type_geom=QgsWkbTypes.MultiLineString
)
unique(itineraires, QgsLineSymbol.createSimple({"line_color": "#6a51a3", "line_width": "0.4"}))

# ------------------------------------------------------------------------------------------------- arbre des couches
g_faire = groupe("À faire")
ajouter(g_faire, a_visiter)
ajouter(g_faire, anomalies)
ajouter(g_faire, isolees, visible=False)
g_saisie = groupe("Validation (saisie)")
ajouter(g_saisie, validation, visible=False)
ajouter(g_saisie, complement, visible=False)
g_saison = groupe("Saison suivie")
ajouter(g_saison, nids)
ajouter(g_saison, couples)
ajouter(g_saison, journal, visible=False)
ajouter(g_saison, couples_n1)
ajouter(g_saison, synthese, visible=False)
if visionature:
    ajouter(g_saison, visionature, visible=False)
    g_fonds.removeChildNode(g_fonds.findLayer(visionature.id()))
g_mergin = groupe("Mergin – parcelles, mesures, regroupements", replie=True)
for lyr in (regroupements, suivis_mesure, suivis_parcelle, parcelles):
    ajouter(g_mergin, lyr, visible=False)
g_hist = groupe("Historique (toutes années)", replie=True)
for lyr in (nids_tous, couples_tous, individus):
    ajouter(g_hist, lyr, visible=False)
g_bilan = groupe("Bilan de la saison (tables)", replie=True)
for lyr in bilan:
    ajouter(g_bilan, lyr)
g_ref = groupe("Référentiels", replie=True)
ajouter(g_ref, secteurs)
ajouter(g_ref, mesures)
ajouter(g_ref, zone)
ajouter(g_ref, plu, visible=False)
ajouter(g_ref, prospection, visible=False)
ajouter(g_ref, itineraires, visible=False)
ortho = QgsRasterLayer(ORTHO_IGN, "Orthophoto IGN", "wms")
if ortho.isValid():
    P.addMapLayer(ortho, False)
    g_fonds.insertLayer(0, ortho).setItemVisibilityChecked(False)
else:
    print("[AVERTISSEMENT] orthophoto IGN inaccessible : couche non ajoutée")
# le groupe des fonds (créé en premier) passe en bas de l'arbre : la copie garde les couches dans l'arbre
root.addChildNode(g_fonds.clone())
root.removeChildNode(g_fonds)
g_nomenc = groupe("Nomenclatures (listes de saisie)", replie=True)
for lyr in refs.values():
    ajouter(g_nomenc, lyr)

# ------------------------------------------------------------------------------------------------- thèmes de carte
modele = QgsLayerTreeModel(root)
themes = P.mapThemeCollection()


def theme(nom, visibles):
    for node in root.findLayers():
        node.setItemVisibilityChecked(node.layer() in visibles)
    for g in root.findGroups(True):
        g.setItemVisibilityChecked(True)
    themes.insert(nom, QgsMapThemeCollection.createThemeFromCurrentState(root, modele))


base = [secteurs, mesures, zone] + fond_couches
theme("4 - Historique", base + [couples_tous, nids_tous, plu])
theme("3 - Contrôle des saisies", base + [anomalies, isolees, nids, couples])
theme("2 - Validation des succès", base + [validation, complement])
theme("1 - Coordination terrain", base + [a_visiter, nids, couples, couples_n1])

P.setTitle("Suivi Œdicnème (PLSOC) – coordination et validation")
emprise = secteurs.extent()
emprise.grow(1500)
P.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(emprise, secteurs.crs()))
dst.parent.mkdir(parents=True, exist_ok=True)
assert P.write(str(dst)), "écriture du projet impossible"
print(f"Projet écrit : {dst} ({len(P.mapLayers())} couches, {len(themes.mapThemes())} thèmes)")
app.exitQgis()
