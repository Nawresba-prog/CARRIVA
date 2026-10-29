# CARRIVA

L'assistant intelligent qui vous aide à trouver un emploi, lancer une idée de projet et développer votre entreprise. Gratuit par défaut ; l'IA est facultative.

## Pour qui ?
- **Espace Candidat** : CV Europass, offres ciblées, compatibilité ATS, candidatures assistées, formations et certifications, profil LinkedIn, lancer son entreprise à 0 €.
- **Espace Entreprise** : identité de marque et site web, pages Facebook, messagerie clients (e-mail, WhatsApp, Messenger), spots publicitaires, retouche d'images, factures, stratégie / RSE.

6 langues : français, anglais, allemand, espagnol, italien, arabe.

## Lancer en local (Windows CMD)
```
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r backend\requirements.txt
copy .env.example .env
python -m uvicorn backend.app:app --port 8000
```
Puis ouvrez http://localhost:8000.

Dans `.env`, remplacez `JWT_SECRET`, `INTERNAL_SECRET` et `CERT_SECRET` par des textes aléatoires d'au moins 32 caractères, tous différents.

## Options (facultatives)
- IA : renseigner `ANTHROPIC_API_KEY` dans `.env`.
- Envoi réel d'e-mails : lancer `gmail-service` (Node, port 3001) et mettre `DRY_RUN=false`.
- Automatisations : `n8n/career_workflows.json` (import dans n8n), `docker-compose.yml`.

## Structure
- `backend/` : API FastAPI et agents (voir ARCHITECTURE.md)
- `frontend/` : application web (PWA)
- `mail-agent/`, `gmail-service/` : services Node
- `tests/` : tests automatiques

## Sécurité
Ne publiez jamais votre fichier `.env`. Il est ignoré par `.gitignore`.
