"""template_indicateurs.py <template_plsoc.docx> <sortie.docx> : construit le template du rapport d'exécution annuel
« Indicateurs de biodiversité en Auvergne-Rhône-Alpes » (dossier indicateurs).

Reprend la page de garde, l'historique des versions, la charte et le sommaire (champ TOC) du template PLSOC, supprime
son contenu et écrit la trame (conception §5.9) : chiffres clés, contexte, une section par protocole (même plan pour
tous, placeholders préfixés STOC_, SHOC_, STOM_, STERF_, POPR_, POPA_, section {{#code}} … {{/code}}), conclusion,
annexes. Textes fixes repris du rapport 2025 (à relire par les coordinateurs) ; paragraphes à rédiger surlignés en
jaune. Le template source n'est pas modifié.
"""

import sys

from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from docx.oxml.ns import qn

src, dst = sys.argv[1], sys.argv[2]
doc = Document(src)
body = doc.element.body


# ----------------------------------------------------------------------------------------------------- nettoyage
def texte(el):
    return "".join(t.text or "" for t in el.iter(qn("w:t")))


def style_de(el):
    ppr = el.find(qn("w:pPr"))
    ps = ppr.find(qn("w:pStyle")) if ppr is not None else None
    return ps.get(qn("w:val")) if ps is not None else ""


enfants = list(body)
i_contenu = next(i for i, e in enumerate(enfants) if e.tag == qn("w:p") and style_de(e) in ("Heading1", "Titre1"))
for e in enfants[i_contenu:]:
    if e.tag != qn("w:sectPr"):
        body.remove(e)

# page de garde, historique des versions, rédaction
for t in body.iter(qn("w:t")):
    if t.text and "Rapport annuel de suivi" in t.text:
        t.text = t.text.replace("Rapport annuel de suivi", "Rapport d'exécution")
    elif t.text == "03/11/2025":
        t.text = "{{DATE_EXTRACTION}}"
A_COMPLETER = {"Aurélien Salesse, chargé de mission", "Xavier Birot-Colomb, chargé de mission",
               "LPO Auvergne-Rhône-Alpes – Délégation territoriale du Rhône", "100, rue des Fougères", "69009 Lyon"}
for table in doc.tables:
    for cell in (c for row in table.rows for c in row.cells):
        for p in cell.paragraphs:
            if p.text.strip() in A_COMPLETER and p.runs:
                nouveau = "[À compléter]" if "chargé" in p.text else p.text.strip()
                for run in p.runs[1:]:
                    run.text = ""
                p.runs[0].text = nouveau
                p.runs[0].font.highlight_color = WD_COLOR_INDEX.YELLOW


# ----------------------------------------------------------------------------------------------------- écriture
def style(*noms):
    existants = {st.name for st in doc.styles}
    return next(n for n in noms if n in existants)


def H(niveau, t):
    doc.add_paragraph(t, style=style(f"Heading {niveau}", f"Titre {niveau}"))


def P(t, jaune=False):
    p = doc.add_paragraph()
    r = p.add_run(t)
    if jaune:
        r.font.highlight_color = WD_COLOR_INDEX.YELLOW
        r.italic = True
    return p


def X(cle):
    """Placeholder seul dans son paragraphe (texte, tableau, image, blocs)."""
    doc.add_paragraph("{{" + cle + "}}")


def L(t):
    doc.add_paragraph(t, style=style("Caption", "Légende"))


def A(t):
    P(f"[{t}]", jaune=True)


CATEGORIES = ("Catégories d'observateurs (règle commune à tous les protocoles) : salarié LPO (organisme LPO ou adresse "
              "LPO), organisme tiers (autre organisme, dont l'OFB), bénévole (aucun organisme). Une aire est attribuée "
              "à la catégorie de l'observateur qui y a fait le plus de passages (à égalité : salarié LPO, puis "
              "organisme tiers, puis bénévole) ; les données et le temps d'un passage suivent la même priorité. Un "
              "changement de statut crée un nouveau compte : les observateurs sont comptés en comptes.")
DESCRIPTIF = ("Indicateurs descriptifs : les fréquences et effectifs présentés ne sont pas des tendances de population "
              "(échantillons trop faibles ; les tendances STOC sont calculées par le MNHN).")

# (code, préfixe, titre, « aires suivies » accordé, textes fixes « Protocole », règles du rapport)
PROTOCOLES = [
    ("stoc", "STOC", "Suivi Temporel des Oiseaux Communs (STOC)", "carrés suivis", [
        "Le programme STOC-EPS est basé sur un protocole standardisé à l'échelle nationale : au sein d'un carré de "
        "2 × 2 km tiré aléatoirement autour d'une commune choisie par l'observateur, 10 points d'écoute de 5 minutes "
        "sont réalisés chaque printemps, par le même observateur, aux mêmes dates et sur les mêmes points.",
        "Deux passages sont attendus, du 1er avril au 8 mai et du 9 mai au 15 juin, avec au moins 4 semaines "
        "d'intervalle ; un passage du 1er au 31 mars, optionnel, est vivement recommandé. Sur chaque point, "
        "l'ensemble des oiseaux observés ou entendus est noté avec leur distance à l'observateur. Les données sont "
        "saisies dans Faune-France (Faune AuRA).",
        "Le STOC-site est une adaptation du STOC-EPS sans tirage au sort ni carré : l'observateur choisit le site. Il "
        "est mis en place par certaines réserves naturelles (STOC-RNF), par l'ONF (STOC-ONF) et par la LPO sur "
        "des sites Natura 2000 de la région.",
    ], "Temps : forfait de 10,5 h par carré suivi (saisie comprise), comme dans les rapports précédents. Observateurs "
       "comptés à partir de 2015 (champ peu fiable auparavant)."),
    ("shoc", "SHOC", "Suivi Hivernal des Oiseaux Communs (SHOC)", "carrés suivis", [
        "Relancé par le MNHN et la LPO Drôme dès l'hiver 2014-2015, le SHOC décrit les variations temporelles et "
        "géographiques de l'abondance relative des oiseaux en hiver, en complément des indicateurs du STOC.",
        "Le site de comptage est un carré de 2 × 2 km (même maillage que le STOC-EPS) dans lequel 10 transects "
        "d'environ 300 m sont parcourus à pied. Deux passages sont effectués chaque hiver : du 1er au 31 décembre et "
        "du 1er au 31 janvier, entre 8 h et 13 h, en 1 h 30 à 2 h. Les données sont saisies dans Faune-France.",
    ], "Saison : l'hiver de décembre à janvier, affiché « 2024-2025 ». Temps estimé : 2 h par passage et 1 h de "
       "saisie par carré (paramètres à ajuster par le coordinateur)."),
    ("stom", "STOM", "Suivi Temporel des Oiseaux de Montagne (STOM)", "sites suivis", [
        "Le STOM, adapté aux espèces des pelouses alpines, répond à la question : comment évolue, sur le long terme, "
        "l'abondance des oiseaux communs dans les milieux ouverts d'altitude ? La LPO Auvergne-Rhône-Alpes anime "
        "depuis 2022 un réseau de suivi à l'échelle régionale.",
        "Les sites (altitude de 1 400 à 2 600 m, pente de 0 à 35°, milieux ouverts) comptent 10 points d'écoute tirés "
        "au sort. Un seul passage est réalisé, entre le 10 mai et le 15 juillet, quand 80 % du secteur est déneigé, "
        "par temps calme, en 5 heures environ.",
    ], "Temps estimé : 5 h de terrain et 1 h de saisie par site (paramètres à ajuster par le coordinateur). Sites des "
       "autres structures (parcs nationaux, CREA, Asters) : voir texte d'animation."),
    ("sterf", "STERF", "Suivi Temporel des Rhopalocères de France (STERF)", "sites suivis", [
        "L'animation régionale du STERF a débuté en 2022 pour décliner localement les dynamiques nationales portées "
        "par le MNHN et l'OPIE, et développer un réseau de « STERFistes » : au moins 100 sites suivis (150 "
        "idéalement) sont nécessaires pour obtenir des tendances fiables.",
    ], "Un « STERF vrai » est un site d'au moins 5 transects suivi l'année du rapport ; les autres sites suivis sont "
       "des « sites type STERF ». Temps mesuré à partir des heures de début et de fin des passages (1 h par transect "
       "quand elles manquent)."),
    ("pop_reptile", "POPR", "POP Reptile", "aires suivies", [
        "L'animation régionale des protocoles nationaux de la Société Herpétologique de France a débuté en 2025. "
        "Objectif : au moins 50 mailles de 5 × 5 km suivies en POP Reptile pour obtenir des tendances fiables.",
    ], "État des aires et passages attendus : règles de la base (vues POP). Temps mesuré à partir des heures des "
       "passages (estimé quand elles manquent)."),
    ("pop_amphibien", "POPA", "POP Amphibien", "aires suivies", [
        "L'animation régionale des protocoles nationaux de la Société Herpétologique de France a débuté en 2025. "
        "Objectif : au moins 500 mares suivies en POP Amphibien pour obtenir des tendances fiables.",
    ], "État des aires et passages attendus : règles de la base (vues POP). Temps mesuré à partir des heures des "
       "passages (estimé quand elles manquent)."),
]


# ----------------------------------------------------------------------------------------------------- trame
H(1, "Chiffres clés {{ANNEE}}")
P("Rapport généré le {{DATE_EXTRACTION}} à partir des données saisies dans Faune-France et GeoNature. Les chiffres "
  "évoluent avec les saisies tardives : ils peuvent différer légèrement d'un rapport édité à une autre date.")
X("TEXTE_CHIFFRES_CLES")
X("TABLE_CHIFFRES_CLES")
L("Tableau : chiffres clés des protocoles suivis dans la zone (temps mesurés ou estimés, voir chaque section).")

H(1, "Contexte")
P("Évaluer les tendances des populations d'espèces au cours du temps est essentiel pour connaître l'état de santé des "
  "cortèges qui font la richesse de la biodiversité, et alerter les décideurs et le grand public sur les causes de "
  "son érosion. En Auvergne-Rhône-Alpes, le STOC-EPS est l'indicateur qui apporte le plus d'informations sur "
  "l'évolution des populations d'oiseaux nicheurs ; il a débuté en 2001, lors de la relance du programme national "
  "par le MNHN.")
P("Ce rapport d'exécution dresse l'état du déploiement en région des protocoles STOC, SHOC (Suivi Hivernal des "
  "Oiseaux Communs), STOM (Suivi Temporel des Oiseaux de Montagne), STERF (Suivi Temporel des Rhopalocères de France) "
  "et POP (reptiles et amphibiens).")
X("TEXTE_ZONE")
P("Méthode commune : chaque protocole est décrit de la même façon (aires suivies — carrés, sites ou aires —, unités "
  "— points, transects, mares —, passages, observateurs, données). Une aire est dans la zone si l'une de ses unités "
  "l'intersecte ; elle est alors comptée entière. " + CATEGORIES)
P(DESCRIPTIF)
A("Contexte à relire et compléter par les coordinateurs (financements, partenaires).")

for code, prefixe, titre, suivis, textes, regles in PROTOCOLES:
    aires = suivis.split(" ")[0]
    X(f"#{code}")
    H(1, titre)
    H(2, "Protocole")
    for t in textes:
        P(t)
    P(regles)
    H(2, "Participation et chiffres clés")
    X(f"{prefixe}_TEXTE_PARTICIPATION")
    X(f"{prefixe}_TABLE_CHIFFRES")
    L(f"Tableau : chiffres clés de la saison {{{{{prefixe}_ANNEE_LIBELLE}}}} et écart avec la saison précédente.")
    X(f"{prefixe}_TABLE_CATEGORIES")
    L(f"Tableau : répartition par catégorie d'observateurs, saison {{{{{prefixe}_ANNEE_LIBELLE}}}}.")
    X(f"{prefixe}_NOTE_CATEGORIES")
    H(2, "Couverture")
    X(f"{prefixe}_TEXTE_COUVERTURE")
    X(f"{prefixe}_TABLE_COUVERTURE")
    L(f"Tableau : {suivis} en {{{{{prefixe}_ANNEE_LIBELLE}}}} (par département si la zone en compte plusieurs).")
    X(f"{prefixe}_TABLE_COUVERTURE_ZBIOG")
    X(f"{prefixe}_CARTE")
    L(f"Carte : {aires} de la zone selon leur suivi en {{{{{prefixe}_ANNEE_LIBELLE}}}}.")
    H(2, "Historique et fidélisation")
    X(f"{prefixe}_TEXTE_HISTORIQUE")
    X(f"{prefixe}_CHART_AIRES")
    L(f"Figure : nombre de {suivis} par saison depuis le début du suivi.")
    X(f"{prefixe}_CHART_OBSERVATEURS")
    L("Figure : observateurs par catégorie et par saison.")
    X(f"{prefixe}_TABLE_HISTORIQUE")
    L("Tableau : chiffres clés des dernières saisons.")
    X(f"{prefixe}_TEXTE_FIDELISATION")
    H(2, "Espèces")
    X(f"{prefixe}_TEXTE_ESPECES")
    X(f"{prefixe}_TABLE_ESPECES")
    L(f"Tableau : espèces les plus fréquentes en {{{{{prefixe}_ANNEE_LIBELLE}}}} (liste complète en annexe).")
    X(f"{prefixe}_TABLE_EVOLUTION_ESPECES")
    L(f"Tableau : part des {aires} où l'espèce est notée, sur les dernières saisons (indicateur descriptif).")
    H(2, "Analyses propres au protocole")
    X(f"{prefixe}_BLOCS_SPECIFIQUES")
    H(2, "Animation et perspectives")
    A("Animation du réseau, formations, communication et perspectives à rédiger par le coordinateur.")
    X(f"/{code}")

H(1, "Conclusion et perspectives")
X("TEXTE_CONCLUSION")
A("Conclusion et perspectives à rédiger.")

H(1, "Annexes")
H(2, "Espèces notées par protocole")
X("BLOCS_ANNEXE_ESPECES")
H(2, "Contrôle des saisies")
X("BLOCS_ANNEXE_CONTROLE")

doc.save(dst)
print("Template écrit :", dst)
