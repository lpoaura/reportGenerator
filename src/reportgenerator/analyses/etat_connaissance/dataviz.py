import plotly.graph_objects as go

def safe_int(value):
    if value is None:
        return 0
    return int(value)



def create_temporal_evolution_chart(data, output_path: str):

    print("Création du graphique d'évolution temporelle...")
    years = [safe_int(row["annee"]) for row in data]
    nb_data = [safe_int(row["nb_data_tot"]) for row in data]
    nb_species = [safe_int(row["nb_espece"]) for row in data]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=years,
        y=nb_data,
        name="Nombre de données",
        mode="lines+markers"
    ))

    fig.add_trace(go.Scatter(
        x=years,
        y=nb_species,
        name="Nombre d'espèces",
        mode="lines+markers",
        yaxis="y2"
    ))

    fig.update_layout(
        title="Évolution temporelle",
        xaxis=dict(title="Année"),
        yaxis=dict(title="Nombre de données"),
        yaxis2=dict(
            title="Nombre d'espèces",
            overlaying="y",
            side="right"
        )
    )

    fig.write_image(output_path, width=1200, height=600)