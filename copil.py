import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Configuration Streamlit
st.set_page_config(layout="wide")

# Téléchargement du fichier
uploaded_file = st.file_uploader("Chargez votre fichier Excel", type=["xlsx"])

if uploaded_file is not None:
    # Lire le fichier Excel
    df = pd.read_excel(uploaded_file, engine="openpyxl")

    # Vérification des colonnes nécessaires
    if all(col in df.columns for col in ['Année', 'FR143 - Poitiers Sud', 'FR036 - Le Mans', 'FR047 - Schweighouse', 'FR037 - Annecy - Epagny', 'FR044 - La Couronne / Angouleme ']):
        st.write("Données chargées avec succès.")

        # Création des colonnes d'évolution pour chaque ville
        for col in ['FR143 - Poitiers Sud', 'FR036 - Le Mans', 'FR047 - Schweighouse', 'FR037 - Annecy - Epagny', 'FR044 - La Couronne / Angouleme ']:
            df[f'Evolution_{col}'] = df[col].pct_change() * 100

        # Création des subplots
        fig = make_subplots(
            rows=2, cols=3,
            shared_xaxes=False,
            vertical_spacing=0.2,
            subplot_titles=['FR143 - Poitiers Sud', 'FR036 - Le Mans', 'FR047 - Schweighouse', 'FR037 - Annecy - Epagny', 'FR044 - La Couronne / Angouleme ', 'Évolutions des consommations 2025 VS 2024'],
            specs=[[{'secondary_y': False}, {'secondary_y': False}, {'secondary_y': False}],
                [{'secondary_y': False}, {'secondary_y': False}, {'type': 'table'}]]
        )

        # Ajout des graphes pour chaque ville
        for idx, col in enumerate(['FR143 - Poitiers Sud', 'FR036 - Le Mans', 'FR047 - Schweighouse', 'FR037 - Annecy - Epagny', 'FR044 - La Couronne / Angouleme ']):
            row = idx // 3 + 1
            col_idx = idx % 3 + 1

            fig.add_trace(go.Bar(
                x=df['Année'].astype(int),
                y=df[col],
                name=f'Consommation {col}',
                marker=dict(color='MediumAquamarine'),
                text=[f'{kwh:.0f} kWh' for kwh in df[col]],
                textposition='outside',
                showlegend=False
            ), row=row, col=col_idx)

            # Ajout des annotations pour les évolutions
            fig.add_trace(go.Scatter(
                x=df['Année'].astype(int),
                y=df[col] * 0.92,  # Position pour les annotations
                mode='text',
                text=[f"{evol:.0f}%" if not pd.isna(evol) else '' for evol in df[f'Evolution_{col}']],
                textfont=dict(size=18, color=['red' if evol > 0 else 'green' for evol in df[f'Evolution_{col}'].fillna(0)]),
                showlegend=False
            ), row=row, col=col_idx)

            fig.update_xaxes(
                title_text="Année",
                tickmode='array',
                tickvals=df['Année'].unique(),
                tickformat='d',
                row=row, col=col_idx
            )

        # Calcul des consommations et évolutions pour le tableau
        evolution_data = {}

        for col in ['FR143 - Poitiers Sud', 'FR036 - Le Mans', 'FR047 - Schweighouse', 'FR037 - Annecy - Epagny', 'FR044 - La Couronne / Angouleme ']:
            consommation_2025 = df[df['Année'] == 2025][col].sum()
            consommation_2024 = df[df['Année'] == 2024][col].sum()

            if consommation_2024 != 0:
                evolution_2025 = ((consommation_2025 - consommation_2024) / consommation_2024) * 100
            else:
                evolution_2025 = 0

            evolution_data[col] = {
                '2025': consommation_2025,
                'Evolution (%)': evolution_2025
            }

        # Ajout du tableau
        fig.add_trace(go.Table(
            header=dict(
                values=["Ville", "Consommation 2025 (kWh)", "Evolution 2025 (%)"],
                fill_color='SeaGreen',
                font=dict(color='white', size=18),
                align='center'
            ),
            cells=dict(
                values=[
                    ['FR143 - Poitiers Sud', 'FR036 - Le Mans', 'FR047 - Schweighouse', 'FR037 - Annecy - Epagny', 'FR044 - La Couronne / Angouleme '],
                    [f"{evolution_data[city]['2025']:,.0f}" for city in ['FR143 - Poitiers Sud', 'FR036 - Le Mans', 'FR047 - Schweighouse', 'FR037 - Annecy - Epagny', 'FR044 - La Couronne / Angouleme ']],
                    [f"{evolution_data[city]['Evolution (%)']:.0f}%" for city in ['FR143 - Poitiers Sud', 'FR036 - Le Mans', 'FR047 - Schweighouse', 'FR037 - Annecy - Epagny', 'FR044 - La Couronne / Angouleme ']]
                ],
                fill_color='LightGreen',
                align='center',
                font=dict(
                    color=[
                        ['black'] * 5,  # Couleurs des noms de ville
                        ['black'] * 5,  # Couleurs des consommations
                        ['red' if evolution_data[city]['Evolution (%)'] > 0 else 'green' 
                        for city in ['FR143 - Poitiers Sud', 'FR036 - Le Mans', 'FR047 - Schweighouse', 'FR037 - Annecy - Epagny', 'FR044 - La Couronne / Angouleme ']]
                    ]
                )
            )
        ), row=2, col=3)


        # Mise à jour de la mise en page
        fig.update_layout(
            title='Consommation énergétique et évolution par ville',
            height=1200,
            width=1200,
            template='plotly_white',
            font=dict(family="Times New Roman", size=18),
        )

        # Mise à jour des axes Y
        for idx in range(1, 6):
            fig.update_yaxes(title_text="Consommation (kWh)", row=(idx - 1) // 3 + 1, col=(idx - 1) % 3 + 1)

        # Affichage
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("Les colonnes requises ne sont pas présentes dans les données.")
