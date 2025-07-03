# -*- coding: utf-8 -*-
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from fpdf import FPDF
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.mime.text import MIMEText
import plotly.express as px
import numpy as np

# --- Constantes ---
DB_FILE = "ventes_restaurant.db"
RAPPORTS_DIR = "rapports"
EMAIL_SOURCE = "ahanninkpojannos@gmail.com"
EMAIL_DESTINATAIRE = "ahanninkpojannos@gmail.com"
EMAIL_MDP = "xctk xfok vanj jkjj"  # mot de passe application Gmail

BAR_NOM = "Le Noctambul"
BAR_CONTACT = "+229 0190661015"

if not os.path.exists(RAPPORTS_DIR):
    os.makedirs(RAPPORTS_DIR)

# --- Initialisation BDD ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ventes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        produit TEXT,
        categorie TEXT,
        quantite INTEGER,
        prix_unitaire REAL
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sorties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        description TEXT,
        montant REAL
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cabines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero TEXT UNIQUE,
        statut TEXT,
        date_ouverture TEXT,
        date_fermeture TEXT,
        operateur TEXT DEFAULT 'Inconnu',
        solde_actuel REAL DEFAULT 0,
        total_commissions REAL DEFAULT 0
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS points_cabines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        numero_cabine TEXT,
        operateur TEXT,
        espece REAL,
        float REAL,
        credit REAL,
        commissions REAL
    )""")
    conn.commit()
    conn.close()

# --- Fonctions utilitaires ---
def confirmer_ajout(message):
    return st.checkbox(message + " (Confirmez ici avant de valider)")

def get_data(table):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
    conn.close()
    return df

def ajouter_vente(date, produit, categorie, quantite, prix):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO ventes (date, produit, categorie, quantite, prix_unitaire) VALUES (?, ?, ?, ?, ?)",
                   (date, produit, categorie, quantite, prix))
    conn.commit()
    conn.close()

def ajouter_sortie(date, description, montant):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO sorties (date, description, montant) VALUES (?, ?, ?)",
                   (date, description, montant))
    conn.commit()
    conn.close()

def ajouter_cabine(numero, statut, date_ouverture, date_fermeture, operateur, solde_actuel, total_commissions):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO cabines (numero, statut, date_ouverture, date_fermeture, operateur, solde_actuel, total_commissions)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (numero, statut, date_ouverture, date_fermeture, operateur, solde_actuel, total_commissions))
    conn.commit()
    conn.close()

def ajouter_point_journalier(date, numero_cabine, operateur, espece, float_val, credit, commissions):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO points_cabines (date, numero_cabine, operateur, espece, float, credit, commissions)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (date, numero_cabine, operateur, espece, float_val, credit, commissions))
    conn.commit()
    conn.close()

# --- Génération PDF avec tableaux par cabine ---
def generer_pdf_combine(ventes_df, points_df, nom_fichier):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(200, 10, f"Rapport Combiné {BAR_NOM}", ln=True, align="C")
    pdf.set_font("Arial", "I", 10)
    pdf.cell(200, 8, f"Généré le {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align="C")
    pdf.ln(10)

    # Section Ventes
    pdf.set_font("Arial", "B", 12)
    pdf.cell(200, 8, "Détails des ventes Restaurant", ln=True)
    pdf.set_font("Arial", "", 10)
    if ventes_df.empty:
        pdf.cell(200, 8, "Aucune vente enregistrée.", ln=True)
    else:
        pdf.cell(25,8,"Date",1); pdf.cell(35,8,"Produit",1); pdf.cell(25,8,"Catégorie",1)
        pdf.cell(20,8,"Qté",1,align="R"); pdf.cell(30,8,"Prix unit.",1,align="R")
        pdf.cell(30,8,"Total",1,ln=True,align="R")
        total_general = 0
        for _, row in ventes_df.iterrows():
            total_ligne = row["quantite"] * row["prix_unitaire"]
            total_general += total_ligne
            pdf.cell(25,8,str(row["date"]),1)
            pdf.cell(35,8,str(row["produit"]),1)
            pdf.cell(25,8,str(row["categorie"]),1)
            pdf.cell(20,8,f"{row['quantite']}",1,align="R")
            pdf.cell(30,8,f"{row['prix_unitaire']:.0f}",1,align="R")
            pdf.cell(30,8,f"{total_ligne:.0f}",1,ln=True,align="R")
        pdf.set_font("Arial","B",10)
        pdf.cell(135,8,"TOTAL VENTES",1)
        pdf.cell(30,8,f"{total_general:.0f}",1,ln=True,align="R")

    pdf.ln(12)

    # Section Points Cabines par cabine distincte
    if "numero_cabine" not in points_df.columns:
        points_df["numero_cabine"] = "N/A"

    pdf.set_font("Arial", "B", 12)
    pdf.cell(200, 8, "Détails Points Cabines Mobile Money", ln=True)
    pdf.ln(4)

    if points_df.empty:
        pdf.set_font("Arial", "", 10)
        pdf.cell(200, 8, "Aucun point enregistré.", ln=True)
    else:
        for cabine in points_df["numero_cabine"].dropna().unique():
            pdf.set_font("Arial", "B", 11)
            pdf.cell(200, 8, f"Cabine : {cabine}", ln=True)
            pdf.set_font("Arial", "B", 10)
            pdf.cell(25,8,"Date",1)
            pdf.cell(25,8,"Opérateur",1)
            pdf.cell(25,8,"Espèces",1,align="R")
            pdf.cell(25,8,"Float",1,align="R")
            pdf.cell(25,8,"Crédit",1,align="R")
            pdf.cell(30,8,"Commiss.",1,ln=True,align="R")

            totaux = {"espece":0,"float":0,"credit":0,"commissions":0}

            df_cabine = points_df[points_df["numero_cabine"] == cabine]
            for _, row in df_cabine.iterrows():
                pdf.set_font("Arial", "", 10)
                pdf.cell(25,8,str(row["date"]),1)
                pdf.cell(25,8,str(row["operateur"]),1)
                pdf.cell(25,8,f"{row['espece']:.0f}",1,align="R")
                pdf.cell(25,8,f"{row['float']:.0f}",1,align="R")
                pdf.cell(25,8,f"{row['credit']:.0f}",1,align="R")
                pdf.cell(30,8,f"{row['commissions']:.0f}",1,ln=True,align="R")
                totaux["espece"] += row["espece"]
                totaux["float"] += row["float"]
                totaux["credit"] += row["credit"]
                totaux["commissions"] += row["commissions"]

            pdf.set_font("Arial", "B", 10)
            pdf.cell(50,8,"TOTAL",1)
            pdf.cell(25,8,f"{totaux['espece']:.0f}",1,align="R")
            pdf.cell(25,8,f"{totaux['float']:.0f}",1,align="R")
            pdf.cell(25,8,f"{totaux['credit']:.0f}",1,align="R")
            pdf.cell(30,8,f"{totaux['commissions']:.0f}",1,ln=True,align="R")
            pdf.ln(10)

    path = os.path.join(RAPPORTS_DIR, nom_fichier)
    pdf.output(path)
    return path

# --- Envoi email ---
def envoyer_email_avec_fichier(fichier):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SOURCE
    msg['To'] = EMAIL_DESTINATAIRE
    msg['Subject'] = f"Rapport PDF {BAR_NOM}"
    msg.attach(MIMEText("Veuillez trouver ci-joint le rapport combiné.", 'plain'))
    with open(fichier, "rb") as f:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(fichier)}')
        msg.attach(part)
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(EMAIL_SOURCE, EMAIL_MDP)
    server.send_message(msg)
    server.quit()

# --- Interface Streamlit principale ---
def main():
    st.set_page_config(page_title=f"Gestion Globale - {BAR_NOM}", layout="wide")
    st.title(f"📊 Gestion Restaurant & 💰 Mobile Money - {BAR_NOM}")
    init_db()

    # Gestion affichage menu avec bouton
    if 'show_menu' not in st.session_state:
        st.session_state.show_menu = True

    if st.button("☰ Menu"):
        st.session_state.show_menu = not st.session_state.show_menu

    # Affichage sidebar si demandé
    if st.session_state.show_menu:
        with st.sidebar:
            choix = st.radio("Menu Principal", [
                "Tableau de bord combiné", "Ajouter vente", "Ajouter sortie", "Gestion cabines",
                "Points journaliers Mobile Money", "Rapport combiné PDF", "Historique détaillé", "⚠️ Réinitialiser BDD"
            ])
    else:
        choix = None

    # Affichage contact en haut
    st.markdown(f"#### 📞 Contact : {BAR_CONTACT}")

    if choix == "Tableau de bord combiné":
        ventes = get_data("ventes")
        points = get_data("points_cabines")

        if ventes.empty:
            st.warning("Aucune donnée de ventes trouvée.")
        if points.empty:
            st.warning("Aucune donnée de points cabines trouvée.")

        # Conversion dates et calcul montant
        ventes["date"] = pd.to_datetime(ventes["date"])
        points["date"] = pd.to_datetime(points["date"])
        ventes["montant"] = ventes["quantite"] * ventes["prix_unitaire"]

        # FILTRES DYNAMIQUES EN SIDEBAR (spécifiques au dashboard)
        st.sidebar.subheader("Filtres Tableau de bord combiné")

        # Filtres cabines
        cabines_dispo = points["numero_cabine"].dropna().unique()
        filtres_cabines = st.sidebar.multiselect("Filtrer par cabine", options=cabines_dispo, default=list(cabines_dispo))

        # Filtres opérateurs
        operateurs_dispo = points["operateur"].dropna().unique()
        filtres_operateurs = st.sidebar.multiselect("Filtrer par opérateur Mobile Money", options=operateurs_dispo, default=list(operateurs_dispo))

        # Filtre dates
        date_min = min(ventes["date"].min(), points["date"].min())
        date_max = max(ventes["date"].max(), points["date"].max())
        date_debut = st.sidebar.date_input("Date début", value=date_min)
        date_fin = st.sidebar.date_input("Date fin", value=date_max)

        # Application filtres
        ventes_f = ventes[(ventes["date"] >= pd.to_datetime(date_debut)) & (ventes["date"] <= pd.to_datetime(date_fin))]
        points_f = points[
            (points["date"] >= pd.to_datetime(date_debut)) &
            (points["date"] <= pd.to_datetime(date_fin)) &
            (points["numero_cabine"].isin(filtres_cabines)) &
            (points["operateur"].isin(filtres_operateurs))
        ]

        # Calculs pour les métriques
        total_ventes = ventes_f["montant"].sum()
        total_mm_commissions = points_f["commissions"].sum()
        sorties = get_data("sorties")
        sorties["montant"] = sorties["montant"].astype(float)
        sorties_f = sorties[
            (pd.to_datetime(sorties["date"]) >= pd.to_datetime(date_debut)) &
            (pd.to_datetime(sorties["date"]) <= pd.to_datetime(date_fin))
        ]
        total_sorties = sorties_f["montant"].sum()
        benefice_global = total_ventes + total_mm_commissions - total_sorties

        st.metric("Total ventes restaurant", f"{total_ventes:,.0f} FCFA")
        st.metric("Total commissions Mobile Money", f"{total_mm_commissions:,.0f} FCFA")
        st.metric("Total sorties", f"{total_sorties:,.0f} FCFA")
        st.metric("Bénéfice global", f"{benefice_global:,.0f} FCFA")

        # Détail Dataframes (avec pagination intégrée)
        st.subheader("Détail ventes restaurant filtrées")
        st.dataframe(ventes_f)

        st.subheader("Détail points cabines Mobile Money filtrés")
        st.dataframe(points_f)

        # Graphique 1 : Évolution des ventes dans le temps
        ventes_date = ventes_f.groupby("date").agg({"montant": "sum"}).reset_index()
        fig_ventes = px.line(
            ventes_date,
            x="date",
            y="montant",
            title="Évolution des ventes dans le temps",
            labels={"montant": "Montant des ventes (FCFA)", "date": "Date"}
        )
        st.plotly_chart(fig_ventes, use_container_width=True)

        # Graphique 2 : Évolution des commissions par cabine
        points_commissions = points_f.groupby(["date", "numero_cabine"]).agg({"commissions": "sum"}).reset_index()
        fig_commissions = px.line(
            points_commissions,
            x="date",
            y="commissions",
            color="numero_cabine",
            title="Évolution des commissions par cabine",
            labels={"commissions": "Commissions (FCFA)", "date": "Date", "numero_cabine": "Cabine"}
        )
        st.plotly_chart(fig_commissions, use_container_width=True)

        # Graphique 3 : Heatmap ventes par jour et heure (simulation heure)
        ventes_f["heure"] = np.random.randint(0, 24, size=len(ventes_f))
        ventes_f["jour_semaine"] = ventes_f["date"].dt.day_name()
        jours_ordonnes = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        ventes_f["jour_semaine"] = pd.Categorical(ventes_f["jour_semaine"], categories=jours_ordonnes, ordered=True)
        heatmap_data = ventes_f.groupby(["jour_semaine", "heure"]).agg({"quantite": "sum"}).reset_index()

        fig_heatmap = px.density_heatmap(
            heatmap_data,
            x="heure",
            y="jour_semaine",
            z="quantite",
            title="Heatmap des ventes par jour et heure",
            labels={"heure": "Heure", "jour_semaine": "Jour de la semaine", "quantite": "Quantité vendue"}
        )
        st.plotly_chart(fig_heatmap, use_container_width=True)

        # Graphique 4 : Barres empilées par catégorie et cabine
        # Fusion partielle des ventes et points_cabines sur date et cabine
        ventes_points = pd.merge(
            ventes_f,
            points_f[["date", "numero_cabine"]],
            how="left",
            on="date"
        )
        ventes_points["montant"] = ventes_points["quantite"] * ventes_points["prix_unitaire"]

        bar_data = ventes_points.groupby(["categorie", "numero_cabine"]).agg({"montant": "sum"}).reset_index()

        fig_bar = px.bar(
            bar_data,
            x="categorie",
            y="montant",
            color="numero_cabine",
            title="Ventes par catégorie et cabine (barres empilées)",
            labels={"montant": "Montant (FCFA)", "categorie": "Catégorie", "numero_cabine": "Cabine"},
            barmode="stack"
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    elif choix == "Ajouter vente":
        st.subheader("Nouvelle vente")
        date = st.date_input("Date", value=datetime.now().date())
        produit = st.text_input("Produit")
        categorie = st.selectbox("Catégorie", ["Bière", "Plat", "Boisson", "Autre"])
        quantite = st.number_input("Quantité", min_value=1, step=1)
        prix_unitaire = st.number_input("Prix unitaire (FCFA)", min_value=0.0, step=100.0)

        if st.button("Ajouter vente"):
            if confirmer_ajout("Confirmer l'ajout de cette vente"):
                ajouter_vente(date.strftime("%Y-%m-%d"), produit, categorie, quantite, prix_unitaire)
                st.success("Vente ajoutée avec succès !")

    elif choix == "Ajouter sortie":
        st.subheader("Nouvelle sortie")
        date = st.date_input("Date", value=datetime.now().date())
        description = st.text_input("Description")
        montant = st.number_input("Montant (FCFA)", min_value=0.0, step=100.0)

        if st.button("Ajouter sortie"):
            if confirmer_ajout("Confirmer l'ajout de cette sortie"):
                ajouter_sortie(date.strftime("%Y-%m-%d"), description, montant)
                st.success("Sortie ajoutée avec succès !")

    elif choix == "Gestion cabines":
        st.subheader("Gestion des cabines Mobile Money")
        cabines = get_data("cabines")
        st.dataframe(cabines)
        with st.form("Ajouter/Modifier cabine"):
            numero = st.text_input("Numéro cabine")
            statut = st.selectbox("Statut", ["Ouverte", "Fermée"])
            date_ouverture = st.date_input("Date ouverture", value=datetime.now().date())
            date_fermeture = st.date_input("Date fermeture", value=datetime.now().date())
            operateur = st.text_input("Opérateur Mobile Money")
            solde_actuel = st.number_input("Solde actuel", min_value=0.0)
            total_commissions = st.number_input("Total commissions", min_value=0.0)
            submit = st.form_submit_button("Ajouter/Modifier cabine")
            if submit:
                if confirmer_ajout("Confirmer l'ajout/modification cabine"):
                    ajouter_cabine(numero, statut, date_ouverture.strftime("%Y-%m-%d"), date_fermeture.strftime("%Y-%m-%d"),
                                  operateur, solde_actuel, total_commissions)
                    st.success("Cabine ajoutée/modifiée")

    elif choix == "Points journaliers Mobile Money":
        st.subheader("Points journaliers Mobile Money")
        points = get_data("points_cabines")
        st.dataframe(points)

        with st.form("Ajouter point journalier"):
            date = st.date_input("Date", value=datetime.now().date())
            numero_cabine = st.text_input("Numéro cabine")
            operateur = st.text_input("Opérateur Mobile Money")
            espece = st.number_input("Espèces (FCFA)", min_value=0.0)
            float_val = st.number_input("Float (FCFA)", min_value=0.0)
            credit = st.number_input("Crédit (FCFA)", min_value=0.0)
            commissions = st.number_input("Commissions (FCFA)", min_value=0.0)
            submit = st.form_submit_button("Ajouter point")
            if submit:
                if confirmer_ajout("Confirmer l'ajout du point"):
                    ajouter_point_journalier(date.strftime("%Y-%m-%d"), numero_cabine, operateur, espece, float_val, credit, commissions)
                    st.success("Point ajouté")

    elif choix == "Rapport combiné PDF":
        st.subheader("Générer un rapport combiné PDF")
        ventes = get_data("ventes")
        points = get_data("points_cabines")

        nom_fichier = f"rapport_combine_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        if st.button("Générer PDF"):
            path = generer_pdf_combine(ventes, points, nom_fichier)
            st.success(f"PDF généré : {path}")

            if st.button("Envoyer PDF par email"):
                try:
                    envoyer_email_avec_fichier(path)
                    st.success("Email envoyé avec succès !")
                except Exception as e:
                    st.error(f"Erreur lors de l'envoi de l'email : {e}")

    elif choix == "Historique détaillé":
        st.subheader("Historique détaillé des données")
        table = st.selectbox("Choisir la table à afficher", ["ventes", "sorties", "cabines", "points_cabines"])
        df = get_data(table)
        st.dataframe(df)

    elif choix == "⚠️ Réinitialiser BDD":
        if st.button("Réinitialiser la base de données (perte de données irréversible)"):
            if confirmer_ajout("Confirmer la réinitialisation de la base"):
                os.remove(DB_FILE)
                init_db()
                st.success("Base de données réinitialisée !")

    else:
        st.info("Utilisez le menu pour naviguer entre les fonctionnalités.")

if __name__ == "__main__":
    main()
