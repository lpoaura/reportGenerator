from plotly import io as pio
import plotly.graph_objects as go


LPO_COLORS = {
    "blue": "#0088cc",
    "orange": "#eb5f1a",
    "green": "#007e85",
    "red": "#e62328",
    "yellow": "#ffc33c",
    "black": "#323232",
    "dark": "#191919",
    "white": "#F0F0EB"
}


lpo_template = go.layout.Template(

    layout=go.Layout(

        font=dict(
            family="LPO-Regular",
            size=16,
            color=LPO_COLORS["black"]
        ),

        title=dict(
            font=dict(
                family="LPO-Bold",
                size=24,
                color=LPO_COLORS["dark"]
            ),
            x=0.02,
            xanchor="left"
        ),

        plot_bgcolor="white",
        paper_bgcolor="white",

        hovermode="x unified",

        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),

        margin=dict(
            l=60,
            r=60,
            t=80,
            b=60
        ),

        xaxis=dict(
            showgrid=True,
            gridcolor="#DDDDDD",
            zeroline=False,
            linecolor="#AAAAAA"
        ),

        yaxis=dict(
            showgrid=True,
            gridcolor="#DDDDDD",
            zeroline=False,
            linecolor="#AAAAAA"
        )
    )
)

pio.templates["lpo"] = lpo_template
pio.templates.default = "lpo"