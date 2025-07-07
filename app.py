# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from fpdf import FPDF
import os
import time
from threading import Lock
import zipfile
from pathlib import Path

# --------------------------
# Configuration Email
# --------------------------
EMAIL_SOURCE = "ahanninkpojannos@gmail.com"
EMAIL_MDP = "xctk xfok vanj jkjj" # Assurez-vous d'utiliser un mot de passe d'application valide

# --------------------------
# Database
# --------------------------
db_lock = Lock()
conn = sqlite3.connect("stock.db", check_same_thread=False)
c = conn.cursor()

# (Le reste de la configuration de la DB ne change pas...)
c.execute("CREATE TABLE IF NOT EXISTS stock (id INTEGER PRIMARY KEY, produit TEXT UNIQUE, quantite INTEGER)")
c.execute("CREATE TABLE IF NOT EXISTS achats (id INTEGER PRIMARY KEY, produit TEXT, quantite INTEGER, montant REAL, date_achat TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS journal (id INTEGER PRIMARY KEY, action TEXT, produit TEXT, quantite INTEGER, montant REAL, date_action TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS destinataires (id INTEGER PRIMARY KEY, email TEXT UNIQUE)")
conn.commit()
c.execute("INSERT OR IGNORE INTO destinataires (email) VALUES (?)", (EMAIL_SOURCE,))
conn.commit()

# --------------------------
# Fonctions métier
# --------------------------

def enregistrer_journal(action, produit, quantite=0, montant=0.0):
    with db_lock:
        date_now = datetime.now().strftime("%Y-%m-%d %H:%M")
        c.execute("INSERT INTO journal (action, produit, quantite, montant, date_action) VALUES (?, ?, ?, ?, ?)",
                  (action, produit, quantite, montant, date_now))
        conn.commit()

def supprimer_produit(produit):
    with db_lock:
        c.execute("DELETE FROM stock WHERE produit = ?", (produit,))
        conn.commit()
    enregistrer_journal("Suppression Produit", produit)
    return True, f"Le produit '{produit}' a été supprimé du stock."

def ajouter_produit(produit, quantite):
    if not produit.strip(): return False, "Le nom du produit est vide."
    try:
        with db_lock:
            c.execute("INSERT OR IGNORE INTO stock (produit, quantite) VALUES (?, 0)", (produit.strip(),))
            c.execute("UPDATE stock SET quantite = quantite + ? WHERE produit = ?", (quantite, produit.strip()))
            conn.commit()
        enregistrer_journal("Ajout", produit.strip(), quantite, 0)
        return True, f"{quantite} {produit}(s) ajouté(s) au stock."
    except Exception as e: return False, f"Erreur lors de l'ajout : {e}"

def enregistrer_achat(produit, quantite, montant):
    try:
        with db_lock:
            date_now = datetime.now().strftime("%Y-%m-%d %H:%M")
            c.execute("INSERT INTO achats (produit, quantite, montant, date_achat) VALUES (?, ?, ?, ?)",
                      (produit, quantite, montant, date_now))
            conn.commit()
        ajouter_produit(produit, quantite)
        enregistrer_journal("Achat local", produit, quantite, montant)
        return True, f"Achat enregistré : {quantite} {produit} pour {montant} FCFA."
    except Exception as e: return False, f"Erreur enregistrement achat: {e}"

def vendre_produit(produit, quantite):
    with db_lock:
        c.execute("SELECT quantite FROM stock WHERE produit = ?", (produit,))
        stock = c.fetchone()
        if stock and stock[0] >= quantite:
            c.execute("UPDATE stock SET quantite = quantite - ? WHERE produit = ?", (quantite, produit))
            conn.commit()
            enregistrer_journal("Vente", produit, quantite, 0)
            return True, f"{quantite} {produit}(s) vendu(s)."
        else:
            return False, f"Stock insuffisant. Actuel: {stock[0] if stock else 0}"

def obtenir_stock():
    with db_lock:
        c.execute("SELECT produit, quantite FROM stock ORDER BY produit ASC")
        rows = c.fetchall()
    return pd.DataFrame(rows, columns=['Produit', 'Quantité'])

def obtenir_journal():
    with db_lock:
        c.execute("SELECT action, produit, quantite, montant, date_action FROM journal ORDER BY date_action DESC")
        rows = c.fetchall()
    return pd.DataFrame(rows, columns=['Action', 'Produit', 'Quantité', 'Montant', 'Date'])

def obtenir_destinataires():
    with db_lock:
        c.execute("SELECT email FROM destinataires")
        return [row[0] for row in c.fetchall()]

def ajouter_destinataires(emails_a_ajouter):
    with db_lock:
        for email in emails_a_ajouter:
            c.execute("INSERT OR IGNORE INTO destinataires (email) VALUES (?)", (email,))
        conn.commit()

def supprimer_destinataire(email_a_supprimer):
    with db_lock:
        c.execute("DELETE FROM destinataires WHERE email = ?", (email_a_supprimer,))
        conn.commit()

def generer_pdf_tableau(df, titre="Rapport"):
    if not os.path.exists("rapports"):
        os.makedirs("rapports")
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"{titre} - {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 10)
    if not df.empty:
        col_width = pdf.w / (len(df.columns) + 0.5)
        for col in df.columns:
            pdf.cell(col_width, 10, col, border=1, align='C')
        pdf.ln()
        pdf.set_font("Arial", '', 9)
        for _, row in df.iterrows():
            for item in row:
                pdf.cell(col_width, 10, str(item), border=1, align='L')
            pdf.ln()
    else:
        pdf.set_font("Arial", 'I', 12)
        pdf.cell(0, 10, "Aucune donnée disponible pour ce rapport.", ln=True, align='C')
    filename = f"rapports/{titre.replace(' ','_').lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf.output(filename)
    return filename

def envoyer_mail(chemins_pdf, destinataires, sujet="Rapport - Le Noctambul"):
    if not destinataires:
        st.warning("Aucun destinataire configuré pour l'envoi d'email.")
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SOURCE
        msg['To'] = ", ".join(destinataires)
        msg['Subject'] = sujet
        msg.attach(MIMEText("Veuillez trouver ci-joint les rapports demandés.", 'plain'))

        for chemin_pdf in chemins_pdf:
            with open(chemin_pdf, "rb") as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={os.path.basename(chemin_pdf)}",
            )
            msg.attach(part)
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SOURCE, EMAIL_MDP)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Erreur lors de l'envoi du mail : {e}")
        return False

# --------------------------
# Interface Streamlit
# --------------------------
st.title("🍽️ Gestion de Stock - Le Noctambul")

st.sidebar.subheader("📧 Emails destinataires")
destinataires_db = obtenir_destinataires()
new_emails = st.sidebar.text_area("Ajouter (séparés par virgule)")
if st.sidebar.button("➕ Ajouter Emails"):
    emails_a_ajouter = [e.strip() for e in new_emails.split(',') if e.strip()]
    if emails_a_ajouter:
        ajouter_destinataires(emails_a_ajouter)
        st.sidebar.success("Emails ajoutés !")
        st.rerun()  # ## CORRIGÉ ##

for email in destinataires_db:
    col1, col2 = st.sidebar.columns([4,1])
    col1.write(email)
    if email != EMAIL_SOURCE:
        if col2.button("🗑️", key=f"del_{email}"):
            supprimer_destinataire(email)
            st.rerun()  # ## CORRIGÉ ##

st.sidebar.markdown("---")
menu = st.sidebar.radio("Menu", ["Dashboard", "Ajouter/Vendre", "Rapports"])

if menu == "Dashboard":
    st.subheader("📊 État actuel du stock")
    df_stock = obtenir_stock()
    if not df_stock.empty:
        stock_faible = df_stock[df_stock['Quantité'] < 5]
        if not stock_faible.empty:
            st.error(f"⚠️ {len(stock_faible)} produit(s) en stock critique (< 5) !")
            st.dataframe(stock_faible, use_container_width=True)
        
        st.markdown("---")
        st.dataframe(df_stock, use_container_width=True)
        
        with st.expander("🗑️ Gérer / Supprimer un produit du stock"):
            produit_a_supprimer = st.selectbox("Choisir le produit à supprimer", df_stock['Produit'], key="sel_prod_del")
            if st.button(f"Supprimer DÉFINITIVEMENT '{produit_a_supprimer}'"):
                ok, msg = supprimer_produit(produit_a_supprimer)
                if ok:
                    st.success(msg)
                    st.rerun() # ## CORRIGÉ ## Rafraîchit pour mettre à jour la liste
                else:
                    st.error(msg)
    else:
        st.info("Aucun produit en stock.")

elif menu == "Ajouter/Vendre":
    st.subheader("➕ Ajouter un produit au stock")
    with st.form("ajout_produit", clear_on_submit=True):
        produit_ajout = st.text_input("Nom du produit")
        quantite_ajout = st.number_input("Quantité à ajouter", min_value=1, value=1)
        if st.form_submit_button("Ajouter au stock"):
            ok, msg = ajouter_produit(produit_ajout, quantite_ajout)
            if ok: st.success(msg) 
            else: st.error(msg)

    st.markdown("---")
    st.subheader("💸 Vendre un produit")
    df_stock_vente = obtenir_stock() # Obtenir les données fraîches pour ce formulaire
    if not df_stock_vente.empty:
        with st.form("vente_produit", clear_on_submit=True):
            produit_vente = st.selectbox("Produit à vendre", df_stock_vente['Produit'])
            quantite_vente = st.number_input("Quantité vendue", min_value=1, value=1)
            if st.form_submit_button("Vendre"):
                ok, msg = vendre_produit(produit_vente, quantite_vente)
                if ok: st.success(msg)
                else: st.error(msg)
    else:
        st.warning("Aucun produit en stock pour la vente.")

    st.markdown("---")
    st.subheader("🛒 Enregistrer un achat local (Réapprovisionnement)")
    df_stock_achat = obtenir_stock() # Obtenir les données fraîches pour ce formulaire
    if not df_stock_achat.empty:
        with st.form("achat_local", clear_on_submit=True):
            produit_achat = st.selectbox("Produit acheté", df_stock_achat['Produit'], key="sel_prod_ach")
            quantite_achat = st.number_input("Quantité achetée", min_value=1, value=1)
            montant_achat = st.number_input("Montant total (FCFA)", min_value=0.0, step=100.0)
            if st.form_submit_button("Enregistrer l'achat"):
                ok, msg = enregistrer_achat(produit_achat, quantite_achat, montant_achat)
                if ok: st.success(msg)
                else: st.error(msg)

elif menu == "Rapports":
    st.subheader("📄 Génération et envoi des rapports")
    
    col1, col2 = st.columns(2)

    with col1:
        st.info("Aperçu du Journal des Activités")
        st.dataframe(obtenir_journal().head(10), height=300)

    with col2:
        st.info("Aperçu de l'État du Stock")
        st.dataframe(obtenir_stock().head(10), height=300)

    st.markdown("---")

    if st.button("📧 Générer et Envoyer les 2 Rapports par Email"):
        with st.spinner("Génération des PDF et envoi de l'email..."):
            pdf_stock = generer_pdf_tableau(obtenir_stock(), titre="Rapport de Stock")
            pdf_journal = generer_pdf_tableau(obtenir_journal(), titre="Journal des Activites")
            
            destinataires = obtenir_destinataires()
            if envoyer_mail([pdf_stock, pdf_journal], destinataires, sujet="Rapports (Stock et Activités) - Le Noctambul"):
                st.success("Email avec les deux rapports envoyé avec succès !")
            else:
                st.error("L'envoi de l'email a échoué.")

    if st.button("📥 Générer et Télécharger les 2 Rapports (.zip)"):
        with st.spinner("Génération des PDF et création de l'archive ZIP..."):
            pdf_stock_path = generer_pdf_tableau(obtenir_stock(), titre="Rapport_Stock")
            pdf_journal_path = generer_pdf_tableau(obtenir_journal(), titre="Journal_Activites")
            
            zip_filename = f"rapports/Rapports_Le_Noctambul_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            
            with zipfile.ZipFile(zip_filename, 'w') as zipf:
                zipf.write(pdf_stock_path, os.path.basename(pdf_stock_path))
                zipf.write(pdf_journal_path, os.path.basename(pdf_journal_path))

            with open(zip_filename, "rb") as f:
                st.download_button(
                    label="✅ Télécharger le fichier ZIP",
                    data=f,
                    file_name=os.path.basename(zip_filename),
                    mime="application/zip"
                )

# La tâche automatique ne change pas
def check_and_send_auto_report():
    now = datetime.now()
    if now.hour in [0, 6] and now.minute < 2:
        lock_file_path = f"report_sent_{now.strftime('%Y-%m-%d_%H')}.lock"
        if not os.path.exists(lock_file_path):
            pdf_stock = generer_pdf_tableau(obtenir_stock(), titre="Rapport de Stock Automatique")
            pdf_journal = generer_pdf_tableau(obtenir_journal(), titre="Journal des Activites Automatique")
            destinataires = obtenir_destinataires()
            sujet = f"Rapports Automatiques du {now.strftime('%d/%m/%Y %H:%M')} - Le Noctambul"
            envoyer_mail([pdf_stock, pdf_journal], destinataires, sujet)
            # Create the lock file
            Path(lock_file_path).touch()

check_and_send_auto_report()