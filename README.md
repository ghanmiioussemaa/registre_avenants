# Registre des avenants — React + Flask (à partir de votre agent1)

Reprend votre dossier `agent1` (agent IA, règles métier, MySQL, `.env`) avec
un tableau de bord React + API Flask JSON à la place des templates Jinja.

## Corrections apportées dans cette version
- **Page "Contrats" blanche** : les montants MySQL de type DECIMAL
  (`premium_amount`) provoquaient une erreur de sérialisation JSON non
  interceptée → page 500 HTML → écran blanc côté React. Corrigé.
- Filet de sécurité ajouté côté API (toute erreur imprévue renvoie du JSON,
  jamais de page HTML brute) et côté React (ErrorBoundary : un bug affiche
  désormais un message au lieu d'un écran blanc).
- **PDF depuis la fiche contrat** : chaque ligne de l'historique des avenants
  est maintenant reliée à son rapport (nouvelle colonne `message_id` dans
  `avenant_history`), avec un bouton de téléchargement PDF.

## Si votre base de données existe déjà (contrats déjà en place)

Exécutez cette commande une seule fois pour ajouter la nouvelle colonne :
```sql
ALTER TABLE avenant_history ADD COLUMN message_id VARCHAR(255) AFTER validation_errors;
```
Sans ça, les avenants déjà enregistrés avant cette mise à jour n'auront pas
de PDF associé (normal — ils n'ont pas cette info), mais tout nouvel avenant
traité par l'agent en aura un.

## Démarrage

### 1. Backend (Flask API)
```bash
cd backend
python -m venv venv && source venv/bin/activate   # optionnel
pip install -r requirements.txt
python dashboard/dashboard_app.py
```
API sur **http://localhost:5050**

### 2. Frontend (React)
```bash
cd frontend
npm install
npm run dev
```
Interface sur **http://localhost:5173**.

## Build de production (un seul serveur, un seul port)
```bash
cd frontend && npm run build
cd ../backend && python dashboard/dashboard_app.py
```
Tout tourne alors sur **http://localhost:5050**.
