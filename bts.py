# mcp_brique_simulation/main.py

import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

# --- PARAMETRES PHYSIQUES ---
L = 0.2  # Epaisseur du mur (m)
Nx = 50  # Nombre de points dans l'espace
dx = L / (Nx - 1)

T_init = 20.0  # Temp initiale dans le mur (Celsius)
T_moy = 15.0   # Moyenne annuelle de la temp ext (Celsius)
T_amp = 10.0   # Amplitude annuelle (Celsius)

jours = 365  # durée de simulation (jours)
dt = 3600     # pas de temps (1h)
Nt = int(jours * 86400 / dt)

temps = np.linspace(0, jours, Nt)

# Parametres thermiques
k = 0.6     # conductivite thermique (W/m.K)
rho = 1800  # masse volumique (kg/m3)
c = 1000    # capacite thermique (J/kg.K)
alpha = k / (rho * c)  # diffusivite

# MCP
L_f = 180000  # chaleur latente (J/kg)
T_mcp = 24.0  # temperature de changement de phase (C)
delta_T = 2.0  # intervalle autour du T_mcp
mcp_ratio = 0.1  # ratio massique MCP

# Capacite thermique effective

def heat_capacity(T):
    c_eff = np.ones_like(T) * c
    phase_change = (T > (T_mcp - delta_T)) & (T < (T_mcp + delta_T))
    c_eff[phase_change] += L_f / (2 * delta_T) * mcp_ratio
    return c_eff

# Temperature exterieure

def temperature_ext(t_jour):
    return T_moy + T_amp * np.sin(2 * np.pi * t_jour / 365)

# Schema explicite

def simulate():
    T = np.ones(Nx) * T_init
    T_new = T.copy()
    T_record = []
    
    for n in range(Nt):
        T_ext = temperature_ext(n * dt / 86400)
        c_eff = heat_capacity(T)
        for i in range(1, Nx - 1):
            T_new[i] = T[i] + alpha * dt / dx**2 * (T[i+1] - 2*T[i] + T[i-1])
        
        # Conditions aux limites
        T_new[0] = T_ext  # Ext
        T_new[-1] = T[-1]  # Int: mur adiabatique
        T = T_new.copy()
        T_record.append(T[-1])  # Temperature cote interieur
    return T_record

# --- INTERFACE STREAMLIT ---
st.set_page_config(layout="wide")
st.title("Simulation thermique d'une brique avec microcapsules de paraffine (MCP)")

st.markdown("""
Ce projet simule la **régulation thermique** d'une brique en terre stabilisée intégrant des **microcapsules de paraffine (MCP)**.
Les MCP permettent d'amortir les variations de température grâce à leur **chaleur latente de fusion**.

Le modèle utilise :
- Une équation de chaleur 1D discrétisée (schéma explicite)
- Une température extérieure variant sur un an (fonction sinusoïdale)
- Un modèle de chaleur latente via une capacité thermique effective

---
""")

# Paramètres utilisateur
mcp_ratio = st.slider("Pourcentage massique de MCP", 0.0, 0.5, 0.1, 0.01)
delta_T = st.slider("Intervalle de transition de phase (°C)", 0.5, 5.0, 2.0, 0.1)
T_amp = st.slider("Amplitude annuelle température extérieure (°C)", 5.0, 20.0, 10.0, 0.5)
T_moy = st.slider("Température moyenne extérieure (°C)", 0.0, 30.0, 15.0, 0.5)

# Relancer la simulation
if st.button("Lancer la simulation"):
    T_record = simulate()
    
    # Affichage
    fig, ax = plt.subplots()
    ax.plot(temps, T_record, label="Température intérieure")
    ax.plot(temps, temperature_ext(temps), label="Température extérieure", linestyle='--')
    ax.set_xlabel("Temps (jours)")
    ax.set_ylabel("Température (°C)")
    ax.legend()
    ax.grid(True)
    st.pyplot(fig)

st.markdown("""
---
**Modèle simplifié** pour prototype et démonstration. À complexifier pour prise en compte de l’humidité, de la convection, ou de la géométrie 2D/3D.
""")
