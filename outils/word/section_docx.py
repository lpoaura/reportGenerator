"""Insertion de la section « État des connaissances par maille » (textes_connaissance.paragraphes) dans un docx.

inserer(doc, ref_el, items, modeles) -> dernier élément inséré
  modeles : {"texte": <w:p> de corps de texte, "titre": <w:p> de titre (niveau voulu),
             "carte": <w:p> d'un placeholder de carte du template, "legende": fonction(ref_el, texte) -> <w:p> | None}
Les paragraphes copient la mise en forme des modèles (pPr et rPr du premier run) ; saut de section retiré.
"""
import copy

from docx.enum.text import WD_COLOR_INDEX
from docx.oxml import OxmlElement  # noqa: F401 (utilisé aussi par section_connaissance.py)
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

W = qn


def _set_text(doc, p_el, parts):
    """Contenu du paragraphe = parts [(texte, jaune)], mise en forme du premier run du modèle conservée."""
    first = p_el.find(".//" + W("w:r"))
    rpr = copy.deepcopy(first.find(W("w:rPr"))) if first is not None and first.find(W("w:rPr")) is not None else None
    for child in list(p_el):
        if child.tag != W("w:pPr"):
            p_el.remove(child)
    p = Paragraph(p_el, doc._body)
    for text, jaune in parts:
        r = p.add_run(text)
        if rpr is not None:
            r._r.insert(0, copy.deepcopy(rpr))
            for h in r._r.findall(".//" + W("w:highlight")):
                h.getparent().remove(h)
        if jaune:
            r.font.highlight_color = WD_COLOR_INDEX.YELLOW
    return p_el


def nouveau(doc, ref_el, modele, parts):
    p = copy.deepcopy(modele)
    sp = p.find(W("w:pPr") + "/" + W("w:sectPr"))
    if sp is not None:
        sp.getparent().remove(sp)
    for br in p.findall(".//" + W("w:br")):   # sauts de page du modèle
        br.getparent().remove(br)
    _set_text(doc, p, parts)
    ref_el.addnext(p)
    return p


def gras(p_el):
    """Intertitre en gras, gardé avec le paragraphe suivant."""
    for r in p_el.iter(W("w:r")):
        rpr = r.find(W("w:rPr"))
        if rpr is None:
            rpr = OxmlElement("w:rPr")
            r.insert(0, rpr)
        if rpr.find(W("w:b")) is not None:
            continue
        # ordre du schéma : rStyle, rFonts, b...
        prec = [c for c in rpr if c.tag in (W("w:rStyle"), W("w:rFonts"))]
        if prec:
            prec[-1].addnext(OxmlElement("w:b"))
        else:
            rpr.insert(0, OxmlElement("w:b"))
    return p_el


def num_heading2(doc) -> str:
    """numId de la liste des titres de niveau 2 (style Heading 2)."""
    return doc.styles["Heading 2"].element.find(f".//{W('w:numPr')}/{W('w:numId')}").get(W("w:val"))


def compteur(num_h2):
    """Paragraphe vide masqué du niveau 0 de la liste des titres de niveau 2 : dans ces templates, il fait avancer
    le chiffre du chapitre des sous-titres (placé avant chaque chapitre qui a des sous-titres)."""
    p = OxmlElement("w:p")
    ppr = OxmlElement("w:pPr")
    num = OxmlElement("w:numPr")
    for tag, val in (("w:ilvl", "0"), ("w:numId", num_h2)):
        e = OxmlElement(tag)
        e.set(W("w:val"), val)
        num.append(e)
    ppr.append(num)
    rpr = OxmlElement("w:rPr")
    rpr.append(OxmlElement("w:vanish"))
    ppr.append(rpr)
    p.append(ppr)
    return p


def est_compteur(el, num_h2) -> bool:
    ppr = el.find(W("w:pPr")) if el.tag == W("w:p") else None
    if ppr is None or "".join(el.itertext()).strip():
        return False
    num = ppr.find(W("w:numPr"))
    return num is not None and num.find(W("w:numId")) is not None \
        and num.find(W("w:numId")).get(W("w:val")) == num_h2 and num.find(W("w:ilvl")).get(W("w:val")) == "0"


def sectpr_avant(el):
    """sectPr du premier paragraphe qui en porte un, à partir de el (inclus) en remontant."""
    while el is not None:
        if el.tag == W("w:p") and el.find(W("w:pPr") + "/" + W("w:sectPr")) is not None:
            return el.find(W("w:pPr") + "/" + W("w:sectPr"))
        el = el.getprevious()
    raise KeyError("sectPr")


def sectpr_apres(el):
    """sectPr de la section qui contient el : premier paragraphe portant un sectPr à partir de el (inclus) en
    descendant, sinon celui du corps du document (dernière section)."""
    while el is not None:
        if el.tag == W("w:p") and el.find(W("w:pPr") + "/" + W("w:sectPr")) is not None:
            return el.find(W("w:pPr") + "/" + W("w:sectPr"))
        if el.tag == W("w:sectPr"):
            return el
        el = el.getnext()
    raise KeyError("sectPr")


def fin_de_section(ref_el, sectpr, avant=False):
    """Paragraphe vide portant une copie de sectpr (fin de section : la mise en page s'applique à ce qui précède),
    inséré après ref_el (ou avant)."""
    p = OxmlElement("w:p")
    ppr = OxmlElement("w:pPr")
    ppr.append(copy.deepcopy(sectpr))
    p.append(ppr)
    (ref_el.addprevious if avant else ref_el.addnext)(p)
    return p


def inserer(doc, ref_el, items, modeles):
    n = ref_el
    for kind, texte in items:
        if kind == "titre":
            n = nouveau(doc, n, modeles["titre"], [(texte, False)])
        elif kind == "question":
            n = gras(nouveau(doc, n, modeles["texte"], [(texte, False)]))
            Paragraph(n, doc._body).paragraph_format.keep_with_next = True
        elif kind == "texte":
            n = nouveau(doc, n, modeles["texte"], [(texte, False)])
        elif kind == "jaune":
            n = nouveau(doc, n, modeles["texte"], [(texte, True)])
        elif kind == "carte":
            n = nouveau(doc, n, modeles["carte"], [("{{" + texte + "}}", False)])
        elif kind == "bloc":
            n = nouveau(doc, n, modeles["texte"], [("{{" + texte + "}}", False)])
        elif kind == "legende" and modeles.get("legende"):
            n = modeles["legende"](n, texte)
    return n
