import streamlit as st
from streamlit_lightweight_charts import renderLightweightCharts
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import seaborn as sns
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import matplotlib.pyplot as plt
from plotly.subplots import make_subplots
import requests
from geopy.geocoders import Nominatim
import psutil
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error
# Configurer la mise en page pour utiliser toute la largeur disponible
st.set_page_config(layout="wide")
# Configuration du thème seaborn
sns.set_theme(style="whitegrid")
# Initialisation des variables globales pour les dates
cal_debut = None
cal_fin = None

# Variables globales
df_energie = None  # Pour les données énergétiques
colonne_p10 = None 

compteurs = {
    "Dakar": "203.0.113.10",
    "Thiès": "198.51.100.20",
    "Saint-Louis": "192.0.2.15"
}

def lire_compteur(ip):
    from pymodbus.client import ModbusTcpClient
    client = ModbusTcpClient(ip, port=502)
    if not client.connect():
        print(f"Échec de connexion à {ip}")
        return None  # ⛔ Éviter une requête si la connexion est impossible
    
    try:
        reg = client.read_holding_registers(address=0x0001, count=2, slave=1)
        return reg.registers[0] if reg else None
    except Exception as e:
        print(f"Erreur lors de la lecture Modbus sur {ip} : {e}")
        return None
    finally:
        client.close()

    data = {ville: lire_compteur(ip) for ville, ip in compteurs.items()}
    df = pd.DataFrame(list(data.items()), columns=["Ville", "Consommation (kWh)"])

    st.title("Suivi de consommation des compteurs distants")
    st.dataframe(df)

# Interface Streamlit
st.title("Analyse de Consommation Énergétique")

uploaded_file = st.sidebar.file_uploader("Choisissez un fichier Excel pour les P10", type=["xlsx"], key="file_uploader")
uploaded_file_temperature = st.sidebar.file_uploader("Choisissez un fichier Excel pour les températures", type=["xlsx"], key="file_uploader_temperature")

# Sélectionner le mode d'analyse
mode = st.sidebar.selectbox("Choisissez un mode d'analyse :", ["Comparaison par période", "Analyse et rapport", "Export des données"])

def recuperer_infos_point_mesure():
    st.title("📡 Informations du Point de Mesure")

    choix = st.radio("Comment voulez-vous renseigner les informations ?", 
                     ("Saisie manuelle", "Charger un fichier Excel"))

    if choix == "Saisie manuelle":
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            point_mesure = st.text_input("🆔 Identifiant du Point de Mesure")
        with col2:
            td_lie = st.text_input("🔗 Tableau Divisionnaire (TD) lié")
        with col3:
            emplacement = st.text_input("📍 Emplacement du compteur sur site")
        with col4:
            usage = st.text_input("⚡ Usage mesuré")

        infos = {
            "Point de Mesure": point_mesure,
            "TD Lié": td_lie,
            "Emplacement": emplacement,
            "Usage": usage
        }

    else:
        fichier = st.file_uploader("📂 Importer les informations du point de mesure (XLSX)", type=["xlsx"])
        
        if fichier:
            df = pd.read_excel(fichier)
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                point_mesure = st.selectbox("Sélectionnez le Point de Mesure", df[df.columns[0]].unique())
            with col2:
                td_lie = st.selectbox("Sélectionnez le TD Lié", df[df.columns[1]].unique())
            with col3:
                emplacement = st.selectbox("Sélectionnez l'Emplacement", df[df.columns[2]].unique())
            with col4:
                usage = st.selectbox("Sélectionnez l'Usage", df[df.columns[3]].unique())

            infos = {
                "Point de Mesure": point_mesure,
                "TD Lié": td_lie,
                "Emplacement": emplacement,
                "Usage": usage
            }

            st.success("✅ Données récupérées avec succès !")

        else:
            st.warning("📌 Veuillez importer les informations (XLSX).")
            infos = {}

    return infos

def graphe_by_analyse_heatmap():
    global colonne_p10
    all_data = analyse()

    # Vérifier si all_data n'est pas None
    if all_data is not None and not all_data.empty:
        # Créer un DataFrame pivot pour structurer les données pour la heatmap
        periodes = all_data['Période'].unique()
        heatmap_data = pd.DataFrame()

        for periode in periodes:
            data_periode = all_data[(all_data['Période'] == periode) & (all_data[colonne_p10] > 0)]
            data_periode = data_periode.set_index('Date')
            data_periode.index = pd.to_datetime(data_periode.index)

            # Resample pour une agrégation par intervalles de 10 minutes
            data_periode_resampled = data_periode[colonne_p10].resample("10T").mean()
            
            # Ajouter les données dans la structure du DataFrame pour la heatmap
            heatmap_data[periode] = data_periode_resampled

        # Remplir les valeurs manquantes avec 0 (ou tout autre valeur par défaut)
        heatmap_data.fillna(0, inplace=True)

        # Créer la heatmap
        fig_heatmap = go.Figure(
            go.Heatmap(
                z=heatmap_data.values,                   # Valeurs de consommation
                x=heatmap_data.index,                    # Dates en tant qu'axe x
                y=heatmap_data.columns,                  # Périodes en tant qu'axe y
                colorscale="Viridis",                    # Palette de couleurs
                colorbar=dict(title="Consommation (kWh)")  # Titre pour l'échelle de couleurs
            )
        )

        # Personnalisation des titres et des polices
        fig_heatmap.update_layout(
            title='Carte thermique des consommations par période',
            xaxis_title='Date',
            yaxis_title='Période de fonctionnement',
            title_font=dict(family="Times New Roman", size=24),
            xaxis_title_font=dict(family="Times New Roman", size=20),
            yaxis_title_font=dict(family="Times New Roman", size=20),
            font=dict(family="Times New Roman", size=14)
        )

        # Afficher la heatmap dans Streamlit
        st.plotly_chart(fig_heatmap)
    else:
        st.error("Aucune donnée à afficher.")

def graphe_regression_tempo():
    global colonne_p10, colonne_temperature, df_temperature, cal_debut, cal_fin
    all_data = analyse()

    # Vérifiez que df_temperature existe et a des valeurs valides
    if df_temperature is not None and not df_temperature.empty:
        df_temperature_clean = df_temperature.dropna(subset=[colonne_temperature])
        df_temperature_resampled = df_temperature_clean.resample("1h").mean()  # Resample par heure

    if all_data is not None and not all_data.empty:
        fig_histogram = go.Figure()
        periodes = all_data['Période'].unique()
        couleurs_periodes = ["Blue", "MediumSeaGreen", "Red"]

        # Tracer l'histogramme des consommations
        for idx, periode in enumerate(periodes):
            data_periode = all_data[(all_data['Période'] == periode) & (all_data[colonne_p10] > 0)]
            data_periode = data_periode.set_index('Date')
            data_periode.index = pd.to_datetime(data_periode.index)
            data_periode_resampled = data_periode[colonne_p10].resample("10min").mean()

            # Ajouter les barres de consommation
            fig_histogram.add_trace(
                go.Bar(
                    x=data_periode_resampled.index,
                    y=data_periode_resampled,
                    name=f'{periode}',
                    marker=dict(color=couleurs_periodes[idx % len(couleurs_periodes)]),
                    opacity=0.8,
                    yaxis="y1"  # Associe cette trace à l'axe Y principal (y1)
                )
            )

            # Filtrer df_temperature pour obtenir les valeurs correspondant aux index de la période
            temperature_periode = df_temperature_resampled[df_temperature_resampled.index.isin(data_periode_resampled.index)]

            # Ajouter la courbe de température pour la période correspondante avec un axe Y secondaire
            fig_histogram.add_trace(
                go.Scatter(
                    x=temperature_periode.index,
                    y=temperature_periode[colonne_temperature],
                    mode='lines',
                    name=f'Température',
                    line=dict(color=couleurs_periodes[idx % len(couleurs_periodes)]),
                    yaxis="y2"  # Associe cette trace à l'axe Y secondaire (y2)
                )
            )

        # Mise en page avec un second axe Y pour les températures
        fig_histogram.update_layout(
            title=f'Consommations électriques et Température : {colonne_p10}',
            xaxis_title='Date',
            yaxis=dict(
                title='Consommations en kWh',
                titlefont=dict(family="Times New Roman", size=20),
                tickfont=dict(family="Times New Roman", size=18),
            ),
            yaxis2=dict(
                title='Température (°C)',
                titlefont=dict(family="Times New Roman", size=20),
                tickfont=dict(family="Times New Roman", size=18),
                overlaying='y',  # Superpose l'axe secondaire sur l'axe Y principal
                side='right'  # Place l'axe secondaire à droite
            ),
            title_font=dict(family="Times New Roman", size=24),
            xaxis_title_font=dict(family="Times New Roman", size=24),
            font=dict(family="Times New Roman", size=16)
        )

        st.plotly_chart(fig_histogram)
    else:
        st.error("Aucune donnée à afficher.")

# Fonction pour afficher les graphiques pour chaque période en regrresion linèaire avec les températures
def graphe_regression_lineaire():
    global colonne_p10, colonne_temperature, df_temperature, cal_debut, cal_fin
    all_data = analyse()
    #température de consignes pour les périodes

    # Vérifiez que df_temperature existe et a des valeurs valides
    if df_temperature is not None and not df_temperature.empty:
        df_temperature_clean = df_temperature.dropna(subset=[colonne_temperature])
        df_temperature_resampled = df_temperature_clean.resample("1h").mean()  # Resample par heure
    else:
        st.error("Données de température manquantes ou invalides.")
        return

    if all_data is not None and not all_data.empty:
        periodes = all_data['Période'].unique()
        dfs_periode = []
        couleurs_periodes = ["Blue", "MediumSeaGreen", "Red"]

        # Préparation des données de chaque période
        for idx, periode in enumerate(periodes):
            data_periode = all_data[(all_data['Période'] == periode) & (all_data[colonne_p10] > 0)]
            data_periode = data_periode.set_index('Date')
            data_periode.index = pd.to_datetime(data_periode.index)
            data_periode_resampled = data_periode[colonne_p10].resample("1h").mean()

            # Filtrer df_temperature pour obtenir les valeurs correspondant aux index de la période
            temperature_periode = df_temperature_resampled[df_temperature_resampled.index.isin(data_periode_resampled.index)]

            # Fusion des consommations et températures dans un seul DataFrame pour cette période
            df_merged = pd.DataFrame({
                'Consommation': data_periode_resampled,
                'Température': temperature_periode[colonne_temperature]
            }).dropna()  # Supprimer les lignes avec des valeurs NaN
            
            df_merged['Période'] = periode
            df_merged['Couleur'] = couleurs_periodes[idx]
            df_merged['Date'] = df_merged.index

            dfs_periode.append(df_merged)

        # Concaténation des données de toutes les périodes
        df_final = pd.concat(dfs_periode)

        # Initialisation de la figure
        fig = make_subplots(
            rows=1, cols=1,
            subplot_titles=["<b>Regression des consommations électriques en rapport avec les tempratures<br>Selon les périodes de fonctionnement du site"],
        )

        # Ajouter des traces pour chaque période
        for idx, periode in enumerate(periodes):
            key_checkbox = f"afficher_annotations_{periode}"  # Clé unique pour chaque période
            afficher_annotations = st.checkbox(f"Afficher les annotations pour {periode}", value=True, key=key_checkbox)

            data = df_final[df_final['Période'] == periode]
            if data.empty:
                st.warning(f"Aucune donnée disponible pour la période {periode}.")
                continue

            # Ajouter un scatter pour la période
            fig.add_trace(
                go.Scatter(
                    x=data[f'Consommation'],
                    y=data['Température'],
                    mode='markers',
                    name=f"{periode}",
                    marker=dict(color=data['Couleur'].iloc[0], size=data['Consommation'] / data['Consommation'].max() * 20),
                    hovertemplate="<b>Date:</b> %{text}<br><b>Consommation en kWh:</b> %{x}<br><b>Température en °C:</b> %{y}<br><extra></extra>",
                    text=data['Date'].dt.strftime('%Y-%m-%d %H:%M')
                ),
                row=1, col=1
            )

            # Calcul et ajout de la droite de régression linéaire
            if not data.empty:
                slope, intercept = np.polyfit(data['Consommation'], data['Température'], 1)
                regression_line = slope * data['Consommation'] + intercept
                r_value = np.corrcoef(data['Consommation'], data['Température'])[0, 1]

                fig.add_trace(
                    go.Scatter(
                        x=data['Consommation'],
                        y=regression_line,
                        mode='lines',
                        name=f"Tendance {periode} (R={r_value:.2f})",
                        line=dict(color=data['Couleur'].iloc[0], dash='dot')
                    ),
                    row=1, col=1
                )

            # Ajouter des annotations si la checkbox est activée
            if afficher_annotations:
                # Annotations pour les quantiles
                quantiles = data['Consommation'].quantile([0.25, 0.5, 0.75]).to_list()
                quantiles_percentages = [25, 50, 75]
                for quantile, percentage in zip(quantiles, quantiles_percentages):
                    closest_point = data.iloc[(data['Consommation'] - quantile).abs().argsort()[:1]]
                    consommation = closest_point['Consommation'].values[0]
                    temperature = closest_point['Température'].values[0]
                    date = closest_point['Date'].dt.strftime('%Y-%m-%d %H:%M').values[0]

                    fig.add_annotation(
                        x=consommation,
                        y=temperature,
                        text=f"{date}, {temperature:.2f} °C<br>{percentage}% des P10 sont < à {consommation:.2f} kWh",
                        showarrow=True,
                        arrowhead=2,
                        ax=40,
                        ay=-40,
                        font=dict(size=12, color="black"),
                        bgcolor="lightyellow",
                        bordercolor="black",
                        borderwidth=1
                    )

                # Annotations pour Température max et min
                max_temp = data.loc[data['Température'].idxmax()]
                min_temp = data.loc[data['Température'].idxmin()]

                for temp_data, label in zip([max_temp, min_temp], ["Max", "Min"]):
                    fig.add_annotation(
                        x=temp_data['Consommation'],
                        y=temp_data['Température'],
                        text=(
                            f"T° {label} en {periode}<br>{temp_data['Date'].strftime('%Y-%m-%d %H:%M')}<br>"
                            f"({temp_data['Consommation']:.2f} kWh, {temp_data['Température']:.2f} °C)"
                        ),
                        showarrow=True,
                        arrowhead=2,
                        ax=40 if label == "Max" else -40,
                        ay=-40,
                        font=dict(size=14, color="black"),
                        bgcolor="lightpink" if label == "Max" else "lightblue",
                        bordercolor="black",
                        borderwidth=1
                    )

        # Mise en forme du graphique
        try:
            fig.update_layout(
                height=800,
                title="<b>Analyse de la Consommation en corrélation avec des Températures",
                title_font=dict(family="Times New Roman", size=24),
                font=dict(family="Times New Roman", size=18),
                editable=True
            )
        except Exception as e:
            print(f"Erreur lors de la mise à jour de la mise en page: {e}")

        fig.update_xaxes(title_text="<b>Consommations électriques mesurées en (kWh)", row=1, col=1)
        fig.update_yaxes(title_text="<b>Température mesurées en (°C)", row=1, col=1)

        # Afficher le graphique
        st.plotly_chart(fig)
    else:
        st.error("Aucune donnée à afficher.")

def graphe_tempo():
    global colonne_p10, colonne_temperature, df_temperature, cal_debut, cal_fin
    all_data = analyse()

    # Vérifiez que df_temperature existe et a des valeurs valides
    if df_temperature is not None and not df_temperature.empty:
        df_temperature_clean = df_temperature.dropna(subset=[colonne_temperature])
        df_temperature_resampled = df_temperature_clean.resample("1h").mean()  # Resample par heure

    if all_data is not None and not all_data.empty:
        periodes = all_data['Période'].unique()
        dfs_periode = []
        couleurs_periodes = ["Yellow", "MediumSeaGreen", "Red", "Blue"]

        # Préparation des données de chaque période
        for periode in periodes:
            data_periode = all_data[(all_data['Période'] == periode) & (all_data[colonne_p10] > 0)]
            data_periode = data_periode.set_index('Date')
            data_periode.index = pd.to_datetime(data_periode.index)
            data_periode_resampled = data_periode[colonne_p10].resample("1h").mean()

            # Filtrer df_temperature pour obtenir les valeurs correspondant aux index de la période
            temperature_periode = df_temperature_resampled[df_temperature_resampled.index.isin(data_periode_resampled.index)]
            
            # Fusion des consommations et températures dans un seul DataFrame pour cette période
            df_merged = pd.DataFrame({
                'Consommation': data_periode_resampled,
                'Température': temperature_periode[colonne_temperature]
            }).dropna()  # Supprimer les lignes avec des valeurs NaN
            df_merged['Période'] = periode

            dfs_periode.append(df_merged)

        # Concaténation des données de toutes les périodes
        df_final = pd.concat(dfs_periode)

        # Création d'un subplot avec une colonne et un nombre de lignes égal au nombre de périodes
        fig = make_subplots(
            rows=len(periodes), cols=1,
            subplot_titles=[f"Période: {periode}" for periode in periodes],
            vertical_spacing=0.1
        )

        # Ajout de chaque période dans un sous-graphe
        for idx, periode in enumerate(periodes):
            data = df_final[df_final['Période'] == periode]
            fig.add_trace(
                go.Scatter(
                    x=data['Consommation'],
                    y=data['Température'],
                    mode='markers',
                    name=f"Consommation vs Température - {periode}",
                    marker=dict(color=couleurs_periodes[idx], size=15),  # Utilisation de la couleur pour chaque période
                ),
                row=idx + 1, col=1
            )

            # Ajout de la tendance linéaire pour chaque période
            if not data.empty:
                trendline = px.scatter(data, x='Consommation', y='Température', trendline="ols")
                trendline_data = trendline.data[1]  # La tendance est la deuxième trace
                fig.add_trace(trendline_data, row=idx + 1, col=1)

        # Personnalisation du layout
        fig.update_layout(
            height=500 * len(periodes),  # Hauteur ajustable pour chaque période
            title="Relation entre Consommation électrique et Température par Période",
            title_font=dict(family="Times New Roman", size=24),
            xaxis_title="Température (°C)",
            yaxis_title="Consommation (kWh)",
            font=dict(family="Times New Roman", size=14)
        )

        # Ajustement des titres des axes pour chaque sous-graphe
        fig.update_xaxes(title_text="Consommation (kWh)")
        fig.update_yaxes(title_text="Température (°C)")

        # Afficher le graphique dans Streamlit
        st.plotly_chart(fig)
    else:
        st.error("Aucune donnée à afficher.")

def get_meteo(latitude, longitude):
    """ Récupère la météo en temps réel via une API météo """
    API_KEY = "982d71c00341c1412d44c7da4de793d4" 
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={latitude}&lon={longitude}&appid={API_KEY}&units=metric&lang=fr"

    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        meteo = {
            "Température": f"{data['main']['temp']}",
            "Ressenti": f"{data['main']['feels_like']}",
            "Humidité": f"{data['main']['humidity']}",
            "Conditions": data["weather"][0]["description"].capitalize()
        }
        return meteo
    else:
        return None

# Charger les données depuis un fichier Excel (remplace "chemin_du_fichier.xlsx" par le vrai chemin)
@st.cache_data
def charger_donnees():
    df = pd.read_excel("C:/Users/utilisateur/Desktop/NHOOD/Testes/projets/Postes techniques actifs.xlsx", sheet_name="Infos périmètres")
    return df

def detecter_pays(adresse, code_postal):
    geolocator = Nominatim(user_agent="geoapi")
    location = geolocator.geocode(f"{adresse}, {code_postal}")
    return location.address.split(",")[-1].strip() if location else ""

def infos_perimetre():
    st.subheader("📍 Informations sur le périmètre", help="Remplissez les informations du site ci-dessous")
    typologie = st.radio("🏗️ Typologie", ["Tertiaire", "Industriel"])
    
    # Charger les données
    df = charger_donnees()
    
    with st.container():
        col1, col2, col3 = st.columns(3)
        
        with col1:
            ville_selectionnee = st.selectbox("🏙️ Ville", options=["Sélectionner une ville"] + df["Ville"].dropna().unique().tolist())
            if ville_selectionnee != "Sélectionner une ville":
                donnees_ville = df[df["Ville"] == ville_selectionnee].iloc[0]
                adresse = donnees_ville["Adresse"]
                code_postal = donnees_ville["Code postal"]
                latitude = donnees_ville["Latitude"]
                longitude = donnees_ville["Longitude"]
            else:
                adresse = st.text_input("🏠 Adresse")
                code_postal = st.text_input("🏤 Code postal")
                latitude = st.number_input("🗺️ Latitude", format="%.6f", step=0.000001)
                longitude = st.number_input("🗺️ Longitude", format="%.6f", step=0.000001)
            
            pays = detecter_pays(adresse, code_postal) if adresse and code_postal else ""
            if not pays:
                pays = st.text_input("🌍 Pays (facultatif)")
        
        with col2:
            surface = st.number_input("🗺️ Superficie m²")
            energie = st.text_input("⚡ Fluide Utilisé", placeholder="Ex: RCU, Electricité, Gaz, Eau")
        
        with col3:
            raison_sociale = st.text_input("🏢 Raison sociale", placeholder="Ex: Nom de l'entreprise")
    
    # Stockage des informations
    Informations_du_perimetre = {
        "Adresse": adresse,
        "Code postal": code_postal,
        "Ville": ville_selectionnee if ville_selectionnee != "Sélectionner une ville" else "",
        "Pays": pays,
        "Raison Sociale": raison_sociale,
        "Fluide (s)": energie,
        "Superficie m²": surface,
        "Latitude": latitude,
        "Longitude": longitude
    }
    
    # Affichage des informations saisies
    with st.container():
        col_info, col_map, col_meteo = st.columns([2, 3, 2])
        
        with col_info:
            st.markdown("<h3 style='font-family:Times New Roman; color:LightSeaGreen;'>📋 Informations du périmètre d'analyse</h3>", unsafe_allow_html=True)
            st.json(Informations_du_perimetre)
        
        with col_map:
            if latitude and longitude:
                st.markdown("<h3 style='font-family:Times New Roman; color:LightSeaGreen;'>🗺️ Localisation du périmètre d'analyse</h3>", unsafe_allow_html=True)
                st.map(pd.DataFrame({"lat": [latitude], "lon": [longitude]}))
        
        with col_meteo:
            if latitude and longitude:
                meteo = get_meteo(latitude, longitude)
                if meteo:
                    st.markdown(
                        "<h3 style='font-family:Times New Roman; color:LightSeaGreen;'>🌤️ Conditions climatiques actuelles</h3>",
                        unsafe_allow_html=True
                    )
                    st.markdown(f"<p style='font-family:Times New Roman; color:LightSeaGreen;'><b>🌡️ Température :</b> {meteo['Température']}°C</p>", unsafe_allow_html=True)
                    st.markdown(f"<p style='font-family:Times New Roman; color:LightSeaGreen;'><b>🌡️ Ressenti :</b> {meteo['Ressenti']}°C</p>", unsafe_allow_html=True)
                    st.markdown(f"<p style='font-family:Times New Roman; color:LightSeaGreen;'><b>💧 Humidité :</b> {meteo['Humidité']}%</p>", unsafe_allow_html=True)
                    st.markdown(f"<p style='font-family:Times New Roman; color:LightSeaGreen;'><b>☁️ Conditions :</b> {meteo['Conditions']}</p>", unsafe_allow_html=True)
                    
                    # Affichage des données météo sous forme de graphique
                    df_meteo = pd.DataFrame({
                        "Paramètre": ["Température", "Ressenti", "Humidité"],
                        "Valeur": [meteo["Température"], meteo["Ressenti"], meteo["Humidité"]]
                    })
                    
                    fig = px.bar(df_meteo, x="Paramètre", y="Valeur", text="Valeur", color="Paramètre", 
                                 title="Données météorologiques actuelles", labels={"Valeur": "Valeur mesurée"})
                    fig.update_traces(textposition="outside")
                    st.plotly_chart(fig)
                else:
                    st.error("❌ Impossible de récupérer la météo. Vérifiez la connexion ou l'API.")
    
    return Informations_du_perimetre

def by_analyse():
    global colonne_p10, data_periode

    cal_debut_dt = pd.to_datetime(cal_debut)
    cal_fin_dt = pd.to_datetime(cal_fin)

    all_data = analyse()
    if all_data is None or all_data.empty:
        st.error("Aucune donnée disponible.")
        return

    data_periode = all_data
    if not pd.api.types.is_datetime64_any_dtype(data_periode["Date"]):
        data_periode["Date"] = pd.to_datetime(data_periode["Date"])

    data_mois_actuel = data_periode
    consommation_actuelle = data_mois_actuel[colonne_p10].sum()

    st.markdown(
        f"<h3 style='color: Lightseagreen; font-family: Times New Roman; font-size: 24px;'>⚡ {colonne_p10} : **{consommation_actuelle:.0f} kWh** mesurées entre le {cal_debut_dt.date()} au {cal_fin_dt.date()} </h3>",
        unsafe_allow_html=True
    )

    if "Période" in data_periode.columns:
        periodes_uniques = data_periode["Période"].unique()
        colonnes = st.columns(len(periodes_uniques))

        for i, periode in enumerate(periodes_uniques):
            with colonnes[i]:
                st.markdown(
                    f"""
                    <div style="
                        border: 1px solid lightSeaGreen;
                        padding: 1px;
                        border-radius: 1px;
                        margin-bottom: 1px;
                        background-color: #f5f5f5;
                    ">
                    """,
                    unsafe_allow_html=True
                )

                data_période_actuel = data_mois_actuel[data_mois_actuel["Période"] == periode]
                somme_actuelle = data_période_actuel[colonne_p10].sum()
                duree = 14 if "08h-22h" in periode else 3 if "05h-08h" in periode else 7 if "22h-05h" in periode else 1

                st.markdown(f"<h4 style='color: LightSeaGreen; font-family: Times New Roman; font-size: 24px;'>⌚ {periode}</h4>", unsafe_allow_html=True)
                st.markdown(f"<p style='color: MediumAquamarine; font-family: Times New Roman; font-size: 20px;'>⚡ Consommation de la période : <b>{somme_actuelle:.2f} kWh</b></p>", unsafe_allow_html=True)
                st.markdown(f"<p style='color: PaleGreen; font-family: Times New Roman; font-size: 20px;'>💰 Coût estimé de la période : <b>{somme_actuelle * 0.17:.2f} €</b></p>", unsafe_allow_html=True)
                st.markdown(f"<p style='color: yellowGreen; font-family: Times New Roman; font-size: 16px;'> ℹ️ Durée de la période : {duree} heures/jour</p>", unsafe_allow_html=True)
                st.markdown(
                    f"""
                    <div style="
                        border: 1px solid lightSeaGreen;
                        padding: 1px;
                        border-radius: 1px;
                        margin-bottom: 1px;
                        background-color: #f5f5f5;
                    ">
                    """,
                    unsafe_allow_html=True
                )
                st.markdown("</div>", unsafe_allow_html=True)

                # Tracé du graphique
                color_scale = ['ForestGreen', 'red']
                fig_histogram = px.bar(
                    data_période_actuel,
                    x="Date",
                    y=colonne_p10,
                    title=f'<b>Électricité en {periode}',
                    labels={colonne_p10: f'<b> Énergies (kWh)'},
                    color=colonne_p10,
                    color_continuous_scale=color_scale
                )

                fig_histogram.update_layout(
                    font=dict(
                        family="Times New Roman",
                        size=24,
                        color="black"
                    ),
                    title=dict(
                        text=f'<b>Électricité en {periode}</b>',
                        font=dict(
                            size=24,
                            family="Times New Roman",
                            color="Lightseagreen"  # Vous pouvez changer cette couleur
                        )
                    )
                )


                st.plotly_chart(fig_histogram, use_container_width=True)

                # Ajout du champ de commentaire
                key_comment = f"comment_{periode}"
                valeurs_str = "\n".join(
                    [f"- {row['Date'].strftime('%Y-%m-%d %H:%M')} : {row[colonne_p10]:.2f} kWh" for _, row in data_période_actuel.iterrows()]
                )
                texte_par_defaut = f"Données Aberrantes (hors consommations attendues) :\n{valeurs_str}\n\nAnalyse : "

                st.markdown(
                    "<h4 style='color: LightSeaGreen; font-family: Times New Roman;'>📝 Constats sur les pas de mesures</h>", 
                    unsafe_allow_html=True
                )
                comment = st.text_area("", key=key_comment, value=texte_par_defaut, height=150)

                if key_comment not in st.session_state:
                    st.session_state[key_comment] = comment

def graphe_by_analyse():

    # Convertir cal_debut et cal_fin en datetime pour la comparaison
    cal_debut_dt = pd.to_datetime(cal_debut)  # Conversion de la date en datetime
    cal_fin_dt = pd.to_datetime(cal_fin)  # Conversion de la date en datetime
    global colonne_p10
    all_data = analyse()
    consommation = all_data[colonne_p10].sum()

    # Vérifier si all_data n'est pas None
    if all_data is not None and not all_data.empty:
        # Initialiser la figure pour l'histogramme
        fig_histogram = go.Figure()


        # Récupérer toutes les valeurs uniques de "Période"
        periodes = all_data['Période'].unique()

        # Définir les couleurs pour chaque période
        couleurs_periodes = ["Blue", "MediumSeaGreen", "Red"]
        

        # Boucler sur chaque période pour ajouter des barres de l'histogramme
        for idx, periode in enumerate(periodes):
            data_periode = all_data[(all_data['Période'] == periode) & (all_data[colonne_p10] > 0)]

            # Convertir 'Date' en index de type DatetimeIndex
            data_periode = data_periode.set_index('Date')
            data_periode.index = pd.to_datetime(data_periode.index)

            # Appliquer le resample pour une agrégation par intervalles de 10 minutes
            data_periode_resampled = data_periode[colonne_p10].resample("10min").mean()

            # Ajouter une trace de barre pour chaque période avec sa couleur
            fig_histogram.add_trace(
                go.Bar(
                    x=data_periode_resampled.index,
                    y=data_periode_resampled,
                    name=str(periode),
                    marker=dict(color=couleurs_periodes[idx % len(couleurs_periodes)]),  # Couleur pour chaque période
                    opacity=0.8  # Opacité des barres
                )
            )


        # Personnalisation des titres et des polices pour l'histogramme
        fig_histogram.update_layout(
            title=f'{colonne_p10} du {cal_debut_dt.date()} au {cal_fin_dt.date()} <br> Energie consommée : {consommation:.2f} kWh',
            xaxis_title='Date',
            yaxis_title=f'Consommations en kWh',
            title_font=dict(family="Times New Roman", size=18),
            xaxis_title_font=dict(family="Times New Roman", size=18),
            yaxis_title_font=dict(family="Times New Roman", size=18),
            legend_title_font=dict(family="Times New Roman", size=18),
            legend_font=dict(family="Times New Roman", size=18),
            font=dict(family="Times New Roman", size=18)
        )
        # Afficher l'histogramme dans Streamlit
        st.plotly_chart(fig_histogram)


    else:
        st.error("Aucune donnée à afficher.")

def graphe_analyse_plage_fonctionnement():
    cal_debut_dt = pd.to_datetime(cal_debut)
    cal_fin_dt = pd.to_datetime(cal_fin)
    global colonne_p10
    all_data = analyse()
    consommation = all_data[colonne_p10].sum()

    if all_data is not None and not all_data.empty:
        st.write("### Définir les plages horaires des activés afin d'identifier les heures d'inefficacité pour une amélioration")

        plage_horaires = st.text_area(
            "👉Entrez les heures d'activités relatives au point de mesures. ℹ️ Format : HH:MM-HH:MM, séparées par des virgules",
            "08:00-22:00, 05:00-07:59",
            key="plage_horaires",
        )

        st.markdown(
            """
            <style>
            textarea { font-family: 'Times New Roman', Times, serif !important; font-size: 20px; }
            </style>
            """,
            unsafe_allow_html=True,
        )

        def parse_plages(plage_str):
            plages = []
            for plage in plage_str.split(","):
                try:
                    debut, fin = plage.strip().split("-")
                    debut_time = pd.to_datetime(debut, format="%H:%M").time()
                    fin_time = pd.to_datetime(fin, format="%H:%M").time()
                    plages.append((debut_time, fin_time))
                except:
                    st.error("Format incorrect. Veuillez entrer sous la forme HH:MM-HH:MM.")
                    return []
            return plages

        plages_fonctionnement = parse_plages(plage_horaires)

        if not plages_fonctionnement:
            return

        consommation_hors_plages = all_data[
            ~all_data['Date'].dt.time.isin(
                [t for plage in plages_fonctionnement for t in pd.date_range(plage[0].strftime('%H:%M'), plage[1].strftime('%H:%M'), freq='10min').time]
            ) & (all_data[colonne_p10] > 0)
        ][colonne_p10].sum()

        if consommation_hors_plages > 0:
            consommation_hors_plages_formatee = f"{consommation_hors_plages:,.2f}".replace(",", " ")
            plages_str = ", ".join([f"<b>{p[0].strftime('%H:%M')}-{p[1].strftime('%H:%M')}</b>" for p in plages_fonctionnement])

            commentaire_base = (
                f"Les mesures du <b><span > {colonne_p10} </span></b>, ont enregistré des consommations d'une somme de <b><span style='color:red'>{consommation_hors_plages_formatee} kWh</span></b> sur la période du "
                f"{cal_debut_dt.date()} au {cal_fin_dt.date()} hors des plages "
                f"de fonctionnement par défaut({plages_str})."
            )

            afficher_zone = st.checkbox("Ajouter ou modifier un commentaire", value=True)
            commentaire_utilisateur = ""

            if afficher_zone:
                commentaire_utilisateur = st.text_area(
                    "📝 Saisissez vos commentaires complémentaires ici :",
                    height=150,
                    key="commentaire_utilisateur"
                )

            commentaire_complet = commentaire_base
            if commentaire_utilisateur.strip():
                commentaire_complet += "<br><br>" + commentaire_utilisateur.replace("\n", "<br>")

            st.markdown(
                f"<p style='font-family: Times New Roman; font-size: 18px;'>{commentaire_complet}</p>",
                unsafe_allow_html=True
            )


        # Construction du graphique
        fig_histogram = go.Figure()

        for periode in all_data['Période'].unique():
            data_periode = all_data[(all_data['Période'] == periode) & (all_data[colonne_p10] > 0)]
            data_periode = data_periode.set_index('Date')
            data_periode.index = pd.to_datetime(data_periode.index)
            data_periode_resampled = data_periode[colonne_p10].resample("10min").mean()
            somme_periode = data_periode[colonne_p10].sum()
            somme_periode_formatee = f"{somme_periode:,.0f}".replace(",", " ")

            couleurs = [
                "green" if any(debut <= dt.time() <= fin for debut, fin in plages_fonctionnement) else "red"
                for dt in data_periode_resampled.index
            ]

            fig_histogram.add_trace(
                go.Bar(
                    x=data_periode_resampled.index,
                    y=data_periode_resampled,
                    name=f"{periode} <br> Consommation de la période : {somme_periode_formatee} kWh",
                    marker=dict(color=couleurs),
                    opacity=0.8
                )
            )

        fig_histogram.update_layout(
            title=f'{colonne_p10} du {cal_debut_dt.date()} au {cal_fin_dt.date()} <br> Energie consommée : {consommation:,.2f} kWh'.replace(",", " "),
            xaxis_title='Date',
            yaxis_title=f'Consommations en kWh',
            title_font=dict(family="Times New Roman", size=18),
            xaxis_title_font=dict(family="Times New Roman", size=18),
            yaxis_title_font=dict(family="Times New Roman", size=18),
            legend_title_font=dict(family="Times New Roman", size=18),
            legend_font=dict(family="Times New Roman", size=18),
            font=dict(family="Times New Roman", size=18)
        )

        st.plotly_chart(fig_histogram)


def graphe_bar_by_analyse():
    # Vérification de cal_debut et cal_fin
    if 'cal_debut' not in globals() or 'cal_fin' not in globals():
        st.error("Les dates de début et de fin ne sont pas définies.")
        return

    cal_debut_dt = pd.to_datetime(cal_debut)  # Conversion de la date en datetime
    cal_fin_dt = pd.to_datetime(cal_fin)  # Conversion de la date en datetime

    global colonne_p10
    all_data = analyse()  # Récupération des données
    consommation = all_data[colonne_p10].sum()

    if all_data is not None and not all_data.empty:
        # Vérifier si la colonne 'Période' est présente
        if 'Période' not in all_data.columns:
            st.error("La colonne 'Période' est absente des données.")
            return

        # Calculer la somme de la consommation pour chaque période
        df_somme = all_data.groupby('Période', as_index=False)[colonne_p10].sum()

        # Tracer le bar chart avec Plotly Express
        fig = px.bar(
            df_somme, 
            x='Période', 
            y=colonne_p10, 
            text=colonne_p10, 
            title=f'{colonne_p10} du {cal_debut_dt.date()} au {cal_fin_dt.date()} <br> Energie consommée : {consommation:.2f} kWh',
            labels={colonne_p10: "Consommation (kWh)", "Période": "Périodes"},
            color='Période',  # Coloration différente par période
            color_discrete_sequence=["Red", "Blue", "MediumSeaGreen"]  # Palette de couleurs
        )

        # Mise en forme du graphique
        fig.update_traces(
            texttemplate='%{text:.0f} kWh',  # Format du texte
            textposition='inside',  # Position du texte à l'intérieur des barres
            insidetextfont=dict(color="white")  # Texte en blanc pour être visible
        )

        fig.update_layout(
            xaxis_title="Périodes",
            yaxis_title="Energie Consommée (kWh)",
            title_font=dict(family="Times New Roman", size=20),
            xaxis_title_font=dict(family="Times New Roman", size=20),
            yaxis_title_font=dict(family="Times New Roman", size=20),
            legend_title_font=dict(family="Times New Roman", size=20),
            legend_font=dict(family="Times New Roman", size=20),
            font=dict(family="Times New Roman", size=20),
            
        )

        # Affichage du graphique dans Streamlit
        st.plotly_chart(fig)

    else:
        st.error("Aucune donnée à afficher.")

def afficher_lien_gtb():
    """Fonction pour charger un fichier Excel et ouvrir un lien GTB dans un nouvel onglet."""
    
    st.subheader("🔗 Accés à la gestion automatisée (xlxs)")

    # Charger le fichier Excel une seule fois et stocker dans session_state pour éviter une répétition
    if "uploaded_file" not in st.session_state:
        st.session_state.uploaded_file = None

    # Afficher le bouton de téléchargement seulement si aucun fichier n'est chargé
    if st.session_state.uploaded_file is None:
        uploaded_file = st.file_uploader("📂 Téléchargez un fichier Excel", type=["xls", "xlsx"])

        if uploaded_file:
            st.session_state.uploaded_file = uploaded_file
            st.success(f"✅ Fichier chargé : {uploaded_file.name}")

    else:
        # Si un fichier a été téléchargé, on le lit et on affiche le contenu
        df = pd.read_excel(st.session_state.uploaded_file)

        # Vérifier la colonne contenant des liens
        colonne_lien = None
        for col in df.columns:
            if df[col].astype(str).str.startswith("http").any():
                colonne_lien = col
                break

        if colonne_lien:
            # Afficher toute la DataFrame avec la colonne des liens
            liens_df = df.copy()  # On garde toute la DataFrame
            # Sélectionner un lien GTB à partir du tableau
            lien_selectionne = st.selectbox("📌 Choisissez un lien GTB :", df[colonne_lien].dropna().unique())
            # Filtrer la ligne correspondante au lien sélectionné
            ligne_selectionnee = liens_df[liens_df[colonne_lien] == lien_selectionne]

            if not ligne_selectionnee.empty:
                # Ajout d'un titre stylisé au-dessus du DataFrame
                st.markdown(
                    "<h3 style='color: LightSeaGreen; font-family: Times New Roman;</h3>", 
                    unsafe_allow_html=True
                )

                # Affichage du tableau avec style
                st.dataframe(
                    ligne_selectionnee.style.set_properties(**{
                        'background-color': 'white',
                        'color': 'LightSeaGreen',
                        'border-color': 'LightSeaGreen',
                        'font-family': 'Times New Roman'
                    })
                )


            # Bouton pour ouvrir le lien GTB dans un nouvel onglet
            if lien_selectionne and st.button("🔄 Se connecter à la GTB"):
                # Utiliser un lien HTML pour ouvrir l'URL dans un nouvel onglet
                st.markdown(f'<a href="{lien_selectionne}" target="_blank">Cliquez ici pour ouvrir le lien dans un nouvel onglet</a>', unsafe_allow_html=True)

        else:
            st.warning("⚠️ Aucune colonne contenant des liens n'a été trouvée dans le fichier.")

# Fonction pour afficher les graphiques des sommes journalières en courbe, avec les courbes de maximums et minimums sur des pas horaires de 1h
def graphe_ecart_des_mesures():

    global colonne_p10
    all_data = analyse()

    # Vérifier si all_data n'est pas None
    if all_data is not None and not all_data.empty:
        # Initialiser la figure pour les courbes
        fig_line = go.Figure()

        # Récupérer toutes les valeurs uniques de "Période"
        periodes = all_data['Période'].unique()

        # Définir des couleurs spécifiques pour chaque période
        couleurs = ["Yellow", "MediumSeaGreen", "Red", "Blue"]

        # Boucler sur chaque période pour tracer une courbe continue
        for i, periode in enumerate(periodes):
            data_periode = all_data[(all_data['Période'] == periode) & (all_data[colonne_p10] > 0)]

            # Convertir 'Date' en index de type DatetimeIndex
            data_periode = data_periode.set_index('Date')
            data_periode.index = pd.to_datetime(data_periode.index)

            # Appliquer le resample pour une agrégation par intervalles de 1 heure
            data_periode_resampled = data_periode[colonne_p10].resample("30min").agg(['max', 'min'])

            # Couleur pour la période actuelle
            couleur_periode = couleurs[i % len(couleurs)]

            # Ajouter une trace pour la courbe des valeurs maximales de la période (ligne continue)
            fig_line.add_trace(
                go.Scatter(
                    x=data_periode_resampled.index,
                    y=data_periode_resampled['max'],
                    mode='lines',
                    name=f'{periode} - Maximum',
                    line=dict(width=2, color=couleur_periode)  # Ligne continue de couleur de la période
                )
            )

            # Ajouter une trace pour la courbe des valeurs minimales de la période (ligne continue)
            fig_line.add_trace(
                go.Scatter(
                    x=data_periode_resampled.index,
                    y=data_periode_resampled['min'],
                    mode='lines',
                    name=f'{periode} - Minimum',
                    line=dict(width=2, color=couleur_periode)  # Ligne continue de couleur de la période
                )
            )

        # Personnalisation des titres et des polices
        fig_line.update_layout(
            title='Écarts des mesures P10 des consommations électriques',
            xaxis_title='Date',
            yaxis_title=f'Mesures {colonne_p10}',
            title_font=dict(family="Times New Roman", size=24),
            xaxis_title_font=dict(family="Times New Roman", size=20),
            yaxis_title_font=dict(family="Times New Roman", size=20),
            legend_title_font=dict(family="Times New Roman", size=20),
            legend_font=dict(family="Times New Roman", size=18),
            font=dict(family="Times New Roman", size=14),
            colorway=couleurs  # Palette de couleurs pour les périodes
        )

        # Afficher le graphique dans Streamlit
        st.plotly_chart(fig_line)
    else:
        st.error("Aucune donnée à afficher.")

# Fonction pour afficher le tableau des périodes de surconsommation
def afficher_tableau_périodes_surcharge(data_periode, table_width=800):
    # Texte personnalisé avec du style
    st.markdown(
        "<p style='font-size:24px; font-family:Time new roman; color:White; font-weight:bold;'>Mesures P10 des Consommations Électriques</p>",
        unsafe_allow_html=True
    )

    # Appliquer la fonction pour ajouter la colonne "Différence"
    data_periode_diff = ajouter_diff_10min(data_periode)

    # Vérifier si la colonne 'Date' existe dans le DataFrame
    if 'Date' in data_periode_diff.columns:
        # Utiliser la colonne 'Date' comme index
        data_periode_diff.set_index('Date', inplace=True)
    else:
        st.error("La colonne 'Date' est introuvable dans les données.")
        return

    # Sélectionner les colonnes pertinentes pour l'affichage
    derives = data_periode_diff[['Période', f'{colonne_p10}', 'Différence des P10']].copy()
    derives.columns = ['Période', f'{colonne_p10}', 'Différence des P10 en (kWh)']

    # Appliquer un gradient de couleur uniquement aux colonnes numériques
    st.write(
        derives.style
        .background_gradient(subset=[f'{colonne_p10}', 'Différence des P10 en (kWh)'], cmap='GnBu')  # Gradient pour les colonnes numériques
        .set_properties(subset=['Période'], **{'background-color': 'lightgray', 'color': 'black'})  # Couleur unie pour la colonne "Période"
        .set_table_styles([
            {'selector': 'thead th', 'props': 'font-weight: bold; background-color: Teal; color: white; text-align: center;'},  # En-têtes
            {'selector': 'td', 'props': 'text-align: center;'}  # Cellules centrées
        ])
        .set_properties(**{'width': f'{table_width}px'})  # Largeur du tableau
    )

# Fonction pour ajouter la différence sur 10 minutes
def ajouter_diff_10min(df):
    df.index = pd.to_datetime(df.index)
    
    # Calculer la différence entre les périodes de 10 minutes consécutives pour la colonne_p10
    df['Différence des P10'] = df[colonne_p10].diff()

    # Garder la colonne 'Date' comme index pour une meilleure lisibilité
    df.reset_index(inplace=True)
    
    return df 

# Fonction pour afficher la somme des dépassements pour une période donnée
def afficher_somme_depassements(data_période, periode, seuil):
    # Convertir cal_debut et cal_fin en datetime pour la comparaison
    cal_debut_dt = pd.to_datetime(cal_debut)  # Conversion de la date en datetime
    cal_fin_dt = pd.to_datetime(cal_fin)  # Conversion de la date en datetime
    if data_période.empty:
        st.warning(f"Aucune donnée disponible pour la période : {periode}")
        return
    somme_depassements = data_période["Dépassement"].sum()
    st.write(f"#### Surconsommations de **{somme_depassements:.2f}** kWh constatées sur la période  du {cal_debut_dt.date()} au {cal_fin_dt.date()}")
    
# Fonction pour afficher les graphiques, données mesurées et comportement de évolution pour chaque période de fonctionnement 
def thiambar():
    global colonne_p10, cal_debut, cal_fin

    # Analyse des données
    data_periode = analyse()
    
    # Assurez-vous que la colonne 'Date' est bien au format datetime et définissez-la comme index
    if 'Date' in data_periode.columns:
        data_periode['Date'] = pd.to_datetime(data_periode['Date'], errors='coerce')
        data_periode.set_index('Date', inplace=True)
    else:
        st.error("La colonne 'Date' est absente des données.")

    # Créer une colonne '10min' pour les intervalles
    data_periode['10min'] = data_periode.index.floor('10T')

    # Obtenir la liste des périodes
    options_periodes = list(data_periode["Période"].unique())

    # Dictionnaire pour stocker les seuils par période
    seuils_par_periode = {}

    st.sidebar.write("### Définir les seuils par période")

    # Interface utilisateur pour définir les seuils par période
    for periode in options_periodes:
        data_période = data_periode[data_periode["Période"] == periode]
        min_val = float(data_période[colonne_p10].min())
        max_val = float(data_période[colonne_p10].max())

        # Ajuster dynamiquement la valeur par défaut
        default_value = min(5.0, max_val) if min_val <= 5.0 <= max_val else max(min_val, max_val)

        # Permettre des seuils sans valeur minimale
        seuil = st.sidebar.number_input(
            f"Seuil pour {periode}",
            min_value=None,  # Pas de valeur minimale
            max_value=max_val,
            value=default_value,  # Valeur par défaut ajustée dynamiquement
            step=0.1,
            key=f"seuil_{periode}"
        )
        seuils_par_periode[periode] = seuil

    # Ajout de la colonne "Dépassement" par période
    data_periode["Dépassement"] = data_periode.apply(
        lambda row: max(0, row[colonne_p10] - seuils_par_periode[row["Période"]]),
        axis=1
    )

    # Options pour sélectionner la période
    options_periodes = ["Toutes les périodes"] + options_periodes
    periode_selectionnee = st.sidebar.radio(
        "Sélectionner la période à afficher :",
        options_periodes,
        key="periode_selector"
    )

    if periode_selectionnee == "Toutes les périodes":
        for periode in seuils_par_periode.keys():
            data_période = data_periode[data_periode["Période"] == periode]

            st.write(f"### {periode}")

            # ** Affichage des dépassements **
            afficher_somme_depassements(data_période, periode, seuils_par_periode[periode])
            afficher_graphe_et_tableau(data_période, periode)
    else:
        data_période = data_periode[data_periode["Période"] == periode_selectionnee]

        # ** Affichage de la somme **
        somme = data_période[colonne_p10].sum()
        st.write(f"### {periode_selectionnee}")
        st.write(f"La somme mesurée sur cette période est de : **{somme:.2f}** kWh")

        # ** Affichage des dépassements **
        afficher_somme_depassements(data_période, periode_selectionnee, seuils_par_periode[periode_selectionnee])
        afficher_graphe_et_tableau(data_période, periode_selectionnee)

# Fonction pour afficher le graphique et gérer les commentaires
def afficher_graphe_et_tableau(data_période, periode):
    global colonne_p10

    # Grouper par intervalles de 10 minutes et sommer les valeurs d'énergie (colonne_p10)
    data_histo = data_période.groupby(['10min'])[colonne_p10].sum().reset_index()

    # Définir le dégradé de couleurs de mediumseagreen à rouge
    color_scale = ['Green', 'mediumseagreen', 'Orange', 'red']  # Faible vers fort

    # Créer un graphique de barres avec Plotly Express pour les intervalles de 10 minutes
    fig_histogram = px.bar(
        data_histo,
        x='10min',
        y=colonne_p10,
        title=f'<b>Évolution des consommations électriques en {periode} : {colonne_p10}',
        labels={'10min': '<b>Mesures électriques (pas de 10 min)', colonne_p10: f'<b>Intensité des P10<br>en (kWh)'},
        color=colonne_p10,
        color_continuous_scale=color_scale
    )

    # Personnalisation des polices avec Times New Roman et taille ajustée
    fig_histogram.update_layout(
        font=dict(
            family="Times New Roman",
            size=24,
            color="black"
        ),
        title=dict(font=dict(size=24, family="Times New Roman")),
        xaxis=dict(title=dict(font=dict(size=20, family="Times New Roman"))),
        yaxis=dict(title=dict(font=dict(size=20, family="Times New Roman")))
    )



    # Initialiser les états dans st.session_state si nécessaire
    if f"masquer_champ_{periode}" not in st.session_state:
        st.session_state[f"masquer_champ_{periode}"] = False
    if f"commentaire_{periode}" not in st.session_state:
        st.session_state[f"commentaire_{periode}"] = ""

    # Afficher le graphique sur toute la largeur de la page
 
    st.plotly_chart(fig_histogram, use_container_width=True)
   

    # Créer deux colonnes : col1 (commentaires) et col2 (tableaux)
    col1, col2 = st.columns([5, 5])

    # Gestion des commentaires dans col1
    with col1:
        # Bouton pour masquer/montrer le champ de texte
        if st.button(f"O/N", key=f"toggle_button_{periode}"):
            st.session_state[f"masquer_champ_{periode}"] = not st.session_state[f"masquer_champ_{periode}"]

        # Si le champ de texte est visible
        if not st.session_state[f"masquer_champ_{periode}"]:
            commentaire = st.text_area(
                label=f"Commentaires sur les dépassements (Graphique : {periode})",
                placeholder="Ajoutez vos observations ici...",
                key=f"commentaire_graphe_{periode}",
                value=st.session_state[f"commentaire_{periode}"]
            )
            # Sauvegarder le commentaire dans st.session_state
            st.session_state[f"commentaire_{periode}"] = commentaire

        # Affichage formaté du commentaire saisi (toujours visible)
        if st.session_state[f"commentaire_{periode}"]:
            commentaire_formate = st.session_state[f"commentaire_{periode}"].replace("\n", "<br>")
            st.markdown(
                f"<div style='font-family: Times New Roman; font-size: 18px; color: Black;'>"
                f"Constats sur la période : {periode}<br>{commentaire_formate}"
                f"</div>",
                unsafe_allow_html=True
            )

    # Gestion des tableaux dans col2
    with col2:
        afficher_tableau_périodes_surcharge(data_période)

# Fonction principale pour les plages de temps
def analyse():
    global df_energie, colonne_p10
    
    # Filtrer les données pour la période sélectionnée
    debut_periode = cal_debut
    fin_periode = cal_fin

    if df_energie is not None:
        df_energie = df_energie[(df_energie.index.date >= debut_periode) & (df_energie.index.date <= fin_periode)]

        # Définir les périodes fixes
        heures_mode_reduit = (5, 8)
        heures_occupation = (8, 22)

        # Filtrer pour chaque période
        mode_reduit = df_energie[
            (df_energie.index.hour >= heures_mode_reduit[0]) & (df_energie.index.hour < heures_mode_reduit[1])
        ].copy()
        occupation = df_energie[
            (df_energie.index.hour >= heures_occupation[0]) & (df_energie.index.hour < heures_occupation[1])
        ].copy()

        inoccupation_22h_05h = df_energie[
            (df_energie.index.hour >= 22) | (df_energie.index.hour < 5)
        ].copy()

        # Ajouter les étiquettes pour les périodes
        mode_reduit['Période'] = 'Mode Réduit (05h-08h)'
        occupation['Période'] = 'Occupation (08h-22h)'
        inoccupation_22h_05h['Période'] = 'Inoccupation (22h-05h)'

        # Regrouper toutes les périodes
        all_data = pd.concat([mode_reduit, occupation, inoccupation_22h_05h])

        # Ajouter la différence toutes les 10 minutes
        all_data = ajouter_diff_10min(all_data)


        # Retourner les données traitées
        return all_data
    else:
        st.error("Aucune donnée énergétique n'a été trouvée.")
        return None

# Fonction pour afficher les graphiques des consommations par période en nuages de points
def graphe_point_temps():
    global colonne_p10
    all_data = analyse()
    consommation = all_data[colonne_p10].sum()

    # Vérifier si all_data n'est pas None
    if all_data is not None and not all_data.empty:
        
        # Tracer le graphique en points
        fig_scatter = px.scatter(
            all_data[all_data[colonne_p10] > 0],  # Exclure les valeurs non positives
            x='Date',  # Utiliser la Date sur l'axe des X
            y=colonne_p10,  # Utiliser la consommation comme axe des Y
            color='Période',
            size=colonne_p10,  # Différencier les points par période
            title=f'Évolution des mesures {colonne_p10} sur la période du {cal_debut} au {cal_fin}<br> Energie consommée : {consommation:.2f} kWh',
            labels={f'{colonne_p10}': 'Energie électrique en (kWh)', 'Date': 'Date'},  # Personnalisation des labels
            color_discrete_sequence=["Blue", "MediumSeaGreen", "Red"]  # Discrétisation des couleurs
        )

        # Mise à jour des polices
        fig_scatter.update_layout(
            title_font=dict(family="Times New Roman", size=24),  # Police et taille du titre
            xaxis_title_font=dict(family="Times New Roman", size=20),  # Police et taille de l'axe X
            yaxis_title_font=dict(family="Times New Roman", size=20),  # Police et taille de l'axe Y
            legend_title_font=dict(family="Times New Roman", size=20),  # Police et taille du titre de la légende
            legend_font=dict(family="Times New Roman", size=20),  # Police et taille de la légende
            font=dict(family="Times New Roman", size=14)  # Police générale
        )

        # Afficher le graphique dans Streamlit
        st.plotly_chart(fig_scatter)
    else:
        st.error("Aucune donnée à afficher.")

# Fonction pour afficher les graphiques des consommations en courbe avec les périodes identifiées
def graphe_courbe_all():
    global colonne_p10
    all_data = analyse()
    consommation = all_data[colonne_p10].sum()
            
    # Vérifier si all_data n'est pas None
    if all_data is not None and not all_data.empty:
        # Initialiser la figure pour les courbes
        fig_line = go.Figure()

        # Récupérer toutes les valeurs uniques de "Période"
        periodes = all_data['Période'].unique()

        # Boucler sur chaque période pour tracer une courbe continue
        for periode in periodes:
            data_periode = all_data[(all_data['Période'] == periode) & (all_data[colonne_p10] > 0)]

            # Convertir 'Date' en index de type DatetimeIndex
            data_periode = data_periode.set_index('Date')
            data_periode.index = pd.to_datetime(data_periode.index)

            # Appliquer le resample pour une agrégation par intervalles de 10 minutes
            data_periode_resampled = data_periode[colonne_p10].resample("10min").mean()

            # Ajouter une trace de courbe pour chaque période
            fig_line.add_trace(
                go.Scatter(
                    x=data_periode_resampled.index,  # Utiliser l'index DatetimeIndex après le resample
                    y=data_periode_resampled,
                    mode='lines',
                    name=str(periode),
                    line=dict(width=2)  # Largeur de ligne pour chaque période
                )
            )
        
        # Personnalisation des titres et des polices
        fig_line.update_layout(
            title=f'Evolution du point de mesure : "{colonne_p10}" sur la période du {cal_debut} au {cal_fin}<br> Energie consommée : {consommation:.2f} kWh',
            xaxis_title='Date',
            yaxis_title='Consommation (kWh)',
            title_font=dict(family="Times New Roman", size=24),
            xaxis_title_font=dict(family="Times New Roman", size=20),
            yaxis_title_font=dict(family="Times New Roman", size=20),
            legend_title_font=dict(family="Times New Roman", size=20),
            legend_font=dict(family="Times New Roman", size=20),  # Police et taille de la légende
            font=dict(family="Times New Roman", size=14),
            colorway=["Blue", "MediumSeaGreen", "Red"]  # Palette de couleurs
        )

        # Afficher le graphique dans Streamlit
        st.plotly_chart(fig_line)
    else:
        st.error("Aucune donnée à afficher.")

# Fonction principale pour filtrer les données
def filtrer_donnees_par_plage(somme_jour, cal_debut, cal_fin):
    # Vérifiez si les dates sont valides et les convertir en pd.Timestamp
    if isinstance(cal_debut, datetime):
        cal_debut = pd.Timestamp(cal_debut)
    if isinstance(cal_fin, datetime):
        cal_fin = pd.Timestamp(cal_fin)

    # Filtrer les données entre cal_debut et cal_fin pour l'année en cours
    df_energie_selection = somme_jour[(somme_jour.index >= cal_debut) & (somme_jour.index <= cal_fin)].copy()

    # Extraire les données pour la même plage de dates de l'année précédente
    cal_debut_prec = cal_debut.replace(year=cal_debut.year - 1)
    cal_fin_prec = cal_fin.replace(year=cal_fin.year - 1)

    # Filtrer en utilisant la plage de dates de l'année précédente
    df_energie_annee_precedente = somme_jour[(somme_jour.index >= cal_debut_prec) & (somme_jour.index <= cal_fin_prec)].copy()

    return df_energie_selection, df_energie_annee_precedente

# Fonction pour afficher les tableaux de données par période d'occupation et inoccupation
def afficher_tableaux_et_graphiques_par_periode():
    # Convertir les dates de début et de fin en datetime
    debut_periode_dt = pd.to_datetime(cal_debut)
    fin_periode_dt = pd.to_datetime(cal_fin)

    # Obtenir les sommes des périodes depuis la fonction talon
    somme_jour, les_talons_combined = talon()

    # Filtrer les données pour la plage sélectionnée
    somme_jour_selection, somme_jour_prec_selection = filtrer_donnees_par_plage(somme_jour, cal_debut, cal_fin)

    # S'assurer que l'index est un DatetimeIndex
    somme_jour_selection.index = pd.to_datetime(somme_jour_selection.index)
    somme_jour_prec_selection.index = pd.to_datetime(somme_jour_prec_selection.index)

    # Calcul des sommes par période (semaine, mois, trimestre, année)
    somme_semaine_selection = somme_jour_selection.resample('W').sum()
    somme_mois_selection = somme_jour_selection.resample('ME').sum()
    somme_trimestre_selection = somme_jour_selection.resample('QE').sum()
    somme_annee_selection = somme_jour_selection.resample('YE').sum()

    somme_semaine_prec_selection = somme_jour_prec_selection.resample('W').sum()
    somme_mois_prec_selection = somme_jour_prec_selection.resample('ME').sum()
    somme_trimestre_prec_selection = somme_jour_prec_selection.resample('QE').sum()
    somme_annee_prec_selection = somme_jour_prec_selection.resample('YE').sum()

    # Supprimer l'heure pour l'affichage, mais garder le DatetimeIndex pour les opérations
    somme_jour_selection_affichage = somme_jour_selection.copy().round(2)
    somme_jour_prec_selection_affichage = somme_jour_prec_selection.copy().round(2)

    somme_jour_selection_affichage.index = somme_jour_selection_affichage.index.date
    somme_jour_prec_selection_affichage.index = somme_jour_prec_selection_affichage.index.date

    somme_semaine_selection.index = somme_semaine_selection.index.date
    somme_semaine_prec_selection.index = somme_semaine_prec_selection.index.date

    somme_mois_selection.index = somme_mois_selection.index.date
    somme_mois_prec_selection.index = somme_mois_prec_selection.index.date

    somme_trimestre_selection.index = somme_trimestre_selection.index.date
    somme_trimestre_prec_selection.index = somme_trimestre_prec_selection.index.date

    somme_annee_selection.index = somme_annee_selection.index.date
    somme_annee_prec_selection.index = somme_annee_prec_selection.index.date

    # Filtrer les données pour la période sélectionnée dans l'année en cours et l'année précédente
    periode_actuelle_selection = somme_jour_selection[(somme_jour_selection.index >= debut_periode_dt) & (somme_jour_selection.index <= fin_periode_dt)]
    periode_precedente_selection = somme_jour_prec_selection[(somme_jour_prec_selection.index >= debut_periode_dt.replace(year=debut_periode_dt.year - 1)) & (somme_jour_prec_selection.index <= fin_periode_dt.replace(year=fin_periode_dt.year - 1))]

    # Ajouter une colonne 'Year' pour distinguer les années
    periode_actuelle_selection['Année'] = 'Année en cours'
    periode_precedente_selection['Année'] = 'Année précédente'

    # Combiner les deux DataFrames
    somme_combined = pd.concat([periode_actuelle_selection, periode_precedente_selection])

    # Réinitialiser l'index pour inclure la colonne Date
    somme_combined.reset_index(inplace=True)

    # Colonnes à tracer
    colonnes_a_tracer = [col for col in ['Talon Nocturne (22h - 05h)', 'Talon en mode Réduit (05h - 08h)', 'Talon Diurne (08h - 22h)'] if col in somme_combined.columns]

    # Réorganiser les données pour le tracé avec un DataFrame 'melted'
    melted_data = somme_combined.melt(id_vars=['Année', 'Date'], value_vars=colonnes_a_tracer, var_name='Période', value_name='Valeur')

    # Filtrer les données pour la période sélectionnée
    periode_selection = somme_jour_selection[(somme_jour_selection.index >= debut_periode_dt) & (somme_jour_selection.index <= fin_periode_dt)]

    # Ajouter une colonne 'Date' pour chaque période
    periode_selection['Date'] = periode_selection.index

    # Réorganiser les données pour le tracé avec un DataFrame 'melted'
    melted_data1 = periode_selection.melt(id_vars=['Date'], value_vars=colonnes_a_tracer, var_name='Période', value_name='Valeur')

    # Stocker toutes les variables dans un dictionnaire
    result = {
        'melted_data': melted_data,
        'melted_data1': melted_data1,
        'colonnes_a_tracer': colonnes_a_tracer,
        'col1': col1,
        'col2': col2,
        'somme_jour_selection_affichage': somme_jour_selection_affichage,
        'somme_semaine_selection': somme_semaine_selection,
        'somme_jour_prec_selection_affichage': somme_jour_prec_selection_affichage,
        'somme_mois_selection': somme_mois_selection,
        'somme_trimestre_selection': somme_trimestre_selection,
        'somme_annee_selection': somme_annee_selection,
        'somme_semaine_prec_selection': somme_semaine_prec_selection,
        'somme_mois_prec_selection': somme_mois_prec_selection,
        'somme_trimestre_prec_selection': somme_trimestre_prec_selection,
        'somme_annee_prec_selection': somme_annee_prec_selection
    }

    return result

# Fonction de coloration basée sur une échelle de couleurs allant du DarkGreen à GreenYellow
def color_teal_to_lightgreensea(val):
    # Dictionnaire des intervalles et des couleurs associées
    color_map = {

        2000: 'SeaGreen',
        1000: 'LightSeaGreen',
        500: 'MediumSeaGreen',
        250: 'LightGreen',
        125: 'SeaGreen',
        65: 'LightSeaGreen',
        50: 'MediumSeaGreen',
        30: 'LightGreen',
    }

        # Boucle à travers les intervalles pour appliquer la couleur
    for threshold, color in color_map.items():
        if val > threshold:
            return f'background-color: {color}; color: black'

    # Valeur très faible, si elle est <= 29
    return 'background-color: Green; color: black'
# Fonction pour les statistiques de l'année en cours
def stat_annee_en_cours():
    global colonne_p10
    # Appel de la fonction pour obtenir toutes les variables
    result = afficher_tableaux_et_graphiques_par_periode()
    
    # Extraire les données nécessaires à partir du dictionnaire 'result'
    somme_jour_selection = result['somme_jour_selection_affichage']
    somme_semaine_selection = result['somme_semaine_selection']
    somme_mois_selection = result['somme_mois_selection']
    somme_trimestre_selection = result['somme_trimestre_selection']
    somme_annee_selection = result['somme_annee_selection']
    col1 = result['col1']


    with col1:
        st.write(f"Consommations journalières de l'Année en cours (kWh) : {colonne_p10}")
        st.dataframe(somme_jour_selection.style.applymap(color_teal_to_lightgreensea).format("{:.2f}"))

        # Tracer le graphique en aires avec Plotly et les couleurs spécifiées
        fig_area = px.area(
            somme_jour_selection, 
            title=f"Evolution des Consommations Journalières  (kWh) {colonne_p10}",
            color_discrete_sequence=['LightGreen', 'Green','Teal']  # Couleurs spécifiées
        )
    # Mise à jour des polices
        fig_area.update_layout(
        title_font=dict(family="Times New Roman", size=20),  # Police et taille du titre
        xaxis_title_font=dict(family="Times New Roman", size=20),  # Police et taille de l'axe X
        yaxis_title_font=dict(family="Times New Roman", size=20),  # Police et taille de l'axe Y
        legend_title_font=dict(family="Times New Roman", size=20),  # Police et taille du titre de la légende
        legend_font=dict(family="Times New Roman", size=20),  # Police et taille de la légende
        font=dict(family="Times New Roman", size=20)  # Police générale
        
    )
        # Afficher le graphique dans Streamlit
        st.plotly_chart(fig_area)
        # Afficher les statistiques descriptives pour les sommes journalières
        st.write("Statistiques descriptives des sommes journalières :")
        st.dataframe(somme_jour_selection.describe().T)

        # Afficher les données hebdomadaires
        st.write("Consommations hebdomadaires de l'Année en cours :")
        st.dataframe(somme_semaine_selection.style.applymap(color_teal_to_lightgreensea).format("{:.2f}"))
        # Afficher les statistiques descriptives pour les sommes journalières
        st.write("Statistiques descriptives des sommes hebdomadaires :")
        st.dataframe(somme_semaine_selection.describe().T)

        # Afficher les données mensuelles
        st.write("Consommations mensuelles de l'Année en cours :")
        st.dataframe(somme_mois_selection.style.applymap(color_teal_to_lightgreensea).format("{:.2f}"))
        # Afficher les statistiques descriptives pour les sommes journalières
        st.write("Statistiques descriptives des consommations mensuelles :")
        st.dataframe(somme_mois_selection.describe().T)

        # Afficher les données trimestrielles
        st.write("Consommations trimestrielles de l'Année en cours :")
        st.dataframe(somme_trimestre_selection.style.applymap(color_teal_to_lightgreensea).format("{:.2f}"))
                # Afficher les statistiques descriptives pour les sommes journalières
        st.write("Statistiques descriptives des consommations trimestrielles :")
        st.dataframe(somme_trimestre_selection.describe().T)

        # Afficher les données annuelles
        st.write("Consommations annuelles de l'Année en cours :")
        st.dataframe(somme_annee_selection.style.applymap(color_teal_to_lightgreensea).format("{:.2f}"))

# Fonction pour les statistiques de l'année précedente
def stat_annee_precedente():
        # Appel de la fonction pour obtenir toutes les variables
    result = afficher_tableaux_et_graphiques_par_periode()
    
    # Extraire les données nécessaires à partir du dictionnaire 'result'
    somme_jour_prec_selection_affichage = result['somme_jour_prec_selection_affichage' ]
    somme_jour_prec_selection = result['somme_jour_prec_selection_affichage']
    somme_semaine_prec_selection = result['somme_semaine_prec_selection']
    somme_mois_prec_selection = result['somme_mois_prec_selection']
    somme_trimestre_prec_selection = result['somme_trimestre_prec_selection']
    somme_annee_prec_selection = result['somme_annee_prec_selection']
    col2 = result['col2']
    
    with col2:
        st.write("Sommes journalières Année précédente en (kWh)")
        st.dataframe(somme_jour_prec_selection_affichage.style.applymap(color_teal_to_lightgreensea).format("{:.2f}"))
        # Utiliser Plotly pour le graphique en area
        fig_area = px.area(somme_jour_prec_selection, title="Graphique des sommes journalières (Année Précédente) en (kWh)",
            color_discrete_sequence=['DarkCyan', 'LightSeaGreen', 'MediumAquamarine', 'LightGreen']  # Couleurs spécifiées
        )

        # Mise à jour des polices
        fig_area.update_layout(
        title_font=dict(family="Times New Roman", size=20),  # Police et taille du titre
        xaxis_title_font=dict(family="Times New Roman", size=20),  # Police et taille de l'axe X
        yaxis_title_font=dict(family="Times New Roman", size=20),  # Police et taille de l'axe Y
        legend_title_font=dict(family="Times New Roman", size=20),  # Police et taille du titre de la légende
        legend_font=dict(family="Times New Roman", size=20),  # Police et taille de la légende
        font=dict(family="Times New Roman", size=20)  # Police générale
        
    )

        st.plotly_chart(fig_area)
        # Afficher les statistiques descriptives pour les sommes journalières
        st.write("Statistiques descriptives des consommations journalières :")
        st.dataframe(somme_jour_prec_selection_affichage.describe().T)

        st.write("Sommes hebdomadaires Année précédente :")
        st.dataframe(somme_semaine_prec_selection.style.applymap(color_teal_to_lightgreensea).format("{:.2f}"))
        # Afficher les statistiques descriptives pour les sommes hebdomadaire
        st.write("Statistiques descriptives des consommations hebdomadaire :")
        st.dataframe(somme_semaine_prec_selection.describe().T)

        st.write("Sommes mensuelles Année précédente :")
        st.dataframe(somme_mois_prec_selection.style.applymap(color_teal_to_lightgreensea).format("{:.2f}"))
        # Afficher les statistiques descriptives pour les sommes mensuelles
        st.write("Statistiques descriptives des consommations mensuelles :")
        st.dataframe(somme_mois_prec_selection.describe().T)

        st.write("Sommes trimestrielles Année précédente :")
        st.dataframe(somme_trimestre_prec_selection.style.applymap(color_teal_to_lightgreensea).format("{:.2f}"))
        # Afficher les statistiques descriptives pour les sommes trimestrielles
        st.write("Statistiques descriptives des consommations trimestrilles :")
        st.dataframe(somme_trimestre_prec_selection.describe().T)

        st.write("Sommes annuelles Année précédente :")
        st.dataframe(somme_annee_prec_selection.style.applymap(color_teal_to_lightgreensea).format("{:.2f}"))

# Fonction pour récupérer les dates de l'interface
def recuperer_dates():
    global cal_debut, cal_fin
    # Entrée date de comparaison pour le choix de l'utilisateur
    cal_debut = st.sidebar.date_input("Entrez la date début à visualiser :", datetime.now().date())
    cal_fin = st.sidebar.date_input("Entrez la date fin à visualiser :", datetime.now().date())

# Fonction pour charger les données des mesures P10
def dieuli_naat_gui(file_path):
    global df_energie, colonne_p10
    try:
        # Charger la feuille unique
        df_energie = pd.read_excel(file_path)
        col3, col4 = st.columns(2)
        
        # Liste déroulante pour choisir la colonne P10 parmi les colonnes disponibles
        with col3:
            colonne_p10 = st.sidebar.selectbox("Sélectionnez la colonne pour les points de 10 minutes (P10) :", df_energie.columns)
            df_energie['Date'] = pd.to_datetime(df_energie['Date'], errors='coerce')
            df_energie.set_index('Date', inplace=True)
     
    except Exception as e:
        st.error(f"Erreur lors du chargement des données : {e}")

# Fonction pour charger les données de température
def dieuli_naat_tangor_gui(file_path):
    global df_temperature, colonne_temperature
    
    try:
        # Charger le fichier Excel
        df_temperature = pd.read_excel(file_path)
        
        # Liste déroulante pour choisir la colonne de température parmi les colonnes disponibles
        colonne_temperature = st.sidebar.selectbox("Sélectionnez la colonne pour les températures :", df_temperature.columns)
      
        # Convertir la colonne 'Date' en type datetime
        df_temperature['Date'] = pd.to_datetime(df_temperature['Date'], errors='coerce')
        df_temperature.set_index('Date', inplace=True)
        
        # Nettoyer et convertir les valeurs de la colonne de température
        if colonne_temperature in df_temperature.columns:
            # Nettoyer les valeurs en supprimant les espaces, guillemets et en remplaçant les virgules par des points
            df_temperature[colonne_temperature] = (
                df_temperature[colonne_temperature]
                .astype(str)
                .str.replace(",", ".", regex=False)  # Remplacer les virgules pour les décimales
                .str.extract(r"(-?\d+\.?\d*)")[0]  # Extraire les valeurs numériques correctes
            )

            # Convertir les valeurs en float, avec des erreurs ignorées (les valeurs incorrectes deviendront NaN)
            df_temperature[colonne_temperature] = pd.to_numeric(df_temperature[colonne_temperature], errors='coerce')
            
            # Remplacer les valeurs NaN par la médiane de la colonne
            median_temperature = df_temperature[colonne_temperature].median()
            df_temperature[colonne_temperature].fillna(median_temperature, inplace=True)
        else:
            st.warning("La colonne spécifiée pour les températures n'existe pas dans le fichier.")
            return
            
    except Exception as e:
        st.error(f"Erreur lors du chargement des données : {e}")

# Fonction principale pour le calcul de talon
def talon():
    global df_energie
    df_energie['Heure'] = df_energie.index.hour

    Talon_Nocturne = df_energie[(df_energie["Heure"] >= 22) | (df_energie["Heure"] < 5)].copy()
    Talon_mode_reduit = df_energie[(df_energie["Heure"] >= 5) & (df_energie["Heure"] < 8)].copy()
    Talon_diurne = df_energie[(df_energie["Heure"] >= 8) & (df_energie["Heure"] < 22)].copy()

    sommes = [calculer_sommes(talon) for talon in [Talon_Nocturne, Talon_mode_reduit, Talon_diurne]]
    somme_jour = pd.concat([s[0] for s in sommes], axis=1)
    somme_jour.columns = ['Talon Nocturne (22h - 05h)', 'Talon en mode Réduit (05h - 08h)', 'Talon Diurne (08h - 22h)']

    # Concatenation des talons
    les_talons_combined = pd.concat([Talon_Nocturne[colonne_p10], Talon_mode_reduit[colonne_p10], Talon_diurne[colonne_p10]], axis=1)
    
    # Renommer les colonnes pour une meilleure lisibilité
    les_talons_combined.columns = ['Talon Nocturne (22h - 05h)', 'Talon en mode Réduit (05h - 08h)', 'Talon Diurne (08h - 22h)']
    
    # Conserver également la colonne Date dans les_talons_combined
    les_talons_combined['Date'] = les_talons_combined.index.date  # Conserver la date si nécessaire

    return somme_jour, les_talons_combined

# Fonction pour calculer les sommes
def calculer_sommes(talon):
    global colonne_p10
    talon['Date'] = pd.to_datetime(talon.index, errors='coerce')
    talon.dropna(subset=['Date'], inplace=True)
    talon['Semaine'] = talon['Date'].dt.isocalendar().week
    talon['Mois'] = talon['Date'].dt.month
    talon['Annee'] = talon['Date'].dt.year

    somme_jour = talon.groupby(talon['Date'].dt.date)[colonne_p10].sum()
    somme_semaine = talon.groupby(['Annee', 'Semaine'])[colonne_p10].sum()
    somme_mois = talon.groupby(['Annee', 'Mois'])[colonne_p10].sum()
    somme_annee = talon.groupby('Annee')[colonne_p10].sum()

    return somme_jour, somme_semaine, somme_mois, somme_annee

# Fonction pour afficher les graphiques 
def afficher_graphiques():
    # Obtenir les sommes des périodes depuis la fonction talon
    somme_jour, les_talons_combined = talon()

    # Assurez-vous que cal_debut et cal_fin sont valides
    if cal_debut is None or cal_fin is None:
        st.error("Veuillez sélectionner une plage de dates valide.")
        return  # Sortir si les dates ne sont pas valides

    # Convertir cal_debut et cal_fin en datetime pour la comparaison
    cal_debut_dt = pd.to_datetime(cal_debut)  # Conversion de la date en datetime
    cal_fin_dt = pd.to_datetime(cal_fin)  # Conversion de la date en datetime
    
    # Filtrer les données selon les dates dans les_talons_combined
    les_talons_combined_selection = les_talons_combined[
        (les_talons_combined.index >= cal_debut_dt) & (les_talons_combined.index <= cal_fin_dt)
    ]

    if les_talons_combined_selection.empty:
        st.error("Aucune donnée disponible pour la période sélectionnée.")
        return

    # Ajout d'une colonne 'Date' pour le tracé
    les_talons_combined_selection['Date'] = les_talons_combined_selection.index  # Conserver la date
    # Définir les colonnes à tracer
    colonnes_a_tracer = [
        'Talon en mode Réduit (05h - 08h)',
        'Talon Diurne (08h - 22h)',
        'Talon Nocturne (22h - 05h)'
    ]

    # Utilisation de la méthode melt pour préparer les données pour le tracé
    melted_data_talons = les_talons_combined_selection.melt(id_vars=['Date'], value_vars=colonnes_a_tracer, var_name='Période', value_name='Valeur')
    
    # Vérification que chaque période est représentée
    if melted_data_talons.empty:
        st.error("Aucune donnée disponible après réorganisation.")
        return

    # Filtrer les données pour la période sélectionnée
    periode_selection = les_talons_combined_selection[(les_talons_combined_selection.index >= cal_debut_dt) & (les_talons_combined_selection.index <= cal_fin_dt)]

    # Ajouter une colonne 'Date' pour chaque période
    periode_selection['Date'] = periode_selection.index

    # Réorganiser les données pour le tracé avec un DataFrame 'melted'
    les_talons_combined_selection = periode_selection.melt(id_vars=['Date'], value_vars=colonnes_a_tracer, var_name='Période', value_name='Valeur')

    # Convertir 'Valeur' en numérique et gérer les NaN
    les_talons_combined_selection['Valeur'] = pd.to_numeric(les_talons_combined_selection['Valeur'], errors='coerce')
    les_talons_combined_selection = les_talons_combined_selection.dropna(subset=['Valeur'])  # Supprimer les lignes avec NaN

    # Remplir les dates manquantes pour chaque période afin d'assurer une continuité
    # En pivotant puis remplissant les dates, toutes les périodes auront une ligne pour chaque date, même si la valeur est NaN
    les_talons_combined_selection_pivot = melted_data_talons.pivot_table(
        index='Date', 
        columns='Période', 
        values='Valeur'
    ).reset_index()

    # Réarranger le DataFrame pour le format 'long' à nouveau après remplissage des périodes manquantes
    les_talons_combined_selection_filled = les_talons_combined_selection_pivot.melt(
        id_vars=['Date'], 
        var_name='Période', 
        value_name='Valeur'
    )

    # Assurer la suppression des NaN dans la version finale avant le tracé (vous pouvez choisir de les interpoler si vous préférez)
    les_talons_combined_selection_filled_clean = les_talons_combined_selection_filled.fillna(0)  # Remplacer les NaN par 0 pour maintenir la continuité
    
    return les_talons_combined_selection_filled_clean, les_talons_combined_selection, melted_data_talons, colonnes_a_tracer

# Fonction pour afficher les graphiques des sommes journalières en Bar
def graphe_bar():
    global colonne_p10
    cal_debut_dt = pd.to_datetime(cal_debut)  # Conversion de la date en datetime
    cal_fin_dt = pd.to_datetime(cal_fin)  # Conversion de la date en datetime
    result = afficher_tableaux_et_graphiques_par_periode()
    melted_data = result['melted_data']
    
    # Calculer la somme pour chaque période et année
    sums_per_period = (
        melted_data[melted_data['Valeur'] > 0]
        .groupby(['Période', 'Année'])['Valeur']
        .sum()
        .reset_index()
    )
    
    # Tracer le graphique avec Plotly
    fig_bar = px.bar(
        melted_data[melted_data['Valeur'] > 0],  # Exclure les valeurs non positives
        x='Période',  
        y='Valeur',  
        color='Année',  
        barmode='group',  
        title=f'Comparaison des consommations électriques du {cal_debut_dt.date()} au {cal_fin_dt.date()} par la période précédente : {colonne_p10}',
        labels={'Valeur': 'Mesures Electriques en (kWh)', 'Période': 'Consommation triée par période de fonctionnement'},
        color_discrete_sequence=['SeaGreen', 'LightGreen']  # Utilisation des couleurs Teal et LightSeaGreen
    )

    # Associer les couleurs des périodes aux annotations
    colors = {trace['name']: trace['marker']['color'] for trace in fig_bar['data']}
    
    # Ajouter des annotations pour chaque somme avec un offset fixe entre chaque période
    last_period = None
    yshift = 0
    for idx, row in sums_per_period.iterrows():
        # Vérifier si la période est différente de la précédente
        if row['Période'] != last_period:
            yshift = 0  # Réinitialiser le décalage pour une nouvelle période
            last_period = row['Période']
        
        # Trouver la couleur associée à l'année
        color = colors.get(str(row['Année']), 'black')  # Noir par défaut si non trouvé
        
        # Ajouter une annotation pour chaque barre
        fig_bar.add_annotation(
            x=row['Période'],  # Position X : alignement avec la période
            y=row['Valeur'],  # Position Y : somme
            text=f"{row['Valeur']:.2f} kWh",  # Texte : somme en kWh
            showarrow=False,  # Pas de flèche
            font=dict(size=18, color=color),  # Style de texte avec couleur
            align='center',  # Alignement horizontal centré
            yshift= 45 + yshift  # Décalage vertical initial de 10 + 15 par annotation
        )
        
        # Augmenter le décalage pour la prochaine annotation de la même période
        yshift += 15

    # Mise à jour des polices et rendre le fond transparent
    fig_bar.update_layout(
        title_font=dict(family="Times New Roman", size=24),  # Taille et police du titre
        xaxis_title_font=dict(family="Times New Roman", size=24),  # Taille et police du titre de l'axe X
        yaxis_title_font=dict(family="Times New Roman", size=24),  # Taille et police du titre de l'axe Y
        legend_title_font=dict(family="Times New Roman", size=24),  # Taille et police du titre de la légende
        legend_font=dict(family="Times New Roman", size=20),  # Police et taille de la légende
        font=dict(family="Times New Roman", size=24),  # Taille et police générale du texte
        plot_bgcolor='rgba(0,0,0,0)',  # Fond du graphique transparent
        paper_bgcolor='rgba(0,0,0,0)'  # Fond du papier (hors graphique) transparent
    )

    # Afficher le graphique dans Streamlit
    st.plotly_chart(fig_bar)

# Fonction pour afficher les graphiques des sommes journalières en Courbe 
def graphe_courbe():
    global colonne_p10
    all_data = analyse()  # Récupération des données
    consommation = all_data[colonne_p10].sum()
    cal_debut_dt = pd.to_datetime(cal_debut)  # Conversion de la date en datetime
    cal_fin_dt = pd.to_datetime(cal_fin)  # Conversion de la date en datetime

    
    # Tracer les courbes avec Date sur l'axe des X
    fig_line = px.line(
        all_data[all_data[colonne_p10] > 0],  # Exclure les valeurs non positives
        x='Date',  # Utiliser la Date sur l'axe des X
        y=colonne_p10,  # Utiliser la consommation comme axe des Y
        color='Période',  # Différencier les courbes par période
        title=f"Évolution des consommations par période du {cal_debut_dt.date()} au {cal_fin_dt.date()} : {colonne_p10}<br> Energie consommée : {consommation:.2f} kWh",
        labels={colonne_p10: 'Consommation en kWh', 'Date': 'Date'},  # Personnalisation des labels
        color_discrete_sequence=["Red", "Blue", "MediumSeaGreen"]  # Discrétisation des couleurs
    )

    # Mise à jour des polices
    fig_line.update_layout(
        title_font=dict(family="Times New Roman", size=24),  # Police et taille du titre
        xaxis_title_font=dict(family="Times New Roman", size=20),  # Police et taille de l'axe X
        yaxis_title_font=dict(family="Times New Roman", size=20),  # Police et taille de l'axe Y
        legend_title_font=dict(family="Times New Roman", size=20),  # Police et taille du titre de la légende
        legend_font=dict(family="Times New Roman", size=20),  # Police et taille de la légende
        font=dict(family="Times New Roman", size=14)  # Police générale
        
    )

    # Afficher le graphique dans Streamlit
    st.plotly_chart(fig_line)

# Fonction pour dérouler l'évolution du talon élctrique en Replay afin d'identifier les dérives
# Permettant l'utilisateur de définir ces propres seuils pour chaque période du talon électrique 
def graphe_interactif():
    cal_debut_dt = pd.to_datetime(cal_debut)  # Conversion de la date en datetime
    cal_fin_dt = pd.to_datetime(cal_fin)  # Conversion de la date en datetime
    # Simule l'obtention des données avec les colonnes 'Date', 'Valeur', 'Période'
   
    all_data = analyse()  # Récupération des données
    consommation = all_data[colonne_p10].sum()
    # Saisie des seuils pour chaque période
    seuils = {} # dictionnaire des seuils
    periodes = all_data['Période'].unique()
    
    st.sidebar.write("Définissez les seuils pour chaque période:")
    for periode in periodes: # boucle parcourant les périodes pour créer les entrées des seuils
        seuils[periode] = float(st.sidebar.text_input(f"Seuil pour la période {periode} :", "10"))

    # Ajouter une colonne "Couleur" pour respecter les couleurs des périodes dans la légende
    all_data['Couleur'] = all_data['Période']

    # Création du graphique avec les couleurs correspondant aux périodes
    fig_interactif = px.scatter(
        all_data, 
        x="Date",  # Axe X pour illustrer l'évolution temporelle
        y=colonne_p10,  # Axe Y pour les valeurs de consommation
        color="Période",  # Couleur basée sur les périodes pour la légende
        hover_name="Période",  # Nom de la période au survol
        animation_frame="Date",  # Animation basée sur la date
        animation_group="Période",  # Groupe d'animation par période
        size=colonne_p10,  # Taille des points proportionnelle à la valeur
        range_y=[all_data[colonne_p10].min() * 0.9, 
                 all_data[colonne_p10].max() * 1.1],  # Plage Y
        range_x=[all_data['Date'].min(), 
                 all_data['Date'].max()],  # Plage X
        title=f'Évolution animée des consommations par période du {cal_debut_dt.date()} au {cal_fin_dt.date()} <br> Energie consommée : {consommation:.2f} kWh',
        color_discrete_sequence=["Blue", "MediumSeaGreen", "Red"]  # Couleurs pour les périodes
    )

    # Ajout de lignes entre les points
    fig_interactif.update_traces(mode='lines+markers')

    # Mise à jour des axes et des polices
    fig_interactif.update_layout(
        title_font=dict(family="Times New Roman", size=20),
        xaxis_title_font=dict(family="Times New Roman", size=18),
        yaxis_title_font=dict(family="Times New Roman", size=18),
        legend_title_font=dict(family="Times New Roman", size=18),
        legend_font=dict(family="Times New Roman", size=18),  # Police et taille de la légende
        font=dict(family="Times New Roman", size=16)
    )

    # Ajouter une trace pour les points qui dépassent le seuil et les faire clignoter en rouge
    for i, row in all_data.iterrows():
        if row[colonne_p10] >= seuils[row['Période']]:
            # Ajout de points supplémentaires en rouge sans affecter la légende des périodes
            fig_interactif.add_trace(go.Scatter(
                x=[row['Date']], 
                y=[row[colonne_p10]],
                mode='markers',
                marker=dict(color='Magenta', size=15, symbol='circle', opacity=0.3),
                name=f"Dérive: {row['Période']} (>{seuils[row['Période']]} kWh {row['Date']})",
                showlegend=True  # afficher cette trace dans la légende
            ))

    # Afficher le graphique interactif dans Streamlit
    st.plotly_chart(fig_interactif)

def graphe_tunnel():
    all_data = analyse()  # Récupération des données
    consommation = all_data[colonne_p10].sum()  # Somme de la consommation totale
    cal_debut_dt = pd.to_datetime(cal_debut)  # Conversion de la date de début
    cal_fin_dt = pd.to_datetime(cal_fin)  # Conversion de la date de fin

    if all_data is not None and not all_data.empty:
        # Sélection des colonnes existantes
        colonnes_existantes = list(all_data.columns)
        colonnes_utiles = ["Date", colonne_p10, "Période", "Différence des P10"]
        colonnes_finales = [col for col in colonnes_utiles if col in colonnes_existantes]

        # Création du graphique en tunnel
        fig_tunnel = px.funnel(
            all_data, 
            x=colonne_p10, 
            y="Période", 
            color="Période",
            color_discrete_sequence=["Blue", "MediumSeaGreen", "Red"],  # Palette de couleurs
            hover_data=colonnes_finales  # Colonnes disponibles pour le survol
        )

        # Mise en page et formatage
        fig_tunnel.update_layout(
            title=f"PAS D'ENERGIES DES MESURES : du {cal_debut_dt.date()} au {cal_fin_dt.date()}<br> Energie consommée : {consommation:.2f} kWh",
            xaxis_title="Consommation d'énergie (kWh)",
            yaxis_title="Période",
            title_font=dict(family="Times New Roman", size=20),
            xaxis_title_font=dict(family="Times New Roman", size=20),
            yaxis_title_font=dict(family="Times New Roman", size=20),
            legend_title_font=dict(family="Times New Roman", size=20),
            legend_font=dict(family="Times New Roman", size=20),
            font=dict(family="Times New Roman", size=20),
            funnelmode="stack"  # Mode empilé pour le tunnel
        )

        # Mise à jour des axes pour ajuster les tailles des ticks et labels
        fig_tunnel.update_xaxes(tickfont=dict(family="Times New Roman", size=20, color="LightSeaGreen"))
        fig_tunnel.update_yaxes(tickfont=dict(family="Times New Roman", size=20))

        # Affichage du graphique dans Streamlit
        st.plotly_chart(fig_tunnel)
    
    else:
        st.error("Aucune donnée à afficher.")

# Fonction pour afficher les graphiques des consommations en violon avec les périodes identifiées 
def graphe_violon():
    all_data = analyse()  # Chargement des données
    consommation = all_data[colonne_p10].sum()
    cal_debut_dt = pd.to_datetime(cal_debut)  # Conversion des dates
    cal_fin_dt = pd.to_datetime(cal_fin)

    if all_data is not None and not all_data.empty:
        # Vérifier si les colonnes existent dans all_data
        colonnes_requises = {"Période", colonne_p10}
        colonnes_existantes = set(all_data.columns)

        if colonnes_requises.issubset(colonnes_existantes):
            # Tracer le graphique en violon avec la colonne "Différence des P10"
            fig_violon = px.violin(
                all_data[all_data[colonne_p10] > 0],  # Exclure les valeurs ≤ 0
                y=colonne_p10, 
                x="Période", 
                color="Période", 
                box=True,
                points="all",  # Afficher tous les points
                title=f"Distribution de la consommation énergétique (kWh) entre {cal_debut_dt.date()} et {cal_fin_dt.date()}<br> Energie consommée : {consommation:.2f} kWh",
                color_discrete_sequence=["Blue", "MediumSeaGreen", "Red"]  # Palette optimisée
            )
            fig_violon.update_yaxes(
                title_text=f"{colonne_p10} (kWh)",
                tickfont=dict(family="Times New Roman", size=18),
                title_font=dict(family="Times New Roman", size=18)
            )

            # Mise en page et polices
            fig_violon.update_layout(
                title_font=dict(family="Times New Roman", size=22),
                xaxis_title_font=dict(family="Times New Roman", size=20),
                yaxis_title_font=dict(family="Times New Roman", size=16),
                legend_title_font=dict(family="Times New Roman", size=18),
                legend_font=dict(family="Times New Roman", size=18),
                font=dict(family="Times New Roman", size=18)
            )
            # Ajustement des axes
            fig_violon.update_xaxes(
                tickfont=dict(family="Times New Roman", size=18)
            )

            fig_violon.update_yaxes(
                title_text=f"{colonne_p10} (kWh)",
                tickfont=dict(family="Times New Roman", size=18),
                title_font=dict(family="Times New Roman", size=18)
            )

            # Affichage dans Streamlit
            st.plotly_chart(fig_violon)
        
        else:
            st.error(f"Les colonnes requises {colonnes_requises} sont absentes dans all_data.")

    else:
        st.error("Aucune donnée disponible pour générer le graphique.")

# Fonction pour afficher les graphiques des consommations en circulaire avec les périodes identifiées  
def graphe_pie():
    all_data = analyse()  # Chargement des données
    cal_debut_dt = pd.to_datetime(cal_debut)  # Conversion des dates
    cal_fin_dt = pd.to_datetime(cal_fin)
    consommation = all_data[colonne_p10].sum()
    if all_data is not None and not all_data.empty:
        # Vérifier si les colonnes existent dans all_data
        colonnes_requises = {"Période", colonne_p10}
        colonnes_existantes = set(all_data.columns)

        if colonnes_requises.issubset(colonnes_existantes):
            # Création du graphique en camembert avec "Différence des P10"
            fig_pie = px.pie(
                all_data, 
                values=colonne_p10, 
                names="Période", 
                title=f"Répartition des mesures du {cal_debut_dt.date()} et {cal_fin_dt.date()} <br> Energie consommée : {consommation:.2f} kWh",
                color="Période",  # Couleurs différenciées par période
                color_discrete_sequence=["Blue", "MediumSeaGreen","Red"]
            )

            # Mise en page et styles
            fig_pie.update_layout(
                title_font=dict(family="Times New Roman", size=22),
                legend_title_font=dict(family="Times New Roman", size=18),
                font=dict(family="Times New Roman", size=14),
                legend=dict(
                    font=dict(size=16),
                    orientation="h",
                    yanchor="bottom",
                    y=-0.3,
                    xanchor="center",
                    x=0.5
                )
            )

            # Affichage dans Streamlit
            st.plotly_chart(fig_pie)
        
        else:
            st.error(f"Les colonnes requises {colonnes_requises} sont absentes dans all_data.")

    else:
        st.error("Aucune donnée disponible pour générer le graphique.")


def predilection():
    global df_energie, colonne_p10

    if df_energie is None or colonne_p10 not in df_energie.columns:
        st.error("Les données énergétiques ou la colonne de consommation ne sont pas disponibles.")
        return

    # S'assurer que la colonne 'Date' existe
    if 'Date' not in df_energie.columns:
        df_energie['Date'] = df_energie.index

    # Convertir en datetime
    df_energie["Date"] = pd.to_datetime(df_energie["Date"], errors='coerce')
    df_energie['Heure'] = df_energie["Date"].dt.hour

    # Créer la plage horaire complète
    full_range = pd.date_range(start=df_energie["Date"].min(), end=df_energie["Date"].max(), freq='h')

    # Initialiser les DataFrames par période
    Natoukay_Goudigui = pd.DataFrame(index=full_range, columns=[colonne_p10]).fillna(0).infer_objects()
    Natoukay_Fadiargui = pd.DataFrame(index=full_range, columns=[colonne_p10]).fillna(0).infer_objects()
    Natoukay_Bathieuggui = pd.DataFrame(index=full_range, columns=[colonne_p10]).fillna(0).infer_objects()

    df_energie_indexed = df_energie.set_index('Date').reindex(full_range)

    # Créer les masques
    mask_goudigui = (df_energie_indexed['Heure'] >= 22) | (df_energie_indexed['Heure'] < 5)
    mask_fadiargui = (df_energie_indexed['Heure'] >= 5) & (df_energie_indexed['Heure'] < 8)
    mask_bathieuggui = (df_energie_indexed['Heure'] >= 8) & (df_energie_indexed['Heure'] < 22)

    # Mise à jour
    Natoukay_Goudigui.update(df_energie_indexed[mask_goudigui])
    Natoukay_Fadiargui.update(df_energie_indexed[mask_fadiargui])
    Natoukay_Bathieuggui.update(df_energie_indexed[mask_bathieuggui])

    # Reset index
    Natoukay_Goudigui.reset_index(inplace=True)
    Natoukay_Fadiargui.reset_index(inplace=True)
    Natoukay_Bathieuggui.reset_index(inplace=True)

    # Renommer les colonnes
    Natoukay_Goudigui.columns = ['Date & Heure', 'Mode Inoccupation (kwh)']
    Natoukay_Fadiargui.columns = ['Date & Heure', 'Mode Réduit (kwh)']
    Natoukay_Bathieuggui.columns = ['Date & Heure', 'Mode Confort (kwh)']

    # Fusion des DataFrames
    Tableau_de_donnees_des_talons = pd.merge(Natoukay_Goudigui, Natoukay_Fadiargui, on='Date & Heure', how='outer')
    Tableau_de_donnees_des_talons = pd.merge(Tableau_de_donnees_des_talons, Natoukay_Bathieuggui, on='Date & Heure', how='outer')

    st.write("### Tableau des talons d'énergie", Tableau_de_donnees_des_talons)

    # Fonction de stats
    def calculs_statistiques(df, colonne):
        return {
            'mean': df[colonne].mean(),
            'std': df[colonne].std(),
            'min': df[colonne].min(),
            '25%': df[colonne].quantile(0.25),
            '50%': df[colonne].median(),
            '75%': df[colonne].quantile(0.75),
            'max': df[colonne].max(),
            'unique': df[colonne].unique(),
            'missing': df[colonne].isnull().sum()
        }

    # Calcul des statistiques
    stats_goudigui = calculs_statistiques(Natoukay_Goudigui, 'Mode Inoccupation (kwh)')
    stats_fadiargui = calculs_statistiques(Natoukay_Fadiargui, 'Mode Réduit (kwh)')
    stats_bathieuggui = calculs_statistiques(Natoukay_Bathieuggui, 'Mode Confort (kwh)')

    st.write("### Statistiques Mode Inoccupation (kwh)", stats_goudigui)
    st.write("### Statistiques Mode Réduit (kwh)", stats_fadiargui)
    st.write("### Statistiques Mode Confort (kwh)", stats_bathieuggui)

    # Machine Learning
    X = Tableau_de_donnees_des_talons[['Date & Heure', 'Mode Réduit (kwh)', 'Mode Confort (kwh)', 'Mode Inoccupation (kwh)']]
    y = df_energie.set_index('Date').reindex(full_range)[colonne_p10].fillna(0).values

    X['Heure'] = pd.to_datetime(X['Date & Heure']).dt.hour
    X['Jour'] = pd.to_datetime(X['Date & Heure']).dt.day
    X['Mois'] = pd.to_datetime(X['Date & Heure']).dt.month
    X['Année'] = pd.to_datetime(X['Date & Heure']).dt.year

    X_dates = X['Date & Heure']
    X.drop(columns=['Date & Heure'], inplace=True)
    X.fillna(X.mean(), inplace=True)

    X_train, X_test, y_train, y_test, dates_train, dates_test = train_test_split(X, y, X_dates, test_size=0.2, random_state=42)

    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    df_energie_results = pd.DataFrame({'Date & Heure': dates_test, 'Actual': y_test, 'Predicted': y_pred})
    df_energie_results['Derive'] = np.abs(df_energie_results['Actual'] - df_energie_results['Predicted']) > 1.0

    st.write("### Résultats avec Dérives", df_energie_results[df_energie_results['Derive']])
    
    df_energie_results.to_excel('resultats_predictions.xlsx', sheet_name='Prédictions et Dérives', index=False)
    st.success("Les résultats ont été exportés dans 'resultats_predictions.xlsx'.")

# Condition des évènements
if mode == "Comparaison par période":
    
    if uploaded_file:
        dieuli_naat_gui(uploaded_file)
        recuperer_dates()
        
        
        # Créer deux colonnes pour les afficher côte à côte
        col1, col2 = st.columns(2)

        with col1:
            st.header("Statistiques de l'année en cours")
            stat_annee_en_cours()
            graphe_bar()


        with col2:
            st.header("Statistiques de l'année précédente")
            stat_annee_precedente()
            graphe_courbe()
            
        # Afficher les tableaux et graphiques communs en dessous
        afficher_tableaux_et_graphiques_par_periode()
        thiambar()
        graphe_courbe_all()
elif mode == "Analyse et rapport":
     
    if uploaded_file or uploaded_file_temperature:
        dieuli_naat_tangor_gui(uploaded_file_temperature)
        dieuli_naat_gui(uploaded_file)
        recuperer_dates()
        
        # Exécution de la fonction pour test
        
        afficher_lien_gtb()
        graphe_analyse_plage_fonctionnement()
        by_analyse()
        infos = recuperer_infos_point_mesure()

        # Affichage des informations récupérées
        st.subheader("📋 Informations liées au compteur ou sous-compteur")

        # CSS pour personnaliser le cadre, la police et la couleur du texte
        st.markdown("""
            <style>
            .custom-box {
                border: 2px solid LightSeaGreen;
                border-radius: 8px;
                padding: 10px;
                text-align: center;
                font-family: 'Times New Roman', serif;
                font-size: 18px;
                color: MediumSeaGreen;
                background-color: #F0F8FF; /* Couleur douce pour le fond */
            }
            </style>
            """, unsafe_allow_html=True)

        if isinstance(infos, list):  # Cas de chargement de fichier
            if infos:
                st.table(pd.DataFrame(infos))  # Afficher sous forme de tableau
        else:  # Cas de saisie manuelle
            if all(infos.values()):  # Vérifier que toutes les valeurs sont remplies
                labels = {
                    "Point de Mesure": "🔢 Point de Mesure",
                    "TD Lié": "🔗 TD Lié",
                    "Emplacement": "📍 Emplacement",
                    "Usage": "⚡ Usage"
                }
                
                # Création des 4 colonnes
                cols = st.columns(4)

                # Affichage des infos dans les colonnes avec une boucle
                for col, (key, label) in zip(cols, labels.items()):
                    with col:
                        st.markdown(f'<div class="custom-box"><strong>{label} :</strong><br>{infos[key]}</div>', 
                                    unsafe_allow_html=True)
            else:
                st.warning("Veuillez remplir toutes les informations.")



        col1, col2 = st.columns(2)
        with col2:
            
            # Utilisation de selectbox au lieu de radio
            choix_graphe = st.selectbox(
                "📊 Sélectionnez un type d'analyse :", 
                [
                    "Part de chaque Période sur la consommation énergétique",
                    "Camembert",
                    "Histogramme",
                    "Violons",
                    "Point Temporel",
                    "Régression Temporelle",
                    "Régression Linéaire",
                    "Tunnel",
                    "Courbe",
                    "Replay de l'évolution",
                    "Ecart des Pas"
                ]
            )

            # Affichage du graphique correspondant au choix
            if choix_graphe == "Part de chaque Période sur la consommation énergétique":
                graphe_bar_by_analyse()
            elif choix_graphe == "Camembert":
                graphe_pie()
            elif choix_graphe == "Histogramme":
                graphe_by_analyse()
            elif choix_graphe == "Violons":
                graphe_violon()
            elif choix_graphe == "Point Temporel":
                graphe_point_temps()
            elif choix_graphe == "Régression Temporelle":
                graphe_regression_tempo()
            elif choix_graphe == "Régression Linéaire":
                graphe_regression_lineaire()
            elif choix_graphe == "Tunnel":
                graphe_tunnel()
            elif choix_graphe == "Courbe":
                graphe_courbe_all()
            elif choix_graphe == "Replay de l'évolution":
                graphe_interactif()
            elif choix_graphe == "Ecart des Pas":
                graphe_ecart_des_mesures()
            else:
                st.error("Veuillez charger un fichier Excel.")
        with col1:
        
            # Utilisation de selectbox au lieu de radio
            choix_graphe = st.selectbox(
                "📊 Sélectionnez un type d'analyse :", 
                [
                    "Camembert",
                    "Histogramme",
                    "Violons",
                    "Point Temporel",
                    "Régression Temporelle",
                    "Régression Linéaire",
                    "Tunnel",
                    "Courbe",
                    "Replay de l'évolution",
                    "Ecart des Pas"
                ]
            )

            # Affichage du graphique correspondant au choix
            if choix_graphe == "Camembert":
                graphe_pie()
            elif choix_graphe == "Histogramme":
                graphe_by_analyse()
            elif choix_graphe == "Violons":
                graphe_violon()
            elif choix_graphe == "Point Temporel":
                graphe_point_temps()
            elif choix_graphe == "Régression Temporelle":
                graphe_regression_tempo()
            elif choix_graphe == "Régression Linéaire":
                graphe_regression_lineaire()
            elif choix_graphe == "Tunnel":
                graphe_tunnel()
            elif choix_graphe == "Courbe":
                graphe_courbe_all()
            elif choix_graphe == "Replay de l'évolution":
                graphe_interactif()
            elif choix_graphe == "Ecart des Pas":
                graphe_ecart_des_mesures()
            else:
                st.error("Veuillez charger un fichier Excel.")
        
        choix_graphe = st.radio(
            "📊 Types d'analyses:", 
            [
                "Camembert",
                "Histogramme",
                "Violons",
                "Point Temporel",
                "Régression Temporelle",
                "Régression Linéaire",
                "Tunnel",
                "Courbe",
                "Replay de l'évolution",
                "Ecart des Pas"

            ],
            horizontal=True  # Permet d'afficher les options sur une ligne
        )

        if choix_graphe == "Camembert":
            graphe_pie()
        elif choix_graphe == "Histogramme":
            graphe_by_analyse()
        elif choix_graphe == "Violons":
            graphe_violon()
        elif choix_graphe == "Point Temporel":
            graphe_point_temps()
        elif choix_graphe == "Régression Temporelle":
            graphe_regression_tempo()
        elif choix_graphe == "Régression Linéaire":
            graphe_regression_lineaire()
        elif choix_graphe == "Tunnel":
            graphe_tunnel()
        elif choix_graphe == "Courbe":
            graphe_courbe_all()
        elif choix_graphe == "Replay de l'évolution":
            graphe_interactif()
        elif choix_graphe == "Ecart des Pas":
            graphe_ecart_des_mesures()
    

    else:
        st.error("Veuillez charger un fichier Excel.")
    predilection() 