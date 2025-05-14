import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
from fpdf import FPDF
import tempfile
import datetime

# ----- CONFIGURATION GÉNÉRALE -----
st.set_page_config(page_title="Plateforme EMS", layout="wide")
st.title("🔌 Page d'analyses – Energy Management System")

# ----- CHARGEMENT DES DONNÉES -----
uploaded_file = st.file_uploader("📂 Importer un fichier CSV ou Excel", type=["csv", "xlsx"])

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        st.success("✅ Données chargées avec succès !")

        if st.checkbox("🔍 Aperçu des données brutes"):
            st.dataframe(df.head())

        st.sidebar.header("🔧 Configuration")
        date_col = st.sidebar.selectbox("🕒 Colonne de date", df.columns)
        value_col = st.sidebar.selectbox("⚡ Colonne de consommation", df.columns)
        site_col = st.sidebar.selectbox("🏭 Colonne site / équipement (optionnel)", ["Aucun"] + list(df.columns))

        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=[date_col])

        st.sidebar.subheader("📅 Filtrer par période")
        min_date, max_date = df[date_col].min(), df[date_col].max()
        date_range = st.sidebar.date_input("Période", [min_date, max_date], min_value=min_date, max_value=max_date)
        if len(date_range) == 2:
            df = df[(df[date_col] >= pd.to_datetime(date_range[0])) & (df[date_col] <= pd.to_datetime(date_range[1]))]

        st.sidebar.subheader("📊 Agrégation")
        period = st.sidebar.selectbox("Période", ["Aucune", "Jour", "Semaine", "Mois", "Trimestre", "Année"])

        if period != "Aucune":
            if period == "Jour":
                df["Période"] = df[date_col].dt.date
            elif period == "Semaine":
                df["Période"] = df[date_col].dt.to_period("W").apply(lambda r: r.start_time)
            elif period == "Mois":
                df["Période"] = df[date_col].dt.to_period("M").apply(lambda r: r.start_time)
            elif period == "Trimestre":
                df["Période"] = df[date_col].dt.to_period("Q").apply(lambda r: r.start_time)
            elif period == "Année":
                df["Période"] = df[date_col].dt.to_period("Y").apply(lambda r: r.start_time)

            group_cols = ["Période"]
            if site_col != "Aucun":
                group_cols.append(site_col)
            df_grouped = df.groupby(group_cols)[value_col].sum().reset_index()
        else:
            df_grouped = df.copy()

        st.subheader("📈 Visualisation de la consommation")
        graph_type = st.selectbox("🎨 Type de graphique", ["Ligne", "Barres", "Boîte", "Violon", "Camembert", "Bulles"])
        x_axis = "Période" if period != "Aucune" else date_col
        color = site_col if site_col != "Aucun" else None
        color_sequence = None if site_col != "Aucun" else ["mediumseagreen", "palegreen"]
        titre_base = f"{value_col} ({period})" if period != "Aucune" else f"{value_col}"

        if graph_type == "Ligne":
            fig = px.line(df_grouped, x=x_axis, y=value_col, color=color, color_discrete_sequence=color_sequence,
                        markers=True, title=f"Consommation énergétique - {titre_base}")
            fig.update_yaxes(title="Consommation (kWh)")

        elif graph_type == "Barres":
            fig = px.bar(df_grouped, x=x_axis, y=value_col, color=color, color_discrete_sequence=color_sequence,
                        title=f"Consommation énergétique - {titre_base}")
            fig.update_yaxes(title="Consommation (kWh)")

        elif graph_type == "Boîte":
            fig = px.box(df_grouped, x=color if color else x_axis, y=value_col,
                        color=color if color else None, color_discrete_sequence=color_sequence,
                        title=f"Distribution consommation - {titre_base}")
            fig.update_yaxes(title="Consommation (kWh)")

        elif graph_type == "Violon":
            fig = px.violin(df_grouped, x=color if color else x_axis, y=value_col,
                            box=True, points="all", color=color if color else None,
                            color_discrete_sequence=color_sequence,
                            title=f"Distribution consommation - {titre_base}")
            fig.update_yaxes(title="Consommation (kWh)")

        elif graph_type == "Camembert":
            pie_df = df_grouped.copy()
            if color:
                pie_df = pie_df.groupby(color)[value_col].sum().reset_index()
                fig = px.pie(pie_df, names=color, values=value_col,
                            color_discrete_sequence=color_sequence,
                            title=f"Répartition par {color} - {value_col} ({period})")
            else:
                pie_df = pie_df.groupby(x_axis)[value_col].sum().reset_index()
                fig = px.pie(pie_df, names=x_axis, values=value_col,
                            color_discrete_sequence=color_sequence,
                            title=f"Répartition par {x_axis} - {value_col} ({period})")

        elif graph_type == "Bulles":
            fig = px.scatter(df_grouped, x=x_axis, y=value_col, size=value_col,
                            color=color, color_discrete_sequence=color_sequence,
                            title=f"Nuage de points - {titre_base}")
            fig.update_yaxes(title="Consommation (kWh)")

        st.plotly_chart(fig, use_container_width=True)

        # ----- ANALYSE HORAIRE AVEC AGRÉGATION -----
        st.subheader("⏱️ Analyse des heures de fonctionnement vs consommation")

        def analyse_horaire_par_periode(df, date_col, value_col):
            df = df.copy()
            df["Heure"] = df[date_col].dt.time
            df["Période"] = df[date_col].dt.to_period("D").apply(lambda r: r.start_time)

            st.markdown("**Définir les plages horaires de fonctionnement (HH:MM-HH:MM)**")
            horaire_input = st.text_input("Exemple : 05:00-22:00", "05:00-22:00")

            def parse_plages(plage_str):
                plages = []
                for plage in plage_str.split(","):
                    try:
                        debut, fin = plage.strip().split("-")
                        debut_time = datetime.datetime.strptime(debut, "%H:%M").time()
                        fin_time = datetime.datetime.strptime(fin, "%H:%M").time()
                        plages.append((debut_time, fin_time))
                    except:
                        st.error("Format incorrect. Utilisez HH:MM-HH:MM")
                        return []
                return plages

            plages = parse_plages(horaire_input)
            if not plages:
                return

            def est_dans_plage(t):
                return any(debut <= t <= fin for debut, fin in plages)

            df["Hors_Plages"] = ~df["Heure"].apply(est_dans_plage)

            conso_totale = df[value_col].sum()
            conso_hors_plage = df[df["Hors_Plages"]][value_col].sum()

            st.markdown(f"**Consommation totale :** {conso_totale:,.2f} kWh")
            st.markdown(f"**Consommation hors plages horaires :** <span style='color:red'>{conso_hors_plage:,.2f} kWh</span>", unsafe_allow_html=True)

            fig_bar = go.Figure()
            df_sorted = df.sort_values(by=date_col)
            couleurs = ["red" if hors else "green" for hors in df_sorted["Hors_Plages"]]
            fig_bar.add_trace(go.Bar(
                x=df_sorted[date_col],
                y=df_sorted[value_col],
                marker_color=couleurs
            ))
            fig_bar.update_layout(
                title="Consommation par timestamp (rouge = hors plages)",
                xaxis_title="Date",
                yaxis_title="Consommation (kWh)"
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        analyse_horaire_par_periode(df, date_col, value_col)

    except Exception as e:
        st.error(f"❌ Erreur lors du traitement du fichier : {e}")
else:
    st.info("Veuillez importer un fichier CSV ou Excel pour démarrer.")
