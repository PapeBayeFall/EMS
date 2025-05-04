import streamlit as st
import numpy as np
import plotly.graph_objects as go
import requests
import pandas as pd
from datetime import datetime, timedelta

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

# --- MÉTÉO REELLE VIA API ---
def get_real_weather_from_api():
    try:
        url = "https://public-api.meteofrance.fr/public/DPClim/v1/temperature/horaire?id-station=07240&date-debut=2024-01-01&date-fin=2024-12-31"
        headers = {"accept": "application/json"}
        response = requests.get(url, headers=headers)
        data = response.json()
        records = data.get("records", [])
        df = pd.DataFrame.from_records(records)

        if 'value' not in df.columns:
            raise ValueError("La colonne 'value' n'existe pas dans les données retournées.")

        if 'date' in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        elif 'datetime' in df.columns:
            df["date"] = pd.to_datetime(df["datetime"])
        else:
            raise ValueError("Aucune colonne de date trouvée dans les données météo.")

        df = df.set_index("date").resample(f"{dt_hrs}H").mean().interpolate()
        df = df.loc[df.index[:Nt]]
        T_ext_real = df["value"].values

        RH = np.full_like(T_ext_real, 60.0)  # placeholder
        A, B = 17.27, 237.7
        alpha = (A * T_ext_real) / (B + T_ext_real) + np.log(RH / 100)
        Td = (B * alpha) / (A - alpha)
        return T_ext_real, RH, Td
    except Exception as e:
        st.error(f"Erreur lors de la récupération des données météo : {e}")
        return generate_realistic_weather()

# --- MÉTÉO DYNAMIQUE SIMULÉE ---
def generate_realistic_weather():
    np.random.seed(42)
    hours = int(365 * 24)
    t = np.arange(hours)
    base_temp = 12 + 8 * np.sin(2 * np.pi * t / (24 * 365)) + 4 * np.sin(2 * np.pi * t / 24)
    noise = np.random.normal(0, 1, size=hours)
    T_real = base_temp + noise
    RH = 50 + 20 * np.sin(2 * np.pi * t / 24 + np.pi / 4)
    RH = np.clip(RH + np.random.normal(0, 5, size=hours), 30, 100)
    A = 17.27
    B = 237.7
    alpha = (A * T_real) / (B + T_real) + np.log(RH / 100)
    Td = (B * alpha) / (A - alpha)
    return T_real[:Nt], RH[:Nt], Td[:Nt]

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
    mcp_state = []  # suivi de l'état liquide/solide

    for n in range(Nt):
        T_ext = T_ext_array[n]
        c_eff, phase_change = heat_capacity(T, delta_T, mcp_ratio)
        for i in range(1, Nx - 1):
            T_new[i] = T[i] + alpha * dt / dx**2 * (T[i+1] - 2*T[i] + T[i-1])
        T_new[0] = T_ext  # Ext
        T_new[-1] = T[-1]  # Int: mur adiabatique
        T = T_new.copy()
        T_record.append(T[-1])  # Température intérieure
        mcp_state.append(phase_change[-1])

    return T_record, mcp_state

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

use_real_weather = st.checkbox("Utiliser les données météo réelles (Météo France)")
delta_T = st.slider("Intervalle de transition de phase (°C)", 0.5, 5.0, delta_T_default, 0.1)
mcp_ratio = st.slider("Pourcentage massique de MCP", 0.0, 0.5, mcp_ratio_default, 0.01)

if st.button("Lancer la simulation"):
    if use_real_weather:
        T_ext_real, RH, Td = get_real_weather_from_api()
    else:
        T_ext_real, RH, Td = generate_realistic_weather()

    T_record, mcp_state = simulate_with_real_temp(T_ext_real, delta_T, mcp_ratio)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=temps, y=T_record, mode='lines', name='Température intérieure'))
    fig.add_trace(go.Scatter(x=temps, y=T_ext_real, mode='lines', name='Température extérieure'))
    fig.add_trace(go.Scatter(x=temps, y=Td, mode='lines', name='Point de rosée', line=dict(dash='dot')))
    fig.add_trace(go.Scatter(x=temps, y=[T_mcp if state else None for state in mcp_state],
                             mode='markers', name='Changement de phase MCP',
                             marker=dict(size=3, color='red'),
                             showlegend=True))
    fig.update_layout(title="Températures simulées et comportement MCP",
                      xaxis_title="Temps (date)", yaxis_title="Température (°C)")
    st.plotly_chart(fig, use_container_width=True)

st.markdown("""
---
**Modèle simplifié** pour prototype et démonstration. À complexifier pour prise en compte de l’humidité, de la convection, ou de la géométrie 2D/3D.
""")
