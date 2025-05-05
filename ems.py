import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
from fpdf import FPDF
import smtplib
from email.message import EmailMessage
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

        # Aperçu
        if st.checkbox("🔍 Aperçu des données brutes"):
            st.dataframe(df.head())

        # ----- CONFIGURATION UTILISATEUR -----
        st.sidebar.header("🔧 Configuration")
        date_col = st.sidebar.selectbox("🕒 Colonne de date", df.columns)
        value_col = st.sidebar.selectbox("⚡ Colonne de consommation", df.columns)
        site_col = st.sidebar.selectbox("🏭 Colonne site / équipement (optionnel)", ["Aucun"] + list(df.columns))

        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=[date_col])

        # ----- FILTRAGE -----
        st.sidebar.subheader("📅 Filtrer par période")
        min_date, max_date = df[date_col].min(), df[date_col].max()
        date_range = st.sidebar.date_input("Période", [min_date, max_date], min_value=min_date, max_value=max_date)
        if len(date_range) == 2:
            df = df[(df[date_col] >= pd.to_datetime(date_range[0])) & (df[date_col] <= pd.to_datetime(date_range[1]))]

        # ----- AGRÉGATION -----
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

            group_cols = ["Période"]
            if site_col != "Aucun":
                group_cols.append(site_col)
            df_grouped = df.groupby(group_cols)[value_col].sum().reset_index()
        else:
            df_grouped = df.copy()

        # ----- GRAPHIQUE INTERACTIF -----
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



        # ----- KPI ET DÉRIVES -----
        st.subheader("📉 Suivi des KPI et dérives")
        cible = st.number_input("🎯 Objectif de consommation", min_value=0.0, value=100.0)
        seuil_pct = st.slider("⚠️ Seuil de dérive (%)", 1, 100, 20)

        # Calcul de l'écart en pourcentage
        df_grouped["Écart (%)"] = ((df_grouped[value_col] - cible) / cible * 100).round(2)

        # Identifier les dérives uniquement pour les dépassements positifs
        df_grouped["Dérive"] = df_grouped["Écart (%)"].apply(lambda x: "Oui" if x > seuil_pct else "Non")

        st.dataframe(df_grouped)

        # Filtrage des dérives détectées (uniquement les dépassements)
        derives_detectees = df_grouped[df_grouped["Dérive"] == "Oui"]
        st.write(f"🔎 Dérives détectées : {len(derives_detectees)}")


        # ----- SUIVI / COMMENTAIRES DES DÉRIVES -----
        st.subheader("🛠 Traitement des dérives")
        commentaires = {}
        for idx, row in derives_detectees.iterrows():
            periode = row["Période"] if "Période" in row else row[date_col]
            identifiant = f"{periode}_{row.get(site_col, '')}"
            key = f"comment_{identifiant}"
            libelle = f"{periode} - {row.get(site_col, '')}" if site_col != "Aucun" else f"{periode}"
            commentaires[key] = st.text_input(f"📝 Commentaire pour {libelle}", key=key)

        # ----- RAPPORT PDF -----
        def save_plotly_fig_as_image(fig):
            import plotly.io as pio
            import tempfile
            try:
                img_bytes = pio.to_image(fig, format='png', width=1000, height=600, engine="kaleido")
                temp_img = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                temp_img.write(img_bytes)
                temp_img.close()
                return temp_img.name
            except Exception as e:
                st.error(f"Erreur lors de la génération de l'image du graphique : {e}")
                return None


       
        st.subheader("🧾 Génération de rapport PDF")

        def generate_pdf(df_report, comments_dict, fig_image_path=None):
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()
            
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "Rapport EMS", ln=True, align='C')
            pdf.ln(8)

            pdf.set_font("Arial", "", 11)
            for idx, row in df_report.iterrows():
                periode = row.get("Période", f"Ligne {idx}")
                site = row.get("Site", "")
                conso = row.get("Consommation", 0)
                ecart = row.get("Écart (%)", 0)
                
                pdf.set_font("Arial", "B", 11)
                pdf.cell(0, 8, f"{periode} - {site}", ln=True)
                
                pdf.set_font("Arial", "", 11)
                pdf.cell(0, 6, f"Consommation : {conso:.2f} kWh", ln=True)
                pdf.cell(0, 6, f"Écart : {ecart:.1f} %", ln=True)

                comment = comments_dict.get(f"comment_{idx}", "")
                if comment:
                    pdf.set_text_color(50, 50, 50)  # gris foncé
                    pdf.multi_cell(0, 6, f"Commentaire : {comment}")
                    pdf.set_text_color(0, 0, 0)
                pdf.ln(4)

            if fig_image_path:
                pdf.add_page()
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 10, "Visualisation graphique", ln=True, align="C")
                pdf.ln(5)
                try:
                    pdf.image(fig_image_path, x=15, w=180)  # centrée et en couleur
                except Exception as e:
                    st.error(f"Erreur lors de l'ajout du graphique au PDF : {e}")

            temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            pdf.output(temp_pdf.name)
            return temp_pdf



        if st.button("📤 Générer le rapport PDF"):
            fig_image_path = save_plotly_fig_as_image(fig)
            pdf_file = generate_pdf(derives_detectees, commentaires, fig_image_path)
            if pdf_file:
                with open(pdf_file.name, "rb") as f:
                    st.download_button("📥 Télécharger le rapport PDF", f, file_name="rapport_ems.pdf")



        # ----- EXPORT CSV -----
        st.markdown("### ⬇️ Télécharger les données filtrées")
        csv = df_grouped.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Télécharger en CSV", data=csv, file_name="donnees_traitees.csv", mime="text/csv")

    except Exception as e:
        st.error(f"❌ Erreur lors du traitement du fichier : {e}")
else:
    st.info("Veuillez importer un fichier CSV ou Excel pour démarrer.")
