import streamlit as st
from streamlit_option_menu import option_menu
import mysql.connector
import pandas as pd
import hashlib
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import warnings
from decimal import Decimal

warnings.filterwarnings('ignore')

# Configuration de la page
st.set_page_config(
    page_title="BiblioStat Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personnalisé pour un design moderne
st.markdown("""
<style>
    .main {
        padding-top: 2rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        border: 1px solid #e0e0e0;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .metric-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 20px;
        border-radius: 15px;
        margin: 10px 0;
    }
    .sidebar .sidebar-content {
        background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
    }
    .stAlert {
        border-radius: 10px;
    }
    h1, h2, h3 {
        color: #2c3e50;
    }
    .book-card {
        background: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 10px 0;
        border-left: 4px solid #3498db;
    }
</style>
""", unsafe_allow_html=True)


# ================================= CONFIGURATION DATABASE ==========================================

def get_db_connection():
    """Connexion à la base de données avec gestion d'erreurs"""
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="biblio",
            charset='utf8mb4',
            autocommit=True
        )
        return connection
    except Exception as e:
        st.error(f"❌ Erreur de connexion DB: {str(e)}")
        return None


def hash_password(password):
    """Hachage sécurisé des mots de passe"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def convert_decimal(value):
    """Convertit les valeurs Decimal en int ou float"""
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    return value


def execute_query(query, params=None, fetch=True):
    """Exécute une requête SQL avec gestion des erreurs"""
    connection = get_db_connection()
    if not connection:
        return None

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, params or ())

        if fetch:
            result = cursor.fetchall()
            # Convertir les Decimal en types natifs Python
            for row in result:
                for key, value in row.items():
                    row[key] = convert_decimal(value)
            return result
        else:
            connection.commit()
            return True

    except Exception as e:
        st.error(f"❌ Erreur SQL: {str(e)}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


# ================================= AUTHENTIFICATION ==========================================

def init_session_state():
    """Initialisation de l'état de session"""
    defaults = {
        'authenticated': False,
        'username': None,
        'user_role': None,
        'user_email': None,
        'user_id': None,
        'last_activity': datetime.now()
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def authenticate_user(email, password):
    """Authentification des utilisateurs"""
    connection = get_db_connection()
    if not connection:
        return False, None, None, None

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        query = "SELECT ID_utilisateur, nom, prenom, password, role FROM utilisateurs WHERE mail = %s"
        cursor.execute(query, (email,))
        result = cursor.fetchone()

        if result:
            # Convertir les Decimal
            for key, value in result.items():
                result[key] = convert_decimal(value)

            stored_password = result['password']
            # Vérification du mot de passe
            if stored_password and (stored_password.startswith('$2b$') or stored_password == hash_password(password)):
                return True, f"{result['prenom']} {result['nom']}", result['role'], result['ID_utilisateur']

        return False, None, None, None

    except Exception as e:
        st.error(f"❌ Erreur d'authentification: {str(e)}")
        return False, None, None, None
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


# ================================= ANALYTICS AVANCÉS ==========================================

def get_advanced_analytics():
    """Analytics avancés"""
    metrics = {}

    try:
        # KPIs de base
        queries = {
            'total_books': "SELECT COUNT(*) as count FROM livres",
            'total_copies': "SELECT COALESCE(SUM(Quantite_disponible), 0) as count FROM livres",
            'total_users': "SELECT COUNT(*) as count FROM utilisateurs",
            'total_rentals': "SELECT COUNT(*) as count FROM locations",
            'active_rentals': "SELECT COUNT(*) as count FROM locations WHERE Statut NOT IN ('Retourné', 'Annulé')",
            'overdue_rentals': "SELECT COUNT(*) as count FROM locations WHERE Date_retour_prevue < CURDATE() AND Statut NOT IN ('Retourné', 'Annulé')"
        }

        for key, query in queries.items():
            result = execute_query(query)
            if result:
                metrics[key] = int(result[0]['count'])  # Convertir en int

        # Calculs de ratios
        if metrics.get('total_users', 0) > 0:
            metrics['rental_per_user'] = round(metrics.get('total_rentals', 0) / max(metrics.get('total_users', 1), 1),
                                               2)
            metrics['utilization_rate'] = round(
                (metrics.get('active_rentals', 0) / max(metrics.get('total_copies', 1), 1)) * 100, 2)

        # Top genres
        result = execute_query(
            "SELECT Genre, COUNT(*) as count FROM livres WHERE Genre IS NOT NULL GROUP BY Genre ORDER BY count DESC LIMIT 5")
        metrics['top_genres'] = result or []

        # Activité récente
        result = execute_query("""
            SELECT DATE(Date_location) as date, COUNT(*) as rentals 
            FROM locations 
            WHERE Date_location >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY DATE(Date_location) 
            ORDER BY date
        """)
        metrics['recent_activity'] = result or []

        # Livres les plus populaires
        result = execute_query("""
            SELECT l.Titre, l.Auteur, COUNT(loc.ID_location) as rental_count
            FROM livres l
            LEFT JOIN locations loc ON l.ID_livre = loc.ID_livre
            GROUP BY l.ID_livre, l.Titre, l.Auteur
            ORDER BY rental_count DESC
            LIMIT 5
        """)
        metrics['popular_books'] = result or []

        return metrics

    except Exception as e:
        st.error(f"❌ Erreur analytics: {str(e)}")
        return {}


# ================================= DASHBOARD AVANCÉ ==========================================

def advanced_dashboard():
    """Dashboard avec visualisations avancées"""
    st.markdown("# 📊 Analytics Dashboard - BiblioStat Intelligence")

    with st.spinner('🔄 Chargement des données...'):
        metrics = get_advanced_analytics()

    if not metrics:
        st.error("Impossible de charger les données")
        return

    # KPIs principaux - Conversion en int pour Streamlit
    st.markdown("## 🎯 Key Performance Indicators")
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        st.metric("📚 Total Livres", int(metrics.get('total_books', 0)))
    with col2:
        st.metric("📖 Exemplaires", int(metrics.get('total_copies', 0)))
    with col3:
        st.metric("👥 Utilisateurs", int(metrics.get('total_users', 0)))
    with col4:
        st.metric("📅 Locations", int(metrics.get('total_rentals', 0)))
    with col5:
        utilization = metrics.get('utilization_rate', 0)
        st.metric("📈 Taux Utilisation", f"{float(utilization):.1f}%")
    with col6:
        overdue = metrics.get('overdue_rentals', 0)
        st.metric("⚠️ Retards", int(overdue))

    # Visualisations
    col_left, col_right = st.columns(2)

    with col_left:
        if metrics.get('top_genres'):
            st.markdown("### 🎭 Distribution des Genres")
            df_genres = pd.DataFrame(metrics['top_genres'])
            # S'assurer que les valeurs sont numériques
            df_genres['count'] = df_genres['count'].astype(int)
            fig_donut = go.Figure(data=[go.Pie(
                labels=df_genres['Genre'], values=df_genres['count'], hole=0.4
            )])
            st.plotly_chart(fig_donut, use_container_width=True)

    with col_right:
        if metrics.get('recent_activity'):
            st.markdown("### 📈 Activité des 30 derniers jours")
            df_activity = pd.DataFrame(metrics['recent_activity'])
            df_activity['date'] = pd.to_datetime(df_activity['date'])
            df_activity['rentals'] = df_activity['rentals'].astype(int)
            fig_line = px.line(df_activity, x='date', y='rentals')
            st.plotly_chart(fig_line, use_container_width=True)

    # Livres populaires
    if metrics.get('popular_books'):
        st.markdown("### 🔥 Livres les Plus Populaires")
        df_popular = pd.DataFrame(metrics['popular_books'])
        df_popular['rental_count'] = df_popular['rental_count'].astype(int)
        st.dataframe(df_popular, use_container_width=True)


# ================================= GESTION DES LIVRES ==========================================

def get_unique_genres():
    """Récupère les genres uniques"""
    result = execute_query("SELECT DISTINCT Genre FROM livres WHERE Genre IS NOT NULL")
    return [row['Genre'] for row in result] if result else []


def book_management():
    """Gestion complète des livres"""
    st.markdown("# 📚 Gestion des Livres")

    # Onglets pour différentes fonctionnalités
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Catalogue", "➕ Ajouter Livre", "✏️ Modifier Livre", "📊 Statistiques"])

    with tab1:
        show_book_catalog()

    with tab2:
        add_book_form()

    with tab3:
        edit_book_form()

    with tab4:
        show_book_statistics()


def show_book_catalog():
    """Affiche le catalogue des livres"""
    st.markdown("## 📋 Catalogue des Livres")

    # Filtres
    col1, col2, col3 = st.columns(3)
    with col1:
        genre_filter = st.selectbox("Filtrer par genre", ["Tous"] + get_unique_genres())
    with col2:
        search_term = st.text_input("🔍 Rechercher un livre")
    with col3:
        disponibility_filter = st.selectbox("Disponibilité", ["Tous", "Disponible", "Indisponible"])

    # Construction de la requête
    query = "SELECT * FROM livres WHERE 1=1"
    params = []

    if genre_filter != "Tous":
        query += " AND Genre = %s"
        params.append(genre_filter)

    if search_term:
        query += " AND (Titre LIKE %s OR Auteur LIKE %s)"
        params.extend([f"%{search_term}%", f"%{search_term}%"])

    if disponibility_filter == "Disponible":
        query += " AND Quantite_disponible > 0"
    elif disponibility_filter == "Indisponible":
        query += " AND Quantite_disponible = 0"

    books = execute_query(query, params)

    if books:
        # Nettoyer les données Decimal
        for book in books:
            for key in ['ID_livre', 'Annee_publication', 'Quantite_disponible']:
                if key in book:
                    book[key] = convert_decimal(book[key])

        df = pd.DataFrame(books)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Aucun livre trouvé avec ces critères")


def add_book_form():
    """Formulaire d'ajout de livre"""
    st.markdown("## ➕ Ajouter un Nouveau Livre")

    with st.form("add_book_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            titre = st.text_input("Titre *", placeholder="Titre du livre")
            auteur = st.text_input("Auteur *", placeholder="Nom de l'auteur")
            annee = st.number_input("Année de publication", min_value=1000, max_value=datetime.now().year, value=2023)

        with col2:
            genre = st.text_input("Genre *", placeholder="Genre du livre")
            quantite = st.number_input("Quantité disponible *", min_value=0, value=1)
            infos = st.text_area("Informations supplémentaires", placeholder="Description, notes...")

        submitted = st.form_submit_button("✅ Ajouter le Livre", type="primary")

        if submitted:
            if not all([titre, auteur, genre, quantite is not None]):
                st.error("❌ Veuillez remplir tous les champs obligatoires (*)")
            else:
                query = """INSERT INTO livres (Titre, Auteur, Annee_publication, Genre, Quantite_disponible, Autres_informations) 
                         VALUES (%s, %s, %s, %s, %s, %s)"""
                success = execute_query(query, (titre, auteur, annee, genre, quantite, infos), fetch=False)
                if success:
                    st.success("✅ Livre ajouté avec succès!")
                    st.rerun()


def edit_book_form():
    """Formulaire de modification de livre"""
    st.markdown("## ✏️ Modifier un Livre")

    books = execute_query("SELECT * FROM livres")

    if not books:
        st.info("Aucun livre à modifier")
        return

    # Nettoyer les données Decimal
    for book in books:
        for key in ['ID_livre', 'Annee_publication', 'Quantite_disponible']:
            if key in book:
                book[key] = convert_decimal(book[key])

    book_titles = [f"{book['ID_livre']} - {book['Titre']} by {book['Auteur']}" for book in books]
    selected_book = st.selectbox("Sélectionner un livre à modifier", book_titles)

    if selected_book:
        book_id = int(selected_book.split(" - ")[0])
        book_result = execute_query("SELECT * FROM livres WHERE ID_livre = %s", (book_id,))

        if book_result:
            book = book_result[0]
            # Nettoyer les données Decimal
            for key in ['ID_livre', 'Annee_publication', 'Quantite_disponible']:
                if key in book:
                    book[key] = convert_decimal(book[key])

            with st.form("edit_book_form"):
                col1, col2 = st.columns(2)

                with col1:
                    titre = st.text_input("Titre", value=book['Titre'])
                    auteur = st.text_input("Auteur", value=book['Auteur'])
                    annee = st.number_input("Année",
                                            value=int(book['Annee_publication']) if book['Annee_publication'] else 2023)

                with col2:
                    genre = st.text_input("Genre", value=book['Genre'] or "")
                    quantite = st.number_input("Quantité", value=int(book['Quantite_disponible']) if book[
                        'Quantite_disponible'] else 0)
                    infos = st.text_area("Informations", value=book['Autres_informations'] or "")

                submitted = st.form_submit_button("💾 Sauvegarder les Modifications")

                if submitted:
                    query = """UPDATE livres SET Titre=%s, Auteur=%s, Annee_publication=%s, 
                             Genre=%s, Quantite_disponible=%s, Autres_informations=%s 
                             WHERE ID_livre=%s"""
                    success = execute_query(query, (titre, auteur, annee, genre, quantite, infos, book_id), fetch=False)
                    if success:
                        st.success("✅ Livre modifié avec succès!")


def show_book_statistics():
    """Affiche les statistiques des livres"""
    st.markdown("## 📊 Statistiques des Livres")

    # Statistiques par genre
    genre_stats = execute_query(
        "SELECT Genre, COUNT(*) as count, SUM(Quantite_disponible) as total FROM livres WHERE Genre IS NOT NULL GROUP BY Genre")

    if genre_stats:
        # Nettoyer les données Decimal
        for stat in genre_stats:
            for key in ['count', 'total']:
                if key in stat:
                    stat[key] = convert_decimal(stat[key])

        df_genre = pd.DataFrame(genre_stats)
        df_genre['count'] = df_genre['count'].astype(int)
        fig = px.bar(df_genre, x='Genre', y='count', title="Nombre de livres par genre")
        st.plotly_chart(fig, use_container_width=True)

    # Livres les plus empruntés
    popular_books = execute_query("""
        SELECT l.Titre, l.Auteur, COUNT(loc.ID_location) as rentals
        FROM livres l LEFT JOIN locations loc ON l.ID_livre = loc.ID_livre
        GROUP BY l.ID_livre, l.Titre, l.Auteur ORDER BY rentals DESC LIMIT 10
    """)

    if popular_books:
        # Nettoyer les données Decimal
        for book in popular_books:
            if 'rentals' in book:
                book['rentals'] = convert_decimal(book['rentals'])

        st.markdown("### 🔥 Livres les Plus Empruntés")
        df_popular = pd.DataFrame(popular_books)
        df_popular['rentals'] = df_popular['rentals'].astype(int)
        st.dataframe(df_popular, use_container_width=True)


# ================================= GESTION DES LOCATIONS ==========================================

def rental_management():
    """Gestion complète des locations"""
    st.markdown("# 📅 Gestion des Locations")

    tab1, tab2, tab3, tab4 = st.tabs(["📋 Locations Actuelles", "➕ Nouvelle Location", "🔄 Retour Livre", "📈 Historique"])

    with tab1:
        show_current_rentals()

    with tab2:
        create_new_rental()

    with tab3:
        return_book()

    with tab4:
        show_rental_history()


def show_current_rentals():
    """Affiche les locations en cours"""
    st.markdown("## 📋 Locations en Cours")

    rentals = execute_query("""
        SELECT loc.*, l.Titre, l.Auteur, u.nom, u.prenom 
        FROM locations loc
        JOIN livres l ON loc.ID_livre = l.ID_livre
        JOIN utilisateurs u ON loc.ID_etudiant = u.ID_utilisateur
        WHERE loc.Statut NOT IN ('Retourné', 'Annulé')
        ORDER BY loc.Date_retour_prevue
    """)

    if rentals:
        # Nettoyer les données Decimal
        for rental in rentals:
            for key in ['ID_location', 'ID_livre', 'ID_etudiant']:
                if key in rental:
                    rental[key] = convert_decimal(rental[key])

        df = pd.DataFrame(rentals)
        st.dataframe(df, use_container_width=True)

        # Alertes pour les retards
        overdue_count = len([r for r in rentals if r['Date_retour_prevue'] < datetime.now().date()])
        if overdue_count > 0:
            st.warning(f"⚠️ {overdue_count} location(s) en retard!")
    else:
        st.info("Aucune location en cours")


def create_new_rental():
    """Crée une nouvelle location"""
    st.markdown("## ➕ Nouvelle Location")

    # Récupérer les livres disponibles
    available_books = execute_query("SELECT * FROM livres WHERE Quantite_disponible > 0")
    # Récupérer les étudiants
    students = execute_query("SELECT * FROM utilisateurs WHERE role = 'Etudiant'")

    if not available_books:
        st.error("❌ Aucun livre disponible pour la location")
        return

    if not students:
        st.error("❌ Aucun étudiant enregistré")
        return

    # Nettoyer les données Decimal
    for book in available_books:
        for key in ['ID_livre', 'Quantite_disponible']:
            if key in book:
                book[key] = convert_decimal(book[key])

    for student in students:
        for key in ['ID_utilisateur']:
            if key in student:
                student[key] = convert_decimal(student[key])
        # S'assurer que les clés existent
        student.setdefault('prenom', '')
        student.setdefault('nom', '')

    with st.form("new_rental_form"):
        col1, col2 = st.columns(2)

        with col1:
            book_options = {f"{book['ID_livre']} - {book['Titre']}": book for book in available_books}
            selected_book_title = st.selectbox("Livre *", options=list(book_options.keys()))
            selected_book = book_options[selected_book_title]

            student_options = {
                f"{student['ID_utilisateur']} - {student.get('prenom', '')} {student.get('nom', '')}": student for
                student in students}
            selected_student_title = st.selectbox("Étudiant *", options=list(student_options.keys()))
            selected_student = student_options[selected_student_title]

        with col2:
            date_location = st.date_input("Date de location", value=datetime.now().date())
            date_retour = st.date_input("Date de retour prévue", value=datetime.now().date() + timedelta(days=14))
            statut = st.selectbox("Statut", ["En cours", "Confirmé", "En attente"])

        submitted = st.form_submit_button("✅ Créer la Location", type="primary")

        if submitted:
            # Vérifier la disponibilité
            if selected_book['Quantite_disponible'] <= 0:
                st.error("❌ Ce livre n'est plus disponible")
                return

            # Créer la location
            query = """INSERT INTO locations (ID_livre, ID_etudiant, Date_location, Date_retour_prevue, Statut) 
                     VALUES (%s, %s, %s, %s, %s)"""
            success1 = execute_query(query, (
                int(selected_book['ID_livre']),
                int(selected_student['ID_utilisateur']),
                date_location,
                date_retour,
                statut
            ), fetch=False)

            if success1:
                # Mettre à jour la quantité disponible
                update_query = "UPDATE livres SET Quantite_disponible = Quantite_disponible - 1 WHERE ID_livre = %s"
                success2 = execute_query(update_query, (int(selected_book['ID_livre']),), fetch=False)

                if success2:
                    st.success("✅ Location créée avec succès!")
                    st.rerun()


def return_book():
    """Gère le retour des livres"""
    st.markdown("## 🔄 Retour de Livre")

    # Récupérer les locations actives
    active_rentals = execute_query("""
        SELECT loc.*, l.Titre, u.nom, u.prenom 
        FROM locations loc
        JOIN livres l ON loc.ID_livre = l.ID_livre
        JOIN utilisateurs u ON loc.ID_etudiant = u.ID_utilisateur
        WHERE loc.Statut NOT IN ('Retourné', 'Annulé')
    """)

    if not active_rentals:
        st.info("Aucune location active")
        return

    # Nettoyer les données Decimal
    for rental in active_rentals:
        for key in ['ID_location', 'ID_livre', 'ID_etudiant']:
            if key in rental:
                rental[key] = convert_decimal(rental[key])
        rental.setdefault('prenom', '')
        rental.setdefault('nom', '')

    rental_options = {f"{r['ID_location']} - {r['Titre']} ({r.get('prenom', '')} {r.get('nom', '')})": r for r in
                      active_rentals}
    selected_rental_title = st.selectbox("Sélectionner une location à retourner", options=list(rental_options.keys()))
    selected_rental = rental_options[selected_rental_title]

    if selected_rental:
        st.info(
            f"**Livre:** {selected_rental['Titre']} | **Étudiant:** {selected_rental.get('prenom', '')} {selected_rental.get('nom', '')}")
        st.info(f"**Date de retour prévue:** {selected_rental['Date_retour_prevue']}")

        etat_retour = st.text_area("État du livre au retour", placeholder="Décrire l'état du livre...")

        if st.button("✅ Marquer comme Retourné", type="primary"):
            # Mettre à jour la location
            update_loc = "UPDATE locations SET Statut = 'Retourné' WHERE ID_location = %s"
            success1 = execute_query(update_loc, (int(selected_rental['ID_location']),), fetch=False)

            if success1:
                # Réapprovisionner le livre
                update_book = "UPDATE livres SET Quantite_disponible = Quantite_disponible + 1 WHERE ID_livre = %s"
                success2 = execute_query(update_book, (int(selected_rental['ID_livre']),), fetch=False)

                if success2:
                    st.success("✅ Livre retourné avec succès!")
                    st.rerun()


def show_rental_history():
    """Affiche l'historique des locations"""
    st.markdown("## 📈 Historique des Locations")

    # Filtres
    col1, col2 = st.columns(2)
    with col1:
        date_debut = st.date_input("Date de début", value=datetime.now().date() - timedelta(days=30))
    with col2:
        date_fin = st.date_input("Date de fin", value=datetime.now().date())

    history = execute_query("""
        SELECT loc.*, l.Titre, l.Auteur, u.nom, u.prenom 
        FROM locations loc
        JOIN livres l ON loc.ID_livre = l.ID_livre
        JOIN utilisateurs u ON loc.ID_etudiant = u.ID_utilisateur
        WHERE loc.Date_location BETWEEN %s AND %s
        ORDER BY loc.Date_location DESC
    """, (date_debut, date_fin))

    if history:
        # Nettoyer les données Decimal
        for item in history:
            for key in ['ID_location', 'ID_livre', 'ID_etudiant']:
                if key in item:
                    item[key] = convert_decimal(item[key])

        df = pd.DataFrame(history)
        st.dataframe(df, use_container_width=True)

        # Statistiques
        st.markdown("### 📊 Statistiques de la Période")
        col1, col2, col3 = st.columns(3)

        with col1:
            total_rentals = len(history)
            st.metric("Total Locations", total_rentals)

        with col2:
            returned = len([h for h in history if h['Statut'] == 'Retourné'])
            st.metric("Retournés", returned)

        with col3:
            active = len([h for h in history if h['Statut'] not in ['Retourné', 'Annulé']])
            st.metric("Actives", active)
    else:
        st.info("Aucune location trouvée pour cette période")


# ================================= GESTION DES UTILISATEURS ==========================================

def user_management():
    """Gestion complète des utilisateurs"""
    st.markdown("# 👥 Gestion des Utilisateurs")

    tab1, tab2, tab3 = st.tabs(["📋 Liste Utilisateurs", "➕ Ajouter Utilisateur", "📊 Statistiques"])

    with tab1:
        show_users_list()

    with tab2:
        add_user_form()

    with tab3:
        show_user_statistics()


def show_users_list():
    """Affiche la liste des utilisateurs"""
    st.markdown("## 📋 Liste des Utilisateurs")

    # Filtres
    col1, col2 = st.columns(2)
    with col1:
        role_filter = st.selectbox("Filtrer par rôle", ["Tous", "Admin", "Etudiant"])
    with col2:
        search_term = st.text_input("Rechercher un utilisateur")

    # Requête avec filtres
    query = "SELECT * FROM utilisateurs WHERE 1=1"
    params = []

    if role_filter != "Tous":
        query += " AND role = %s"
        params.append(role_filter)

    if search_term:
        query += " AND (nom LIKE %s OR prenom LIKE %s OR mail LIKE %s)"
        params.extend([f"%{search_term}%"] * 3)

    users = execute_query(query, params)

    if users:
        # Nettoyer les données Decimal
        for user in users:
            for key in ['ID_utilisateur']:
                if key in user:
                    user[key] = convert_decimal(user[key])
            # S'assurer que les clés existent
            user.setdefault('prenom', '')
            user.setdefault('nom', '')
            user.setdefault('mail', '')
            user.setdefault('role', '')

        df = pd.DataFrame(users)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Aucun utilisateur trouvé")


def add_user_form():
    """Formulaire d'ajout d'utilisateur"""
    st.markdown("## ➕ Ajouter un Nouvel Utilisateur")

    with st.form("add_user_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            nom = st.text_input("Nom *")
            prenom = st.text_input("Prénom *")
            mail = st.text_input("Email *")

        with col2:
            role = st.selectbox("Rôle *", ["Etudiant", "Admin"])
            password = st.text_input("Mot de passe *", type="password")
            confirm_password = st.text_input("Confirmer le mot de passe *", type="password")

        submitted = st.form_submit_button("✅ Créer l'Utilisateur", type="primary")

        if submitted:
            # Validation
            errors = []
            if not all([nom, prenom, mail, password]):
                errors.append("Tous les champs obligatoires doivent être remplis")
            if len(password) < 8:
                errors.append("Le mot de passe doit contenir au moins 8 caractères")
            if password != confirm_password:
                errors.append("Les mots de passe ne correspondent pas")

            if errors:
                for error in errors:
                    st.error(f"❌ {error}")
            else:
                # Vérifier l'email unique
                existing_user = execute_query("SELECT COUNT(*) as count FROM utilisateurs WHERE mail = %s", (mail,))
                if existing_user and existing_user[0]['count'] > 0:
                    st.error("❌ Un utilisateur avec cet email existe déjà")
                else:
                    hashed_pwd = hash_password(password)
                    query = """INSERT INTO utilisateurs (nom, prenom, mail, password, role) 
                             VALUES (%s, %s, %s, %s, %s)"""
                    success = execute_query(query, (nom, prenom, mail, hashed_pwd, role), fetch=False)
                    if success:
                        st.success("✅ Utilisateur créé avec succès!")
                        st.rerun()


def show_user_statistics():
    """Affiche les statistiques des utilisateurs"""
    st.markdown("## 📊 Statistiques des Utilisateurs")

    # Répartition par rôle
    role_stats = execute_query("SELECT role, COUNT(*) as count FROM utilisateurs GROUP BY role")

    if role_stats:
        # Nettoyer les données Decimal
        for stat in role_stats:
            if 'count' in stat:
                stat['count'] = convert_decimal(stat['count'])

        df_roles = pd.DataFrame(role_stats)
        df_roles['count'] = df_roles['count'].astype(int)
        fig = px.pie(df_roles, values='count', names='role', title="Répartition des utilisateurs par rôle")
        st.plotly_chart(fig, use_container_width=True)

    # Utilisateurs les plus actifs
    active_users = execute_query("""
        SELECT u.nom, u.prenom, u.role, COUNT(l.ID_location) as rental_count
        FROM utilisateurs u
        LEFT JOIN locations l ON u.ID_utilisateur = l.ID_etudiant
        WHERE u.role = 'Etudiant'
        GROUP BY u.ID_utilisateur, u.nom, u.prenom, u.role
        ORDER BY rental_count DESC
        LIMIT 10
    """)

    if active_users:
        # Nettoyer les données Decimal
        for user in active_users:
            if 'rental_count' in user:
                user['rental_count'] = convert_decimal(user['rental_count'])

        st.markdown("### 🏆 Utilisateurs les Plus Actifs")
        df_active = pd.DataFrame(active_users)
        df_active['rental_count'] = df_active['rental_count'].astype(int)
        st.dataframe(df_active, use_container_width=True)


# ================================= RAPPORTS AVANCÉS ==========================================

def advanced_reports():
    """Module de rapports avancés"""
    st.markdown("# 📊 Rapports Avancés")

    tab1, tab2 = st.tabs(["📈 Rapport Complet", "🔍 Analyse Avancée"])

    with tab1:
        generate_comprehensive_report()

    with tab2:
        advanced_analysis()


def generate_comprehensive_report():
    """Génère un rapport complet"""
    st.markdown("## 📈 Rapport Complet de la Bibliothèque")

    # Métriques principales
    col1, col2, col3, col4 = st.columns(4)

    total_books = execute_query("SELECT COUNT(*) as total FROM livres")
    total_users = execute_query("SELECT COUNT(*) as total FROM utilisateurs")
    total_rentals = execute_query("SELECT COUNT(*) as total FROM locations")
    active_rentals = execute_query(
        "SELECT COUNT(*) as active FROM locations WHERE Statut NOT IN ('Retourné', 'Annulé')")

    with col1:
        st.metric("Total Livres", int(total_books[0]['total']) if total_books else 0)
    with col2:
        st.metric("Total Utilisateurs", int(total_users[0]['total']) if total_users else 0)
    with col3:
        st.metric("Total Locations", int(total_rentals[0]['total']) if total_rentals else 0)
    with col4:
        st.metric("Locations Actives", int(active_rentals[0]['active']) if active_rentals else 0)

    # Graphiques
    col_left, col_right = st.columns(2)

    with col_left:
        # Évolution mensuelle des locations
        monthly_data = execute_query("""
            SELECT DATE_FORMAT(Date_location, '%Y-%m') as mois, COUNT(*) as locations
            FROM locations 
            GROUP BY mois 
            ORDER BY mois
        """)

        if monthly_data:
            # Nettoyer les données Decimal
            for data in monthly_data:
                if 'locations' in data:
                    data['locations'] = convert_decimal(data['locations'])

            df_monthly = pd.DataFrame(monthly_data)
            df_monthly['locations'] = df_monthly['locations'].astype(int)
            fig = px.line(df_monthly, x='mois', y='locations', title="Évolution Mensuelle des Locations")
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        # Top 5 des auteurs les plus empruntés
        top_authors = execute_query("""
            SELECT l.Auteur, COUNT(loc.ID_location) as locations
            FROM livres l
            JOIN locations loc ON l.ID_livre = loc.ID_livre
            GROUP BY l.Auteur
            ORDER BY locations DESC
            LIMIT 5
        """)

        if top_authors:
            # Nettoyer les données Decimal
            for author in top_authors:
                if 'locations' in author:
                    author['locations'] = convert_decimal(author['locations'])

            df_authors = pd.DataFrame(top_authors)
            df_authors['locations'] = df_authors['locations'].astype(int)
            fig = px.bar(df_authors, x='Auteur', y='locations', title="Auteurs les Plus Populaires")
            st.plotly_chart(fig, use_container_width=True)


def advanced_analysis():
    """Analyse avancée des données"""
    st.markdown("## 🔍 Analyse Avancée")

    # Analyse des retards
    st.markdown("### ⚠️ Analyse des Retards")

    retards = execute_query("""
        SELECT u.nom, u.prenom, l.Titre, loc.Date_retour_prevue,
               DATEDIFF(CURDATE(), loc.Date_retour_prevue) as jours_retard
        FROM locations loc
        JOIN livres l ON loc.ID_livre = l.ID_livre
        JOIN utilisateurs u ON loc.ID_etudiant = u.ID_utilisateur
        WHERE loc.Date_retour_prevue < CURDATE() 
        AND loc.Statut NOT IN ('Retourné', 'Annulé')
        ORDER BY jours_retard DESC
    """)

    if retards:
        # Nettoyer les données Decimal
        for retard in retards:
            if 'jours_retard' in retard:
                retard['jours_retard'] = convert_decimal(retard['jours_retard'])

        df_retards = pd.DataFrame(retards)
        st.dataframe(df_retards, use_container_width=True)

        # Statistiques des retards
        if not df_retards.empty:
            retard_moyen = df_retards['jours_retard'].mean()
            st.metric("📅 Retard Moyen", f"{float(retard_moyen):.1f} jours")
    else:
        st.info("Aucun retard actuellement")


# ================================= APPLICATION PRINCIPALE ==========================================

def main():
    """Application principale"""
    init_session_state()

    # En-tête
    st.markdown("""
    <div style="text-align: center; padding: 2rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; margin-bottom: 2rem;">
        <h1 style="color: white; margin: 0;">📊 BiblioStat Analytics Platform</h1>
        <p style="color: #f8f9fa; margin: 0.5rem 0 0 0;">Système Complet de Gestion de Bibliothèque</p>
    </div>
    """, unsafe_allow_html=True)

    # Authentification
    if not st.session_state.authenticated:
        show_login_interface()
    else:
        show_main_application()


def show_login_interface():
    """Interface de connexion"""
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("### 🔐 Authentification")

        with st.form("login_form"):
            email = st.text_input("📧 Email", placeholder="votre.email@exemple.com")
            password = st.text_input("🔒 Mot de passe", type="password", placeholder="Votre mot de passe")

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                login_btn = st.form_submit_button("🚀 Se connecter", type="primary")
            with col_btn2:
                demo_btn = st.form_submit_button("🎯 Mode Démo")

            if login_btn and email and password:
                authenticated, name, role, user_id = authenticate_user(email, password)
                if authenticated:
                    st.session_state.update({
                        'authenticated': True,
                        'username': name,
                        'user_role': role,
                        'user_email': email,
                        'user_id': user_id
                    })
                    st.success(f"✅ Connexion réussie! Bienvenue {name}")
                    st.rerun()
                else:
                    st.error("❌ Identifiants incorrects")

            if demo_btn:
                st.session_state.update({
                    'authenticated': True,
                    'username': "Utilisateur Démo",
                    'user_role': "Admin",
                    'user_email': "demo@bibliostat.com"
                })
                st.rerun()

        # Comptes de test
        with st.expander("💡 Comptes de test disponibles"):
            st.markdown("""
            **Administrateurs:**
            - merlin@gmail.com | password123
            - fabricestat@gmail.com | password123  

            **Étudiant:**
            - paul@gmail.com | password123
            """)


def show_main_application():
    """Application principale après connexion"""
    # Sidebar
    with st.sidebar:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%); 
                    padding: 1rem; border-radius: 10px; color: white; text-align: center;">
            <h3 style="margin: 0;">👤 {st.session_state.username}</h3>
            <p style="margin: 0.5rem 0 0 0;">🎯 {st.session_state.user_role}</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        # Navigation
        menu_options = [
            "📊 Analytics Dashboard",
            "📚 Gestion des Livres",
            "📅 Gestion des Locations",
            "👥 Gestion des Utilisateurs",
            "📈 Rapports Avancés"
        ]

        selected = option_menu(
            menu_title="📋 Navigation Principale",
            options=menu_options,
            icons=["graph-up", "book", "calendar-check", "people", "bar-chart"],
            default_index=0,
            styles={
                "container": {"padding": "0!important"},
                "nav-link": {"font-size": "14px", "--hover-color": "#e3e3e3"},
                "nav-link-selected": {"background-color": "#3498db"},
            }
        )

        st.markdown("---")

        if st.button("🚪 Déconnexion", type="secondary"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    # Routage des pages
    if selected == "📊 Analytics Dashboard":
        advanced_dashboard()
    elif selected == "📚 Gestion des Livres":
        book_management()
    elif selected == "📅 Gestion des Locations":
        rental_management()
    elif selected == "👥 Gestion des Utilisateurs":
        user_management()
    elif selected == "📈 Rapports Avancés":
        advanced_reports()


if __name__ == "__main__":
    main()