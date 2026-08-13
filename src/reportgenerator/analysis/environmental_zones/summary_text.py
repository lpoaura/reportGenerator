TYPE_LABELS = {
    "PNR": "Parc Naturel Régional",
    "APB": "Arrêté de Protection de Biotope",
    "ZNIEFF1": "ZNIEFF de type I",
    "ZNIEFF2": "ZNIEFF de type II",
    "RNR": "Réserve Naturelle Régionale",
    "RNN": "Réserve Naturelle Nationale",
    "Natura 2000": "Natura 2000",
}

ZONE_LABELS = {
    "zone_etude": "la zone d'étude",
    "buffer": "le buffer",
    "10km": "l'extension à 10 km",
}


def pivot_zonage_data(raw_data):
    """Transforme le format long SQL en une liste de dicts pivotés par type_code."""
    pivot = {}
    for row in raw_data:
        entry = pivot.setdefault(
            row["type_code"],
            {"type_code": row["type_code"], "zone_etude": 0, "buffer": 0, "10km": 0},
        )
        entry[row["zone_name"]] = float(row["surface_km2"] or 0)
    return sorted(pivot.values(), key=lambda x: x["type_code"])


def build_zonage_summary_text(pivoted_data):
    """Génère un paragraphe de synthèse à partir des données pivotées."""
    if not pivoted_data:
        return "Aucun zonage environnemental n'a été recensé sur le périmètre étudié."

    phrases = []
    for entry in pivoted_data:
        label = TYPE_LABELS.get(entry["type_code"], entry["type_code"])
        parts = []
        for zone_key in ("zone_etude", "buffer", "10km"):
            surface = entry.get(zone_key, 0)
            if surface > 0:
                parts.append(f"{surface:.2f} km² dans {ZONE_LABELS[zone_key]}")

        if parts:
            phrases.append(f"{label} : " + ", ".join(parts) + ".")

    if not phrases:
        return "Aucun zonage environnemental n'a été recensé sur le périmètre étudié."

    return (
        "Le périmètre étudié recoupe plusieurs zonages environnementaux réglementaires. "
        + " ".join(phrases)
    )