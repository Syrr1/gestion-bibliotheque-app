CREATE TABLE Utilisateurs (
    ID_utilisateur INT PRIMARY KEY AUTO_INCREMENT,
    Nom VARCHAR(50),
    Prenom VARCHAR(50),
    Nom_utilisateur VARCHAR(50),
    password VARCHAR(255),
    Role ENUM('Etudiant', 'Admin'),  
    mail TEXT
);


CREATE TABLE Livres (
    ID_livre INT PRIMARY KEY AUTO_INCREMENT,
    Titre VARCHAR(100),
    Auteur VARCHAR(100),
    Annee_publication INT,
    Genre VARCHAR(50),
    Quantite_disponible INT,
    Autres_informations TEXT
);


CREATE TABLE Etudiants (
    ID_etudiant INT PRIMARY KEY AUTO_INCREMENT,
    Nom VARCHAR(50),
    Prenom VARCHAR(50),
    Autres_informations TEXT
);


CREATE TABLE Administrateurs (
    ID_admin INT PRIMARY KEY AUTO_INCREMENT,
    Nom VARCHAR(50),
    Prenom VARCHAR(50),
    Autres_informations TEXT
);

CREATE TABLE Locations (
    ID_location INT PRIMARY KEY AUTO_INCREMENT,
    ID_livre INT,
    ID_etudiant INT,
    Date_location DATE,
    Date_retour_prevue DATE,
    Statut VARCHAR(50),
    FOREIGN KEY (ID_livre) REFERENCES Livres(ID_livre),
    FOREIGN KEY (ID_etudiant) REFERENCES Etudiants(ID_etudiant)
);
