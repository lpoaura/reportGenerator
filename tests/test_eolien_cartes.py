"""Plan des cartes par groupe d'espèces et couleurs (dossier éolien), sans base ni QGIS."""

from reportgenerator.analysis.eolien import cartes as c
from reportgenerator.core.dossier import load_dossier


def _sp(cd, lb_nom, ordre="Accipitriformes", famille="Accipitridae", nom=None):
    return {"cd_ref": cd, "lb_nom": lb_nom, "ordre": ordre, "famille": famille, "nom_vern": nom or lb_nom}


NOCTURNES = [_sp(i, n, "Strigiformes", "Strigidae") for i, n in enumerate(
    ["Bubo bubo", "Asio otus", "Otus scops", "Strix aluco", "Athene noctua", "Glaucidium passerinum",
     "Aegolius funereus", "Tyto alba"], start=1)]
GROUPES = [
    {"cle": "nocturnes", "titre": "rapaces nocturnes", "section": "rapaces", "ordres": ["Strigiformes"],
     "decoupage": [{"cle": "hiboux", "titre": "hiboux", "genres": ["Bubo", "Asio", "Otus"]},
                   {"cle": "chouettes", "titre": "chouettes", "genres": ["Strix", "Athene", "Glaucidium",
                                                                         "Aegolius", "Tyto"]}]},
    {"cle": "milans_busards", "titre": "milans et busards", "section": "rapaces", "genres": ["Milvus", "Circus"]},
    {"cle": "diurnes", "titre": "autres rapaces diurnes", "section": "rapaces", "ordres": ["Accipitriformes"]},
]


def test_groupes_par_regles_et_carte_autres():
    especes = [_sp(10, "Milvus milvus"), _sp(11, "Circus cyaneus"), _sp(12, "Aquila chrysaetos"),
               _sp(13, "Alcedo atthis", "Coraciiformes", "Alcedinidae"), NOCTURNES[0]]
    cartes = c.plan_cartes(especes, GROUPES, 6)
    par_cle = {k["cle"]: [sp["cd_ref"] for sp in k["especes"]] for k in cartes}
    assert par_cle == {"nocturnes": [1], "milans_busards": [11, 10], "diurnes": [12], "autres": [13]}
    assert [k["ordre"] for k in cartes] == [1, 2, 3, 4] and cartes[-1]["section"] == "autres"
    # toutes les espèces sont sur une carte, une seule fois
    assert sorted(cd for k in cartes for cd in (sp["cd_ref"] for sp in k["especes"])) == [1, 10, 11, 12, 13]


def test_decoupage_hiboux_chouettes_au_dela_de_6():
    cartes = c.plan_cartes(NOCTURNES, GROUPES, 6)
    assert [(k["cle"], k["titre"], len(k["especes"])) for k in cartes] == [
        ("nocturnes_hiboux", "hiboux", 3), ("nocturnes_chouettes", "chouettes", 5)]
    assert len(c.plan_cartes(NOCTURNES[:6], GROUPES, 6)) == 1


def test_decoupage_automatique_garde_les_genres():
    especes = [_sp(i, f"{g} sp{i}") for i, g in enumerate(["Aquila", "Aquila", "Aquila", "Buteo", "Buteo",
                                                           "Pernis", "Accipiter", "Accipiter"], start=1)]
    cartes = c.plan_cartes(especes, GROUPES, 6)
    assert [k["titre"] for k in cartes] == ["autres rapaces diurnes (1/2)", "autres rapaces diurnes (2/2)"]
    genres = [{c.genre(sp) for sp in k["especes"]} for k in cartes]
    assert not genres[0] & genres[1]          # aucun genre coupé entre deux cartes
    assert all(len(k["especes"]) <= 6 for k in cartes)


def test_decoupage_equilibre():
    especes = [_sp(i, f"Genus{i} sp") for i in range(7)]
    assert [len(p) for p in c.decouper(especes, 6)] == [4, 3]
    assert [len(p) for p in c.decouper(especes[:6], 6)] == [6]
    assert [len(p) for p in c.decouper([_sp(i, f"G{i} sp") for i in range(13)], 6)] == [5, 5, 3]
    assert c.decouper([], 6) == []


def test_groupes_du_dossier_eolien():
    groupes = load_dossier("eolien").params["groupes_cartes"]
    assert [g["cle"] for g in groupes][:4] == ["nocturnes", "buses_faucons", "milans_busards", "vautours"]
    autres = [_sp(1, "Gyps fulvus"), _sp(2, "Falco tinnunculus", "Falconiformes", "Falconidae"),
              _sp(3, "Ardea cinerea", "Pelecaniformes", "Ardeidae"),
              _sp(4, "Lanius excubitor", "Passeriformes", "Laniidae")]
    cartes = {k["especes"][0]["cd_ref"]: k["cle"] for k in c.plan_cartes(autres, groupes, 6)}
    assert cartes == {1: "vautours", 2: "buses_faucons", 3: "herons", 4: "passereaux"}


def test_couleurs_referentiel_et_automatiques():
    ref = {1: "#2c4699", 2: "#2c4799", 3: "#db1e2a"}      # 1 et 2 presque identiques
    couleurs, remplacees = c.attribuer_couleurs([[1, 2, 4], [3, 4]], ref)
    assert couleurs[1] == "#2c4699" and couleurs[3] == "#db1e2a"
    assert remplacees == [2] and c.ecart(couleurs[2], couleurs[1]) >= c.ECART_MIN
    # l'espèce 4 (sans couleur de référence) a la même couleur sur ses deux cartes, distincte de ses voisines
    assert all(c.ecart(couleurs[4], couleurs[v]) >= c.ECART_MIN for v in (1, 2, 3))
    # sans voisine commune, une même couleur peut être réutilisée
    seules, _ = c.attribuer_couleurs([[5], [6]], {})
    assert seules[5] == seules[6]


def test_ecart_et_referentiel_du_dossier():
    assert c.ecart("#000000", "#ffffff") > 99 and c.ecart("#2c4699", "#2c4699") == 0
    ref = c.load_couleurs(load_dossier("eolien").path / "couleurs_especes.csv")
    assert ref[2844] == "#db1e2a"          # Milan royal
    assert len(ref) >= 45
