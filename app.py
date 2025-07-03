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
        ventes["montant"] = ventes["quantite"] * ventes["prix_unitaire"]
        sorties = get_data("sorties")
        points = get_data("points_cabines")
        total_ventes = ventes["montant"].sum()
        total_sorties = sorties["montant"].sum()
        total_mm_commissions = points["commissions"].sum()
        benefice_global = total_ventes + total_mm_commissions - total_sorties

        st.metric("Total ventes restaurant", f"{total_ventes:,.0f} FCFA")
        st.metric("Total commissions Mobile Money", f"{total_mm_commissions:,.0f} FCFA")
        st.metric("Total sorties", f"{total_sorties:,.0f} FCFA")
        st.metric("Bénéfice global", f"{benefice_global:,.0f} FCFA")

        st.subheader("Détail ventes restaurant")
        st.dataframe(ventes)

        st.subheader("Détail points cabines Mobile Money")
        st.dataframe(points)

        # Graphiques ventes par catégorie
        if not ventes.empty:
            ventes_categ = ventes.groupby("categorie").agg({"montant":"sum"}).reset_index()
            fig = px.pie(ventes_categ, names="categorie", values="montant", title="Répartition des ventes par catégorie")
            st.plotly_chart(fig, use_container_width=True)

        # Graphique évolution des ventes dans le temps
        if not ventes.empty:
            ventes_date = ventes.groupby("date").agg({"montant":"sum"}).reset_index()
            fig2 = px.bar(ventes_date, x="date", y="montant", title="Évolution des ventes dans le temps")
            st.plotly_chart(fig2, use_container_width=True)

    elif choix == "Ajouter vente":
        st.subheader("Nouvelle vente")
        date = st.date_input("Date", value=datetime.now().date())
        produit = st.text_input("Produit")
        categorie = st.selectbox("Catégorie", ["Bière", "Plat", "Boisson", "Autre"])
        quantite = st.number_input("Quantité", min_value=1)
        prix = st.number_input("Prix unitaire", min_value=0.0)
        if confirmer_ajout("Confirmer l'ajout") and st.button("Valider"):
            ajouter_vente(str(date), produit, categorie, quantite, prix)
            st.success("Vente enregistrée.")

    elif choix == "Ajouter sortie":
        st.subheader("Nouvelle sortie")
        date = st.date_input("Date", value=datetime.now().date())
        description = st.text_input("Description")
        montant = st.number_input("Montant", min_value=0.0)
        if confirmer_ajout("Confirmer l'ajout") and st.button("Valider"):
            ajouter_sortie(str(date), description, montant)
            st.success("Sortie enregistrée.")

    elif choix == "Gestion cabines":
        st.subheader("Ajouter une cabine")
        numero = st.text_input("Numéro cabine")
        statut = st.selectbox("Statut", ["Active", "Inoccupée", "En maintenance"])
        date_ouverture = st.date_input("Date d'ouverture", value=datetime.now().date())
        date_fermeture = st.text_input("Date de fermeture (facultatif)", value="")
        operateur = st.selectbox("Opérateur", ["MTN", "Moov", "Wave", "Autre"])
        solde_actuel = st.number_input("Solde actuel (FCFA)", min_value=0.0)
        total_commissions = st.number_input("Total commissions (FCFA)", min_value=0.0)
        if confirmer_ajout("Confirmer l'ajout") and st.button("Ajouter"):
            ajouter_cabine(numero, statut, str(date_ouverture), date_fermeture if date_fermeture else None,
                           operateur, solde_actuel, total_commissions)
            st.success("Cabine ajoutée.")
        st.subheader("Liste des cabines")
        st.dataframe(get_data("cabines"))

    elif choix == "Points journaliers Mobile Money":
        st.subheader("Ajouter point journalier Mobile Money")
        date = st.date_input("Date", value=datetime.now().date())
        numero_cabine = st.text_input("Numéro de cabine")
        operateur = st.selectbox("Opérateur", ["MTN", "Moov", "Celtiis"])
        espece = st.number_input("Montant en espèces initial", min_value=0.0)
        float_val = st.number_input("Montant float sur SIM", min_value=0.0)
        credit = st.number_input("Montant crédit sur SIM", min_value=0.0)
        commissions = st.number_input("Commission prévue", min_value=0.0)
        if confirmer_ajout("Confirmer l'ajout") and st.button("Ajouter"):
            ajouter_point_journalier(str(date), numero_cabine, operateur, espece, float_val, credit, commissions)
            st.success("Point journalier enregistré.")
        st.subheader("Historique des points journaliers")
        st.dataframe(get_data("points_cabines"))

    elif choix == "Rapport combiné PDF":
        ventes, points = get_data("ventes"), get_data("points_cabines")

        # Dates par défaut
        if not ventes.empty:
            min_date = pd.to_datetime(ventes["date"]).min()
            max_date = pd.to_datetime(ventes["date"]).max()
        else:
            min_date = max_date = datetime.now()

        date_debut = st.date_input("Date début", value=min_date)
        date_fin = st.date_input("Date fin", value=max_date)

        # Gestion sécurité colonne numero_cabine
        if points.empty or "numero_cabine" not in points.columns:
            cabines_dispo = []
        else:
            cabines_dispo = points["numero_cabine"].dropna().unique().tolist()

        if not cabines_dispo:
            cabines_dispo = ["Aucune cabine"]

        cabine_choisie = st.multiselect("Filtrer par cabine", cabines_dispo,
                                       default=cabines_dispo if cabines_dispo != ["Aucune cabine"] else [])

        # Filtrage ventes
        ventes_f = ventes[
            (pd.to_datetime(ventes["date"]) >= pd.to_datetime(date_debut)) &
            (pd.to_datetime(ventes["date"]) <= pd.to_datetime(date_fin))
        ]

        # Filtrage points
        if "Aucune cabine" in cabine_choisie:
            points_f = points[
                (pd.to_datetime(points["date"]) >= pd.to_datetime(date_debut)) &
                (pd.to_datetime(points["date"]) <= pd.to_datetime(date_fin))
            ]
        else:
            points_f = points[
                (pd.to_datetime(points["date"]) >= pd.to_datetime(date_debut)) &
                (pd.to_datetime(points["date"]) <= pd.to_datetime(date_fin)) &
                (points["numero_cabine"].isin(cabine_choisie))
            ]

        if st.button("Générer PDF et envoyer par email"):
            nom_fichier = f"rapport_combine_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            path = generer_pdf_combine(ventes_f, points_f, nom_fichier)
            envoyer_email_avec_fichier(path)
            st.success(f"Rapport généré et envoyé à {EMAIL_DESTINATAIRE}")

    elif choix == "Historique détaillé":
        st.subheader("Ventes")
        st.dataframe(get_data("ventes"))
        st.subheader("Sorties")
        st.dataframe(get_data("sorties"))
        st.subheader("Cabines")
        st.dataframe(get_data("cabines"))
        st.subheader("Points journaliers Mobile Money")
        st.dataframe(get_data("points_cabines"))

    elif choix == "⚠️ Réinitialiser BDD":
        if st.button("Réinitialiser la base de données (TOUTES les données seront perdues)"):
            os.remove(DB_FILE) if os.path.exists(DB_FILE) else None
            init_db()
            st.success("Base de données réinitialisée.")

    # FOOTER
    st.markdown(
        f"""
        <style>
        footer {{
            position: fixed;
            left: 0;
            bottom: 0;
            width: 100%;
            background-color: #f0f2f6;
            text-align: center;
            padding: 10px 0;
            font-size: 12px;
            color: #888888;
            z-index: 9999;
        }}
        </style>
        <footer>© 2025 {BAR_NOM} | Contact : {BAR_CONTACT} | Développé par Jannos AHANNINKPO</footer>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
