import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO

st.set_page_config(page_title="Plateforme EMS", layout="wide")

st.title("🔌 Plateforme EMS – Energy Management System")

# ----------- UPLOAD SECTION -----------
uploaded_file = st.file_uploader("📂 Importer un fichier CSV ou Excel", type=["csv", "xlsx"])

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        st.success("✅ Données chargées avec succès !")

        # ----------- PRÉVISUALISATION -----------
        if st.checkbox("🔍 Aperçu des données"):
            st.dataframe(df.head())

        # ----------- SÉLECTION DES COLONNES -----------
        st.sidebar.header("🔧 Configuration")
        date_col = st.sidebar.selectbox("🕒 Colonne de date", df.columns)
        value_col = st.sidebar.selectbox("⚡ Colonne de consommation", df.columns)

        # Conversion de la date
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=[date_col])

        # ----------- FILTRAGE PAR DATE -----------
        st.sidebar.subheader("📅 Filtrer par période")
        min_date, max_date = df[date_col].min(), df[date_col].max()
        date_range = st.sidebar.date_input("Choisir une période", [min_date, max_date], min_value=min_date, max_value=max_date)

        if len(date_range) == 2:
            df = df[(df[date_col] >= pd.to_datetime(date_range[0])) & (df[date_col] <= pd.to_datetime(date_range[1]))]

        # ----------- AGRÉGATION PAR PÉRIODE -----------
        st.sidebar.subheader("📊 Agrégation")
        period = st.sidebar.selectbox("Période", ["Aucune", "Jour", "Semaine", "Mois", "Année"])

        if period != "Aucune":
            if period == "Jour":
                df["Période"] = df[date_col].dt.date
            elif period == "Semaine":
                df["Période"] = df[date_col].dt.to_period("W").apply(lambda r: r.start_time)
            elif period == "Mois":
                df["Période"] = df[date_col].dt.to_period("M").apply(lambda r: r.start_time)
            elif period == "Année":
                df["Période"] = df[date_col].dt.to_period("Y").apply(lambda r: r.start_time)

            df_grouped = df.groupby("Période")[value_col].sum().reset_index()
        else:
            df_grouped = df.copy()

        # ----------- GRAPHIQUE INTERACTIF -----------
        st.subheader("📈 Visualisation de la consommation")
        fig = px.line(df_grouped, x="Période" if period != "Aucune" else date_col, y=value_col,
                      title=f"Consommation énergétique ({period.lower() if period != 'Aucune' else 'non agrégée'})",
                      markers=True)
        st.plotly_chart(fig, use_container_width=True)

        # ----------- TÉLÉCHARGEMENT DU FICHIER TRAITÉ -----------
        st.markdown("### ⬇️ Télécharger les données filtrées")
        to_download = df_grouped if period != "Aucune" else df
        csv = to_download.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Télécharger en CSV", data=csv, file_name="donnees_traitees.csv", mime="text/csv")

    except Exception as e:
        st.error(f"❌ Erreur lors du traitement du fichier : {e}")
else:
    st.info("Veuillez importer un fichier CSV ou Excel pour démarrer.")
