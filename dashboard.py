import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import time

# -------------------- CONFIGURATION --------------------
st.set_page_config(page_title="KPI Projet", layout="wide")

# URL publique de ta Google Sheet
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQKgao_dLrrNJV1qPYv0nW7UTkcJLVmIpDmr6ZDSBVjjyihqWdNxOpHT2wVvsbJDOOqmyNBDNPmSVT7/pub?gid=0&single=true&output=csv"

@st.cache_data(ttl=300)
def charger_donnees():
    df = pd.read_csv(SHEET_CSV_URL)
    df['Échéance'] = pd.to_datetime(df['Échéance'], errors='coerce')
    df['État d’avancement'] = df['État d’avancement'].fillna("")
    df['Terminée'] = df['État d’avancement'].str.lower().str.contains("terminée")
    df['En cours'] = df['État d’avancement'].str.lower().str.contains("cours")
    df['En retard'] = (df['Échéance'] < pd.Timestamp.today()) & (~df['Terminée'])
    return df

# -------------------- Titre et rechargement --------------------
st.title("Suivi des Activités & Échéances des Rendus")

if st.button("🔄 Recharger les données"):
    st.cache_data.clear()

df = charger_donnees()

# -------------------- KPI --------------------
st.subheader("📌 Indicateurs clés")
col1, col2, col3, col4 = st.columns(4)
col1.metric("📦 Total des Activité à réaliser", len(df))
col2.metric("🟩 Activtés Terminées", df['Terminée'].sum())
col3.metric("⏳ Activité En cours", df['En cours'].sum())
col4.metric("🕓 Activité En retard", df['En retard'].sum())

# -------------------- Défilement automatique --------------------
# Ici il doit y'avoir trois cadres en utilisant les col de streamlit avec une mise page optimale
# destinés pour chaque indicateur : Terminée, En cours, En retard
# L'activité de chaque des indicateurs doivent défiler mot par mot
# avec un sleep de 1/2 seconde par mot suivi des commentaires sur fichiers
st.subheader("🔄 Activités")
categories = {
    "🟩 Terminées": df[df['Terminée']]['Activité'].tolist(),
    "⏳ En cours": df[df['En cours']]['Activité'].tolist(),
    "🕓 En retard": df[df['En retard']]['Activité'].tolist()
}
placeholder = st.empty()
for i in range(1):  # nombre de cycles de défilement
    for etat, activites in categories.items():
        with placeholder.container():
            st.markdown(f"### {etat}")
            if not activites:
                st.info("Aucune activité.")
            else:
                for act in activites:
                    st.success(f"• {act}")
                    time.sleep(0.4)
            time.sleep(1.2)

# -------------------- ALERTES --------------------
# Ici il doit y'avoir aussi une alerte pour chaque responsable
# de son activité en retard ou imminente
st.subheader("🚨 Tâches en retard ou imminentes")
df_alertes = df[~df['Terminée'] & df['Échéance'].notna()].copy()
df_alertes['Jours restants'] = (df_alertes['Échéance'] - pd.Timestamp.now()).dt.days
df_alertes['Alerte'] = df_alertes['Jours restants'].apply(lambda x:
    "🟥 EN RETARD" if x < 0 else ("🟨 Échéance proche" if x <= 3 else "")
)

alerte_df = df_alertes[df_alertes['Alerte'] != ""][['Activité', 'R (Responsable)', 'Échéance', 'Jours restants', 'Alerte']]
if not alerte_df.empty:
    st.dataframe(alerte_df)
else:
    st.success("✅ Aucune tâche urgente ou en retard.")

# -------------------- GRAPHIQUES --------------------
st.subheader("📈 Suivi visuel des échéances et avancement")
g1, g2 = st.columns(2)

# Graphe 1 : Répartition des tâches par état
# Répartition des tâches selon les différents états d'avancement : Terminée, En cours, etc.
with g1:
    fig1 = px.histogram(df, x="État d’avancement", color="État d’avancement",
                        title="Répartition des tâches par état d’avancement",
                        color_discrete_sequence=px.colors.qualitative.Set2)
    st.plotly_chart(fig1, use_container_width=True)

# Graphe 2 : Nombre de tâches par date d’échéance
with g2:
    df_echeances = df[df['Échéance'].notna()].copy()
    df_echeances['Jour'] = df_echeances['Échéance'].dt.date
    nb_par_jour = df_echeances.groupby('Jour').size().reset_index(name='Nombre de tâches')

    fig2 = px.bar(nb_par_jour, x='Jour', y='Nombre de tâches',
                  title="📅 Nombre de tâches par jour d’échéance",
                  labels={"Jour": "Date", "Nombre de tâches": "Tâches"},
                  color='Nombre de tâches',
                  color_continuous_scale='Tealrose')
    st.plotly_chart(fig2, use_container_width=True)

# Graphe 3 : État d’avancement par responsable
if "R (Responsable)" in df.columns:
    fig3 = px.histogram(df, x="R (Responsable)", color="État d’avancement",
                        title="Tâches par responsable et par état d’avancement",
                        barmode="stack",
                        color_discrete_sequence=px.colors.qualitative.Pastel)
    st.plotly_chart(fig3, use_container_width=True)

# -------------------- TABLEAU COMPLET --------------------
# Ici l'utilisateur doit pouvoir apporter des modifications sur le tableau complet
# Il doit pouvoir ajouter une nouvelle activité, modifier une activité existante
# ou supprimer une activité et les modifications doivent être enregistrées dans la Google Sheet
st.subheader("📋 Tableau complet des tâches")
st.dataframe(df[['Activité', 'R (Responsable)', 'C (Contributeurs)', 'État d’avancement', 'Commentaires', 'Échéance']])
