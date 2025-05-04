import streamlit as st
import numpy as np
import plotly.graph_objects as go
import requests
import pandas as pd
from datetime import datetime, timedelta
from io import StringIO

# --- CONFIGURATION PAGE ---
st.set_page_config(layout="wide")

# --- PARAMETRES PHYSIQUES ---
L = 0.2  # Epaisseur du mur (m)
Nx = 50  # Nombre de points dans l'espace
dx = L / (Nx - 1)

T_init = 20.0  # Temp initiale dans le mur (Celsius)
T_moy_default = 15.0   # Moyenne annuelle de la temp ext (Celsius)
T_amp_default = 10.0   # Amplitude annuelle (Celsius)

# --- TITRE ---
st.title("Simulation thermique d'une brique avec microcapsules de paraffine (MCP)")

# --- CONTROLES UTILISATEUR ---
jours = st.slider("Durée de simulation (jours)", 1, 365, 30, step=1)
dt_hrs = st.slider("Pas de temps (heures)", 1, 24, 1, step=1)
dt = dt_hrs * 3600  # conversion en secondes
Nt = int(jours * 86400 / dt)
temps = np.array([datetime(2024, 1, 1) + timedelta(seconds=i * dt) for i in range(Nt)])

# Parametres thermiques
k = 0.6     # conductivite thermique (W/m.K)
rho = 1800  # masse volumique (kg/m3)
c = 1000    # capacite thermique (J/kg.K)
alpha = k / (rho * c)  # diffusivite

# MCP
L_f = 180000  # chaleur latente (J/kg)
T_mcp = 24.0  # temperature de changement de phase (C)
delta_T_default = 2.0  # intervalle autour du T_mcp
mcp_ratio_default = 0.1  # ratio massique MCP

# Capacite thermique effective et suivi phase
def heat_capacity(T, delta_T, mcp_ratio):
    c_eff = np.ones_like(T) * c
    phase_change = (T > (T_mcp - delta_T)) & (T < (T_mcp + delta_T))
    c_eff[phase_change] += L_f / (2 * delta_T) * mcp_ratio
    return c_eff, phase_change

# Simulation thermique avec suivi du MCP
def simulate_with_real_temp(T_ext_array, delta_T, mcp_ratio):
    T = np.ones(Nx) * T_init
    T_new = T.copy()
    T_record = []
    mcp_state = []
    phase_log = []

    for n in range(Nt):
        T_ext = T_ext_array[n] if n < len(T_ext_array) else T_ext_array[-1]
        c_eff, phase_change = heat_capacity(T, delta_T, mcp_ratio)
        for i in range(1, Nx - 1):
            T_new[i] = T[i] + alpha * dt / dx**2 * (T[i+1] - 2*T[i] + T[i-1])
        T_new[0] = T_ext
        T_new[-1] = T[-1]
        T = T_new.copy()
        T_record.append(T[-1])
        mcp_state.append(phase_change[-1])
        if phase_change[-1]:
            phase_log.append((temps[n], T[-1]))

    return T_record, mcp_state, phase_log

# --- INTERFACE STREAMLIT ---

st.markdown("""
Ce projet simule la **régulation thermique** d'une brique en terre stabilisée intégrant des **microcapsules de paraffine (MCP)**.
Les MCP permettent d'amortir les variations de température grâce à leur **chaleur latente de fusion**.

Le modèle utilise :
- Une équation de chaleur 1D discrétisée (schéma explicite)
- Une température extérieure horaire issue de données météo réelles ou simulées
- Un modèle de chaleur latente via une capacité thermique effective

---
""")

st.subheader("Option de données météo")
source = st.radio("Source des températures extérieures", ["Fichier utilisateur", "API InfoClimat", "Météo simulée"])

uploaded_file = None
df = None
if source == "Fichier utilisateur":
    uploaded_file = st.file_uploader("Importer un fichier CSV ou Excel contenant des températures horaires", type=["csv", "xlsx"])

elif source == "API InfoClimat":
    url = "https://www.infoclimat.fr/opendata/?version=2&method=get&format=csv&stations[]=07510&start=2025-01-01&end=2025-05-04&token=null"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            df = pd.read_csv(StringIO(response.text), sep=';', engine='python')
            st.success("Données météo téléchargées depuis InfoClimat")
        else:
            st.error(f"Erreur API InfoClimat : {response.status_code}")
    except Exception as e:
        st.error(f"Erreur lors de la récupération des données météo : {e}")

# Sélection manuelle des colonnes
T_ext_real = None
if uploaded_file is not None or df is not None:
    try:
        if uploaded_file is not None:
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)

        st.write("Aperçu des données importées :", df.head())
        date_col = st.selectbox("Sélectionnez la colonne de date/temps", df.columns)
        temp_col = st.selectbox("Sélectionnez la colonne de température", df.columns)

        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=[date_col])
        df = df.set_index(date_col).sort_index()
        df = df.resample(f"{dt_hrs}H").mean().interpolate()
        df = df.loc[df.index[:Nt]]
        T_ext_real = df[temp_col].values
    except Exception as e:
        st.error(f"Erreur de chargement des données météo : {e}")

# Paramètres MCP
st.subheader("Paramètres du matériau et du MCP")
delta_T = st.slider("Intervalle de transition de phase (°C)", 0.5, 5.0, delta_T_default, 0.1)
mcp_ratio = st.slider("Pourcentage massique de MCP", 0.0, 0.5, mcp_ratio_default, 0.01)

if st.button("Lancer la simulation"):
    if T_ext_real is None:
        # fallback météo simulée
        np.random.seed(42)
        hours = int(365 * 24)
        t = np.arange(hours)
        base_temp = 12 + 8 * np.sin(2 * np.pi * t / (24 * 365)) + 4 * np.sin(2 * np.pi * t / 24)
        noise = np.random.normal(0, 1, size=hours)
        T_ext_real = (base_temp + noise)[:Nt]

    T_record, mcp_state, phase_log = simulate_with_real_temp(T_ext_real, delta_T, mcp_ratio)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=temps, y=T_record, mode='lines', name='Température intérieure'))
    fig.add_trace(go.Scatter(x=temps, y=T_ext_real, mode='lines', name='Température extérieure'))
    fig.add_trace(go.Scatter(x=temps, y=[T_mcp if state else None for state in mcp_state],
                             mode='markers', name='Changement de phase MCP',
                             marker=dict(size=3, color='red'),
                             showlegend=True))
    fig.update_layout(title="Températures simulées et comportement MCP",
                      xaxis_title="Temps (date)", yaxis_title="Température (°C)")
    st.plotly_chart(fig, use_container_width=True)

    if phase_log:
        st.subheader("Moments du changement de phase détectés")
        phase_df = pd.DataFrame(phase_log, columns=["Temps", "Température intérieure"])
        st.dataframe(phase_df)
    else:
        st.info("Aucun changement de phase détecté pendant la simulation.")

st.markdown("""
---
**Modèle simplifié** pour prototype et démonstration. À complexifier pour prise en compte de l’humidité, de la convection, ou de la géométrie 2D/3D.
""")
