# CARRIVA — Agent IA d'entreprise (architecture & plan technique)

Pipeline imposé :
**User → AI Agent → RAG → Tools → Enterprise API → Human Approval → Action → Monitoring**

---

## 1. Architecture du système & workflow multi-agents

```
┌────────┐   ┌──────────────┐   ┌──────────┐   ┌────────┐   ┌────────────────┐
│ User   │──▶│ Orchestrator │──▶│   RAG    │──▶│ Tools  │──▶│ Enterprise API │
│ (UI)   │   │ (AI Agent)   │   │ (Qdrant) │   │        │   │ jobs/PDF/Gmail │
└────────┘   └──────┬───────┘   └──────────┘   └────────┘   └───────┬────────┘
     ▲              │                                               │
     │              ▼                                               ▼
     │      ┌───────────────┐   approve    ┌────────┐        ┌────────────┐
     └──────│ Approval Gate │─────────────▶│ Action │───────▶│ Monitoring │
   notif.   │ (Human, RBAC) │   reject→stop│ (send) │        │ Prom/Lang- │
            └───────────────┘              └────────┘        │ Smith/Logs │
                                                             └────────────┘
```

### Agents spécialisés

| Agent | Rôle | Entrées → Sorties | Outils |
|---|---|---|---|
| **Orchestrator** | Route la demande, maintient l'état de session, applique les politiques | requête UI → plan d'exécution | tous (via registre) |
| **CV Parser/Builder Agent** | Structure le formulaire, produit un CV Europass (JSON + HTML/PDF), détecte les lacunes | formulaire → CV structuré | `build_europass_cv`, `extract_skills` |
| **RAG Retrieval Agent** | Recherche sémantique dans offres et formations | profil → top-k documents | `search_jobs`, `search_trainings` |
| **Job Matcher Agent** | Score de matching (similarité vectorielle + filtres ville/pays + re-ranking LLM) | CV + filtres → offres classées | `search_jobs`, `rerank` |
| **Training Advisor Agent** | Compare compétences du CV vs. compétences requises → formations | gaps → formations | `search_trainings`, `issue_certificate` |
| **Email Dispatcher Agent** | Rédige et traduit l'e-mail de candidature (langue officielle du pays), **prépare** l'envoi | CV + offre → brouillon | `draft_application_email`, `send_email` (**gated**) |
| **Approval Gate** | Suspend l'exécution tant qu'un humain n'a pas validé | brouillon → décision | — |

Principe : un agent **propose**, jamais n'exécute seul une action à effet externe irréversible.

**Implémentation (backend/agent.py)** : graphe LangGraph `draft → approval_gate → send`. Le noeud `approval_gate` appelle `interrupt()` : l'exécution est suspendue et l'état persisté par le checkpointer (`MemorySaver` en prototype, `PostgresSaver` en production). Elle reprend uniquement via `Command(resume=...)` depuis `POST /approvals/{id}/decision`. Le noeud `send` revérifie le hash du contenu approuvé.

---

## 2. RAG & base vectorielle

- **Store** : Qdrant (collections `jobs`, `trainings`, `cv_profiles`). Mode `:memory:` pour le prototype, cluster managé en production.
- **Chunking**
  - Offres : 1 offre = 1 chunk « sémantique » (titre + missions + compétences) ≤ 512 tokens ; si plus long, découpage par section (missions / profil / avantages) avec 64 tokens de chevauchement.
  - Formations : 1 formation = 1 chunk (intitulé, objectifs, prérequis, compétences visées, certification).
  - CV : un chunk par bloc (expérience, formation, compétences).
- **Embeddings** : modèle multilingue (ex. `text-embedding-3-large` ou `multilingual-e5-large`) afin de matcher un CV français avec une offre allemande. Fallback local de hash dans le prototype.
- **Payload indexé** (filtrage) : `country`, `city`, `language`, `seniority`, `source`, `posted_at`, `expires_at`, `hash`.
- **Indexation dynamique** : upsert idempotent (id = hash(source+url)) déclenché par n8n ; TTL via `expires_at` + purge nocturne.
- **Appariement par compétences** (`backend/matching.py`) : extraction de compétences canoniques (taxonomie FR/EN/AR) du CV, des offres et des formations ; Qdrant fournit les candidats, puis re-classement par couverture de compétences (+ intitulé) avec explication (compétences communes / manquantes). Les lacunes viennent des 2 offres les plus proches du profil et pilotent les formations. Catalogue de démo : `backend/seed_data.py` (28 offres, 24 formations).
- **Recherche** (implémentée) : hybride, vecteurs nommés `dense` + `sparse`, deux `Prefetch` (top-20, filtres pays/ville) fusionnés par RRF. Le sparse du prototype est un hachage de termes (à remplacer par BM25/SPLADE) ; re-ranking LLM sur le top-20 prévu.

---

### Traitement des données saisies (`backend/processing.py`)

La saisie n'est **jamais** recopiée telle quelle dans le CV ni dans l'e-mail : `process_cv` (déterministe, idempotent) nettoie (HTML/scripts, espaces, ponctuation), met en forme (noms, villes, pays, e-mail), normalise le téléphone au format international, l'URL, les **dates** (« mars 2021 », « 03/2021 », « en cours »), dédoublonne et corrige l'écriture des **compétences** (python → Python, SQL, CI/CD), transforme les descriptions en **puces**, reconnaît les **langues** (langue maternelle vs niveaux CECR, « courant » → C1), trie les expériences/formations (récent d'abord) et corrige les dates inversées. Un résumé n'est généré que si l'utilisateur n'en fournit pas, **uniquement à partir de faits fournis** (dernier intitulé, années calculées, compétences) : aucune expérience, aucun employeur ni chiffre n'est inventé. `POST /cv` renvoie le rapport des modifications, affiché à l'utilisateur. Option `CV_LLM_REFINE=true` : reformulation LLM du résumé/des activités, sortie rejetée si elle contient un chiffre absent de la source (garde-fou anti-invention) ; les données du CV sont transmises comme *données*, jamais comme instructions. Tailles de saisie bornées côté API (2000 caractères / champ, 30 éléments / liste).

## 3. Outils & APIs d'entreprise

| Tool | Description | API cible | Classe de risque |
|---|---|---|---|
| `build_europass_cv(cv)` | Normalise le CV au schéma Europass, génère HTML/PDF | moteur PDF interne | faible |
| `search_jobs(query, country, city, k)` | Recherche RAG d'offres | Qdrant | faible |
| `search_trainings(gaps, k)` | Formations pertinentes | Qdrant | faible |
| `issue_certificate(user, training)` | Attestation PDF signée HMAC-SHA256, vérifiable via `GET /certificates/verify/{id}`; exige une fin de formation enregistrée | `pdf_gen.py` | moyen |
| `cv_pdf` (`POST /cv/pdf?lang=`) | CV au **modèle Europass** (identité, expériences multiples, formations avec niveau CEC, langues maternelles + tableau CECR écouter/lire/interaction/production/écrit, compétences numériques, permis, infos complémentaires), en fr/en/de/it/es/ar (miroir RTL pour l'arabe), joint à l'e-mail dans la langue de l'offre | ReportLab | faible |

**Arabe dans les PDF** : `arabic-reshaper` (liaison des lettres) + `python-bidi` (ordre visuel RTL) + police Noto Sans Arabic (`python backend/fonts/fetch_fonts.py`, licence OFL). Le retour à la ligne est calculé en ordre logique avant l'inversion bidi, et l'alignement passe à droite. Les e-mails vers les pays arabophones (MA, DZ, TN, EG, SA, AE…) sont rédigés en arabe.
| `draft_application_email(cv, job)` | Rédige/traduit le mail | LLM | faible |
| `send_email(draft_id)` | **Envoi Gmail** via service Node.js (OAuth2) | Gmail API | **critique → Approval Gate** |

Chaque tool a un schéma Pydantic d'entrée, un timeout, un retry exponentiel et un log d'audit.

---

## 4. Automatisation n8n (voir `n8n/career_workflows.json`)

1. **WF-1 Ingestion des offres** : Cron (toutes les 6 h) → HTTP (API emploi : France Travail, Adzuna, Jooble…) → normalisation/dédoublonnage → `POST /internal/jobs/index`.
2. **WF-2 Alertes de matching** : Cron (quotidien) → `POST /internal/matching/run` → pour chaque nouveau match > seuil → notification (mail/Slack) à l'utilisateur.
3. **WF-3 Suivi des candidatures** : Webhook `application-status` (appelé par le backend après envoi) → mise à jour statut (`sent`, `opened`, `reply`, `rejected`) → relance J+7 proposée (soumise elle aussi à approbation).

n8n gère l'asynchronisme ; le backend reste l'unique source de vérité (n8n n'a aucun accès direct à Gmail ni aux données CV).

---

## 5. Human-in-the-Loop (Approval Gate)

- `POST /apply` ne **fait jamais** d'envoi : il crée une `ApprovalRequest` (`status=pending`) contenant destinataire, objet, corps traduit, pièce jointe, hash du contenu.
- L'utilisateur (ou un approbateur désigné en contexte entreprise) voit le brouillon complet, peut l'éditer, puis `approve` / `reject`.
- Seul l'endpoint `POST /approvals/{id}/decision` (rôle `approver`, authentifié) déclenche `send_email`.
- Garde-fous : le contenu envoyé doit avoir le même hash que le contenu approuvé (anti-TOCTOU) ; une approbation est à usage unique et expire (24 h) ; tout est journalisé (qui, quand, quoi).

---

## 6. Sécurité & RBAC

- **Rôles** : `candidate` (CV, recherche, demander une candidature), `approver` (valider/refuser), `admin` (indexation, monitoring). Moindre privilège par route (dépendance FastAPI) et par outil (liste blanche par rôle).
- **Authentification** : OIDC / JWT court (15 min) + refresh ; secrets en gestionnaire (Vault / Secret Manager), jamais dans le code.
- **Gmail** : scope minimal `gmail.send` uniquement ; refresh token chiffré ; service Node isolé, accessible seulement avec un secret inter-service (mTLS en production).
- **Chiffrement** : TLS 1.2+ en transit ; AES-256 au repos (disque Qdrant/Postgres, CV chiffrés avec clé par utilisateur via KMS).
- **RGPD** : base légale = consentement explicite, minimisation, droit d'accès/effacement (`DELETE /me`), rétention limitée (CV 12 mois), registre de traitements, DPA avec les sous-traitants LLM, hébergement UE, pseudonymisation dans les logs.
- **Sécurité LLM** : séparation données/instructions (le contenu des offres scrappées est traité comme *non fiable* — défense contre le prompt injection), validation de sortie par schéma, aucun tool critique appelable sans approbation, limites de débit.

---

## 7. Tests, monitoring & observabilité

- **Traçage LLM** : LangSmith (tokens, latence par étape, erreurs d'outils) via `LANGCHAIN_TRACING_V2=true`.
- **Métriques** : Prometheus (`/metrics`) — latence HTTP, appels d'outils par statut, approbations en attente, envois réussis/échoués ; dashboards Grafana + alertes (taux d'erreur outils > 5 %, p95 > 3 s).
- **Logs** : JSON structuré, corrélation par `request_id`, PII masquée.
- **Tests** : unitaires (schémas, scoring), contrat (APIs externes mockées), E2E (CV → matching → brouillon → approbation → envoi sandbox), jeux d'évaluation RAG (recall@k, MRR), tests de sécurité (prompt injection, accès inter-rôles).
- **Prototype** : voir `backend/app.py` (FastAPI + Qdrant + registre de tools + Approval Gate + Prometheus), `gmail-service/server.js`, `frontend/index.html`.

---

## Lancer le prototype

```bash
cd career
cp .env.example .env
docker compose up qdrant -d           # optionnel (sinon Qdrant en mémoire)
pip install -r backend/requirements.txt
python backend/fonts/fetch_fonts.py    # police Noto Sans Arabic (PDF en arabe)
uvicorn backend.app:app --reload      # API  : http://localhost:8000
cd gmail-service && npm i && node server.js   # service Gmail : :3001
# ouvrir frontend/index.html (ou servi par FastAPI sur /)
```

## Traitement IA du CV
Le résumé et les « Activités et responsabilités principales » sont reformulés par un LLM (`processing.maybe_refine`) lorsque `ANTHROPIC_API_KEY` est défini (`CV_LLM_REFINE=auto`). La saisie est traitée comme une donnée ; toute sortie contenant un chiffre, un lien ou un e-mail absent de la source, ou une structure inattendue, est rejetée et la version déterministe est conservée. Le nom de l’établissement est toujours normalisé en majuscules.

## Agent e-mail autonome (mail-agent/)
Agent Node.js mono-fichier : recherche DuckDuckGo -> analyse des sites -> IA (Anthropic/Mistral/Ollama) -> brouillon de candidature dans la langue du site -> envoi Gmail avec CV PDF. Garde-fous : DRY_RUN par défaut, envoi uniquement pour les pistes cochées, adresses réellement trouvées sur le site, un envoi par entreprise, plafonds par lot/jour, pauses aléatoires, liste STOP, chiffres inventés rejetés, panneau lié à 127.0.0.1. Lancement : `cd mail-agent && npm i && node agent.js`.

## Compatibilité ATS (bouton 3 de l'Espace Candidat)
Panneau `#p-ats` dans `frontend/index.html` : moteur 100 % navigateur (objet `ATS` : `analyze` = correspondance lexicale CV/offre, compétence technique poids 3, terme poids 1 ; `audit` = alertes de format : chiffres, formulations vagues, sections, contact, longueur, mise en forme). Aucun texte n'est envoyé au serveur. Le bouton « Copier le prompt » génère un prompt Claude (6 langues) qui interdit toute invention.
Fichier de modèles de CV : `frontend/cv-templates.js` (servi par `/cv-templates.js`) — et non à la racine du projet.

## Photo facultative et arabe (CV)
- Photo : choisie dans « Création de CV Europass » (appli principale) et dans la galerie de l'agent mail. Le navigateur recadre en portrait 4:5 et améliore exposition/contraste/netteté (local). L'analyse par IA (`POST /cv/photo/check`, `backend/photo_ai.py`) n'a lieu que sur clic, après confirmation, et ne fait ni identification ni déduction sur la personne.
- Arabe : les 6 modèles et Europass gèrent l'arabe (RTL). Il faut la police Noto Sans Arabic : `python backend/fonts/fetch_fonts.py` (servie par `/fonts/{nom}`). Sans elle, un message explicite s'affiche.

## Routes n8n (WF-2 et WF-3) — `backend/alerts.py`, `backend/followup.py`
Toutes protégées par l'en-tête `x-internal-secret` (comparaison en temps constant).
- `POST /jobs/alerts` (utilisateur, consentement obligatoire), `GET`/`DELETE /jobs/alerts` : abonnement aux alertes. Seul un profil dérivé est conservé (compétences canoniques, intitulés, pays/ville, seuil, e-mail de notification), pas le CV.
- `POST /internal/matching/run` (WF-2) : corps facultatif `{max_per_user, dry_run}`. Réponse : tableau plat, une ligne par nouvelle correspondance `{user, email, lang, title, company, url, score, matched, missing, message}` (n8n le découpe en éléments). Une offre n'est jamais signalée deux fois à un même abonné. `score ≥ min_score` de l'abonné (0,6 par défaut).
- `POST /internal/applications/status` : `{approval_id, status: opened|reply|rejected|withdrawn}`. `reply`/`rejected`/`withdrawn` stoppent toute relance.
- `POST /internal/followup/propose` (WF-3, J+7) : `{approval_id}`. Crée une **demande d'approbation** de relance (rien n'est envoyé) : texte déterministe fondé sur la candidature d'origine, sans pièce jointe, une seule relance (une nouvelle si la précédente a expiré). Réponse `{proposed: true, approval_id, to, subject, requester}` ou `{proposed: false, reason: not_sent|no_email|reply_received|already_proposed|too_early, eligible_at}`. La relance apparaît dans `GET /approvals` (`kind: "followup"`) et suit la même validation humaine que les candidatures.
- Après un envoi réussi, le backend appelle `N8N_WEBHOOK_URL` (au mieux, en arrière-plan) pour lancer WF-3.
Limite : la détection automatique des réponses (lecture de la boîte Gmail) n'existe pas ; c'est n8n ou un autre système qui appelle `/internal/applications/status`.
Test de fumée sans dépendances : `python tests/n8n_routes_smoke.py`.

## Plateforme de formation (LMS) — `backend/lms.py`
Moodle via Web Services REST (`core_user_get_users_by_field`, `core_user_create_users`, `enrol_manual_enrol_users`, `core_completion_get_course_completion_status`). Activation : `MOODLE_URL` (https) + `MOODLE_TOKEN` dans `.env`. Les cours hébergés se déclarent dans `backend/lms_courses.json` (modèle : `lms_courses.example.json`) et rejoignent le catalogue/les recommandations.
- `GET /lms/status`, `POST /trainings/enroll` (inscription + lien d'accès), `POST /trainings/complete` (**vérifie auprès du LMS**, 409 tant que le cours n'est pas terminé), `POST /internal/lms/webhook` (événement signé `x-lms-signature: sha256=HMAC(LMS_WEBHOOK_SECRET, corps)`, JSON `{"event":"course_completed","user_email","course_id"}` ou instruction xAPI `completed`/`passed`).
- Attestations : `GET /certificates/verify/{id}` indique l'origine de la complétion (`lms` vérifiée, `internal`, `declared`). En production (`ENV != dev`), les cours de fournisseurs externes ne peuvent plus être auto-déclarés : pas d'attestation pour eux.
- Limite : l'intégration est testée avec un Moodle simulé (aucun Moodle réel n'était disponible) ; à valider sur votre instance (jeton limité aux fonctions listées, achèvement activé dans chaque cours).

## Vérification des liens de formation
`python -m backend.check_links --only-bad [--json rapport.json]` (machine avec Internet) : ok / redirige / bloqué / page_vide / mort / erreur / injoignable.

## Attestations : cachet et envoi par e-mail
- **Cachet** (`pdf_gen._seal`) : cachet circulaire « CARRIVA » à double anneau, avec date et code court de la signature HMAC. Bleu « COMPLETION VERIFIED » seulement si la fin de formation a été confirmée (plateforme LMS ou appel interne signé) ; gris « NOT VERIFIED • DEMO » pour une auto-déclaration. Le QR code et la signature restent vérifiables via `/certificates/verify/{id}` (champ `verified`).
- **E-mail** (`backend/cert_mail.py`) : `POST /certificates` accepte `email` ; l'attestation PDF est envoyée à l'utilisateur dans sa langue (cours de la plateforme : à l'adresse du compte inscrit, qui prime). Texte fixe, destinataire unique, limites 5 envois/heure/utilisateur et 3/jour/attestation. L'envoi n'est **pas** soumis à l'Approval Gate (c'est le document de l'utilisateur, à sa demande) ; un échec n'empêche jamais le téléchargement (en-tête `x-certificate-email` : sent | failed | limited | skipped). Nécessite le service Gmail (`GMAIL_SERVICE_URL`, `DRY_RUN=false` pour un envoi réel).

## Design des attestations (par formation)
`backend/cert_design.py` : A4 paysage, bandeau coloré + motif + icône + libellé du domaine. `theme_for(formation)` choisit l'un des 10 thèmes
(langues, web, projet, marketing, data/IA, cloud, sécurité, gestion/finance, design, général) via la catégorie du catalogue puis un vote sur les
compétences. Le motif varie selon le titre. Arabe : mise en page en miroir. `pdf_gen.certificate_pdf` accepte un titre ou la fiche complète
(`/certificates` passe désormais la fiche : fournisseur, durée, niveau). Cachet, QR et signature inchangés.

## Offres d'emploi réelles
`backend/jobsources.py` interroge en direct Adzuna (clé), France Travail (clé), Arbeitnow et Remotive (sans clé), en parallèle, avec cache 15 min ;
les offres sont indexées dans Qdrant (candidature possible) puis classées par compétences. Les offres du catalogue de démo (fictives, surtout Paris)
sont masquées sauf `JOBS_DEMO=1`. `/jobs/search` et `/jobs/match` renvoient `sources` (statut par fournisseur, affiché dans l'interface).
Sans clé : Allemagne + télétravail seulement. Pas d'API gratuite pour MA / TN / DZ / Golfe : liens de recherche en direct uniquement.

## Service 5 — Élaborer les factures (Propriétaire d'entreprise)
`backend/invoices.py` + routes `/invoices/preview`, `/invoices/pdf`, `/invoices/next-number` (permission `growth`). Pas de LLM : calcul déterministe en `Decimal`
(ligne = qté × PU × (1 − remise), arrondi demi supérieur ; TVA par taux sur la base de ce taux ; TTC ; acompte ; net à payer), 5 régimes de TVA
(standard, franchise, autoliquidation, livraison intracommunautaire, export), mentions légales FR/DE/IT/ES + génériques (art. L441-10 pour les B2B français),
contrôles de conformité (identifiants vendeur/client, n° de série, échéance, IBAN, date de prestation en Allemagne), PDF A4 en 6 langues (arabe en miroir)
sur plusieurs pages. Les données vendeur (IBAN inclus) restent dans le navigateur (`localStorage`) ; le serveur ne stocke aucune facture.
Limites : le PDF n'est pas une facture électronique structurée (Factur-X / XRechnung / FatturaPA) ; les mentions sont à valider par un expert-comptable.

### Factur-X, avoirs et devis (service 5)
- `doc_type` : `invoice` (FA-), `credit_note` (AV-, montants affichés en négatif, facture d'origine + motif obligatoires, ni acompte ni de pénalités), `quote` (DE-, validité, cadre « Bon pour accord »).
- `backend/facturx.py` + `POST /invoices/facturx` : PDF visible (polices incorporées) + XML CII profil **EN 16931** (type 380 facture / 381 avoir ; catégories TVA S, Z, E, AE, K, G ; remise de ligne en BG-27 pour que quantité × prix − remise = net) incorporé en `factur-x.xml` (AFRelationship `/Alternative`),
  XMP PDF/A-3B + schéma d'extension `fx`, profil sRGB. Les devis sont refusés (ce ne sont pas des factures). Dépendances : `pikepdf`, `lxml`, `Pillow` ; police latine : `python backend/fonts/fetch_fonts.py` (Noto Sans) ou DejaVu/Arial détectés.
- **Non validé officiellement** : lancez Mustang (`java -jar Mustang-CLI.jar --action validate --source facture.pdf`) ou le validateur Factur-X / veraPDF sur vos premiers fichiers. L'en-tête `x-facturx-pdfa: ready|partial` indique si polices et profil de sortie sont présents.
- Journal des documents (statuts, avoir depuis facture, devis converti en facture, export CSV) : `localStorage` de ce navigateur uniquement, plafonné à 200 documents ; sauvegardez le CSV. Le serveur ne stocke rien.

## Import d'un CV déjà prêt (Formations et Offres d'emploi)
`backend/cv_import.py` + `POST /cv/import` (`{filename, data_b64}`, permission `cv`). Formats détectés sur les octets : PDF (pypdf), Word .docx (zip + XML, sans dépendance), texte (UTF-8/16, cp1252). Analyse par règles, sans IA ni tiers, fichier non conservé :
coordonnées, nom, résumé, expériences (dates, titre, entreprise, missions), formations, compétences (rubrique + dictionnaire canonique), langues et niveaux (CECR ou mots), FR/EN/DE/ES/IT/AR.
Le formulaire « Création de CV Europass » est pré-rempli et sert ensuite à l'analyse des formations, à la recherche d'offres et aux candidatures. Un PDF importé (≤ 1,4 Mo) est joint tel quel aux candidatures (sinon Europass).
Limites : mises en page à colonnes/tableaux = résultat partiel ; PDF scanné (image) refusé avec message ; .doc ancien refusé. Le résultat est toujours à relire.
Interface : numéros des boutons colorés (1 ambre, 2 émeraude, 3 violet, 4 rose, 5 cyan) dans les deux menus.

## Bouton 6 « Améliorer votre profil LinkedIn » (menu Espace Candidat)
`backend/linkedin.py` + `POST /linkedin/audit` (permission `cv`) et `POST /linkedin/boost`.
- **LinkedIn n'offre aucune API publique de lecture/écriture de profil et interdit le scraping** : l'utilisateur colle ses textes (ou pré-remplit depuis son CV / son PDF de profil via `/cv/import`), l'outil analyse, puis il recopie les améliorations sur LinkedIn. Rien n'est envoyé à LinkedIn et aucune connexion à son compte n'est demandée.
- Audit déterministe (sans IA ni tiers), score /100 : titre 20, À propos 25, expériences 20, compétences 15, complétude 20 (photo, bannière, URL, localisation, « À la une », recommandations). Bandes : vert ≥ 80, jaune ≥ 55, rouge. Constats classés par priorité avec gain de points, mots-clés du poste visé présents/manquants (dictionnaire canonique de `matching`), titres proposés et squelette d'« À propos » construits **uniquement** avec les faits saisis (jamais de chiffre ou d'employeur inventé).
- Gestion : plan 30 jours (semaines 1-4 + routines) à cocher, historique des scores ; tout est stocké dans `localStorage` de ce navigateur (`careerup_li`, `careerup_li_done`).
- « Boost IA » facultatif : réécriture par Claude via `ANTHROPIC_API_KEY` (503 clair sans clé) ; le bouton « Copier le prompt » permet de le faire dans Claude sans clé. Le prompt interdit toute invention ; relire avant de publier.
- Interface en 6 langues ; numéro 6 en vert citron. Tests : `tests/test_linkedin.py`, routes dans `tests/n8n_routes_smoke.py`.

## Service 6 « Conseil en stratégie, RSE (développement durable) et conformité » (menu Espace Entreprise)
`backend/strategy.py` + `POST /strategy/diagnostic` (permission `growth`) ; conseiller IA via `POST /growth/chat` avec `service: 6` (persona `PERSONA6` dans `growth.py`, service 5 = factures, sans chat).
- **Diagnostic déterministe** (sans IA ni tiers) : 16 questions (stratégie 5, RSE 5, conformité 6), réponses Non / Partiellement / Oui (0-2). Score par pilier et global /100 (vert ≥ 75, jaune ≥ 45, rouge) ; les questions sans réponse ne sont pas pénalisées.
- **Feuille de route** : chaque écart a un impact et un effort (1-3). 30 jours = gains rapides (impact ≥ 2, effort ≤ 2, conformité sans « oui » en premier : risque juridique), 90 jours = le reste à effort ≤ 2, 12 mois = chantiers de fond. Actions cochables → avancement du plan.
- **Radar réglementaire indicatif** (`regulations(pays, effectif, CA)`) : RGPD et équivalents Maroc/Tunisie/Algérie, lanceurs d'alerte (≥ 50), transparence salariale, NIS2, AI Act, CSRD (> 1 000 salariés et > 450 M€ après l'omnibus adopté en 2026, applicable aux exercices ouverts dès 2027 : calendrier de transposition à confirmer ; sinon standard volontaire VSME), CSDDD (> 5 000 et > 1,5 Md€), France (DUERP, CSE ≥ 11, index d'égalité ≥ 50, BEGES ≥ 500, Sapin II ≥ 500 et 100 M€, facturation électronique), LkSG allemand (≥ 1 000), label RSE CGEM, ISO et EcoVadis. Statuts : s'applique probablement / à vérifier / volontaire / bon à savoir. **À valider avec un juriste** : seuils et dates évoluent ; à revoir à chaque changement de texte (`strategy.regulations`, libellés `r_*` dans `I18N_ST`).
- Conseiller IA (facultatif, `ANTHROPIC_API_KEY`) : reçoit un résumé du diagnostic (pays, effectif, objectif, scores, principaux écarts) et propose stratégie de croissance, feuille de route RSE, conformité, plan global, sans inventer de lois ni de chiffres.
- Réponses, actions cochées et historique des scores : `localStorage` (`careerup_st`, `careerup_st_hist`) ; impression / PDF via le navigateur. Interface FR/EN/DE/ES/IT/AR ; badge 6 vert citron. Tests : `tests/test_strategy.py` (dont couverture i18n de tous les identifiants) et `tests/n8n_routes_smoke.py`.

## Service 2 « E-mails : prospecter, lire et répondre » (menu Espace Entreprise)
Le bouton 2 (ex-« Envoyer des emails pour chercher de nouveaux clients ») a deux onglets : **Prospection** (assistant IA, inchangé) et **E-mails reçus**.
- `backend/mailbox.py` + routes `GET /mail/status`, `GET /mail/inbox`, `POST /mail/parse` (e-mail collé ou fichier `.eml`), `POST /mail/report`, `POST /mail/draft`, `POST /mail/send` ; lecture via `gmail-service` (`GET /inbox`, `GET /message/:id`).
- **Lecture seule** (scope `gmail.readonly`, désactivée par défaut : `GMAIL_READ=true` + jeton Google) ; sans compte relié, boîte de démonstration. Jamais de suppression, d'archivage ni de marquage « lu » ; pièces jointes non lues.
- Classement et rapport **par règles** (hameçonnage, automatique, réclamation, paiement, devis/commande, rendez-vous, assistance, autre ; urgence ; action conseillée ; résumé), rapport copiable ou imprimable en PDF.
- Brouillon de réponse : IA si `ANTHROPIC_API_KEY`, sinon modèle avec passages `[à compléter]` ; ton et langue au choix, consigne facultative. Le texte reçu est une donnée non fiable (jamais une consigne) ; aucun prix, délai ou engagement inventé.
- **Rien ne part sans validation** : l'utilisateur relit et modifie, coche « j'ai relu », complète les passages entre crochets (bouton bloqué tant qu'il en reste), confirme dans une boîte de dialogue ; le serveur exige `confirmed: true`, retrouve lui-même le destinataire d'un message de la boîte (le client ne peut pas le changer), refuse de répondre aux messages automatiques ou suspects, limite à 10 envois par heure. `DRY_RUN=true` (défaut) : envoi simulé.
- Tests : `tests/test_mailbox.py`, routes dans `tests/n8n_routes_smoke.py` (lecture, brouillon sans envoi, refus sans validation, destinataire imposé par le serveur, refus des messages automatiques).

## Noms des menus (alignés sur la description sous le logo : « trouvez un emploi & développez votre entreprise »)
Espace Candidat : 1 Création de CV Europass · 2 Offres d'emploi ciblées · 3 Analyse de compatibilité ATS · 4 Candidatures assistées · 5 Formations et certifications · 6 Optimisation du profil LinkedIn.
Espace Entreprise : 1 Animation des pages Facebook · 2 Prospection et gestion des e-mails · 3 Création de spots publicitaires · 4 Optimisation IA des visuels produits · 5 Facturation, devis et avoirs · 6 Conseil stratégique, RSE et conformité.
Les libellés (6 langues) sont dans le bloc `I18N_NAV` de `frontend/index.html`, qui prime sur les définitions plus anciennes ; la description sous le logo (`tagline`) y est aussi harmonisée dans toutes les langues.

## Assistant IA de l'Espace Entreprise — renforcement
`backend/growth.py` (services 1, 2, 3, 4, 6) :
- **Qualité** : bloc `QUALITY` commun (livrable prêt à copier, 3 questions de cadrage au maximum, exemples adaptés au secteur/pays, « (à vérifier) » sur tout fait incertain, respect du droit et des plateformes, ligne « Prochaine action »), date du jour injectée pour les calendriers, mémoire entreprise toujours traitée comme donnée (champs limités à 300 caractères).
- **Fiabilité** : `_send` relance jusqu'à 3 fois (429, 5xx, 529, délai dépassé, coupure réseau) avec attente croissante ; pas de relance sur erreur 4xx. `trim_history` garde les échanges récents (14 000 caractères) pour éviter les dépassements de contexte.
- **Vitesse et coût** : bloc système mis en cache (`cache_control: ephemeral`) ; `max_tokens` 3000, température 0,5.
- **Interface** : sous la dernière réponse, boutons d'affinage « Plus court / Plus détaillé / Plus chaleureux / Autre version » (6 langues) et menu rapide 1 à 6 (le 6 manquait). Tests : `tests/test_growth.py`.

## Nom de l'agent : CARRIVA
« CAREER UP » était déjà utilisé par une autre société (careerup.com) : l'agent s'appelle désormais **CARRIVA** (interface, titre de page, PDF, e-mails d'attestation, cachet, métadonnées Factur-X, agent e-mail, documentation). Les clés `localStorage` (`careerup_*`) et les variables `CAREER_*` gardent volontairement leur nom pour ne pas perdre les données déjà saisies par les utilisateurs. Une recherche web n'a trouvé aucun usage exact de « Carriva » dans l'emploi ou l'IA, mais ce n'est **pas** une recherche d'antériorité : avant tout usage commercial, vérifiez la marque auprès de l'INPI / EUIPO et la disponibilité du domaine.

## Audit des lacunes — corrections
- **Jeton expiré** (15 min en dev) : `authFetch` se reconnecte automatiquement sur 401 puis rejoue la requête.
- **Limites de débit** par utilisateur (`cert_mail.Limiter`) : `LLM_LIMIT` (chat IA, boost LinkedIn, brouillons e-mail) et `HEAVY_LIMIT` (PDF, Factur-X, import CV, contrôle photo) → HTTP 429.
- **Prospection** : classement des e-mails trouvés par préfixe préféré (`contact@`, `info@`… avant les autres).
- **Messages d'erreur** de l'API normalisés côté interface (`apiError`) ; imports inutilisés supprimés ; service inconnu → 422.
- **Alertes emploi** : bloc dans le panneau « offres » (`#alertBox`) → `POST/GET/DELETE /jobs/alerts`. Case de consentement obligatoire, désinscription = suppression du profil conservé. L'envoi réel dépend du flux n8n d'alertes. `api()` gère le 204.
- Les clés `localStorage` `careerup_*` sont conservées volontairement après le renommage en CARRIVA (pas de perte de données utilisateur).

## Service 4 « Retouche photo & visuels produit premium » (Espace Entreprise)
- `backend/retouch.py` : `plan()` (règles déterministes : étapes avec outils **gratuits** — Upscayl, Photoroom, Microsoft Designer, remove.bg, Photopea/GIMP/Fotor, Squoosh —, réglages lumière/couleur chiffrés par type de sujet et éclairage, export par usage, contrôle qualité) et `enhance()` (Pillow : balance des blancs limitée à ±8 %, niveaux, débruitage médian léger, contraste/saturation modérés, agrandissement Lanczos ≤ ×2, netteté adaptative ; proportions et canal alpha conservés ; 8 Mo / 40 Mpx max ; rien n'est conservé).
- Routes : `POST /images/plan` (perm « growth »), `POST /images/enhance` (limite `HEAVY_LIMIT`, 422 si image invalide). Le plan renvoie des identifiants + paramètres : l'interface les traduit (clés `s_*`, `k_*`, `ph_*` de `I18N_R`, 6 langues).
- Limites assumées : ce n'est pas de la super-résolution IA ni un détourage automatique (modèle à télécharger) ; le plan oriente vers Upscayl et Photoroom. Le service IA conversationnel n°4 (`growth.SERVICES[4]`) reste disponible côté API.
- Interface : panneau `#gRetouch` (ids `rt*`, distincts de la photo de CV `ph*`).

## Service 3 « Spots vidéo publicitaires clé en main » (Espace Entreprise)
- `backend/spot.py` : `campaign()` produit, sans IA ni tiers, la structure d'une campagne en 5 sections : stratégie (hook, angle problème/solution – avant/après – tendance/humour choisi automatiquement selon le ton, UVP, CTA), storyboard minuté (15/30/60 s ; hook = 3 s ; 3, 5 ou 7 plans), prompts B-roll en anglais, prompt voix-off, prompt musique, pile d'outils gratuits (CapCut, Clipchamp, ElevenLabs gratuit, Pexels, Pixabay, Mixkit, Coverr, YouTube Audio Library, DaVinci Resolve, Canva, Adobe Podcast Enhance, Audacity, Microsoft Designer), format d'export par plateforme, liste de conformité.
- Route `POST /spots/campaign` (perm « growth »). Les textes sont composés côté interface (clés `sp_*` de `I18N_R`, 6 langues) : la voix-off est comparée au nombre de mots maximal du plan (débit de la voix selon le ton) et un avertissement s'affiche si elle est trop longue. Tout est échappé avant affichage (saisies libres).
- Le service conversationnel n°3 (`growth.SERVICES[3]`) reste disponible côté API. Les quotas et licences des outils gratuits changent : le panneau le rappelle.

## Onglet « Tuteur d'autoformation » du bouton 5 Formations (Espace Candidat)
- `backend/tutor.py` : `master_prompt()` génère, sans IA ni tiers, un prompt maître en 6 langues (fr/en/de/es/it/ar) à coller dans n'importe quelle IA gratuite. Il intègre les 6 piliers (socratique avec escalade d'indices, Feynman, répétition espacée J+1/3/7/14/30 ; feuille de route par semaines/séances ; ressources 100 % gratuites sans lien inventé ; apprentissage actif ; boucle de rétroaction avec validation ≥ 80 % ; mode adaptatif « plus simple / plus d'exemples / exercice plus difficile ») + un journal d'apprentissage pour pallier l'oubli entre sessions.
- `plan()` estime la durée (30/50/80/120 h par palier de niveau, à titre indicatif), répartit les phases (30/40/30 %) et les 5 blocs d'une séance selon le temps disponible ; plafond 52 semaines.
- Route `POST /tutor/master-prompt` (perm « trainings »). Troisième onglet du panneau `#p-train` (`#tabTutor` / `#vTutor`, ids `tu*`), à côté de « Formations proposées » et « Formations standards » : copie, téléchargement .txt, protocole d'utilisation en 3 règles.
- Limite : le prompt n'est pas testé sur une IA réelle ; les plateformes citées (edX, Coursera en audit, MIT OCW, CS50, Khan Academy, freeCodeCamp, Odin Project, Anki…) peuvent changer leurs conditions : le prompt demande à l'IA de ne jamais inventer de lien et à l'apprenant de vérifier.

## Passe qualité transversale (12 boutons)
- **Audit automatisé** : parité i18n des 6 langues (clés, valeurs non vides, marqueurs `{x}` identiques — `tests/test_ux_static.py`), ids uniques, noms accessibles, contrastes (≥ 4,5:1 mesuré sur les pastilles), cibles tactiles ≥ 44 px pour les menus déroulants (style `select` global), absence de débordement horizontal à 320/390/1200 px dans les 6 langues, aucune erreur console. Un balayage Playwright (12 panneaux × onglets × 6 langues × 3 largeurs) est reproductible hors dépôt.
- **Corrections** : pastilles 3 et 4 assombries (contraste), `aria-label` automatique pour les zones de texte à placeholder, message d'état effacé à chaque changement de panneau/onglet, navigation clavier des onglets (flèches/Début/Fin, inversée en arabe), `:focus-visible` généralisé, textes arabes alignés sur les nouveaux noms de boutons, `loadStd` tolérant.
- **Brouillons** (`DR` dans `index.html`) : sauvegarde automatique locale (CV, offres, ATS, candidatures, spots, retouche, tuteur) dans `careerup_draft_*`, expiration 30 j, bouton « Effacer mes brouillons », jamais enregistrés : consentements, fichiers, mots de passe, e-mails reçus, factures. Le CV est restauré avec ses blocs expériences/formations/langues (hors photo).
- **Rapidité** : bouton « Remplir un exemple » (spots, tuteur) ; l'audience des spots est préremplie depuis la mémoire entreprise.
- **Robustesse** (`tests/test_fuzz_outputs.py`) : grilles exhaustives et entrées aléatoires/hostiles sur spot, retouche, tuteur, stratégie, LinkedIn (aucune exception, scores bornés, JSON valide, aucun gabarit non rempli).

## Accueil guidé, tableau de progression, export PDF

- **Accueil** (`<dialog id="onb">`, clé locale `careerup_onb`) : 3 étapes, affiché une seule fois si aucun brouillon n'existe ; il préremplit un exemple.
- **Tableau de progression** (`var PG`) : pour chaque espace, des étapes cochées automatiquement quand l'appel d'API correspondant réussit ; stocké localement, bouton de remise à zéro.
- **Export PDF** (`backend/report_pdf.py`, `POST /export/pdf`, permission `cv`) : le navigateur convertit le résultat affiché en blocs (`pdfBlocks`), le serveur produit le PDF (reportlab). Arabe pris en charge si la police est installée (`python backend/fonts/fetch_fonts.py`), sinon erreur 503 explicite.

## Application installable (PWA)

- `frontend/manifest.webmanifest`, `frontend/icons/*` (générées avec Pillow), `frontend/sw.js` servis à la racine par `app.py`.
- Le service worker ne met en cache que la coque statique (page, `app.css`, `cv-templates.js`, icônes) : **jamais** l'API, l'authentification ni une requête non-GET. La page est « réseau d'abord ». Changer `VERSION` dans `sw.js` à chaque évolution de la liste.

## Intégration continue et modularisation

- `.github/workflows/ci.yml` : tests, smoke des routes, vérification de syntaxe JS (page, service worker, agents Node).
- Authentification : déjà réelle (`ACCESS_CODES`, `/auth/login`) ; le jeton de développement est refusé hors `ENV=dev`.
- Le CSS est dans `frontend/app.css`. Les dictionnaires de langues restent dans `index.html` (les tests les analysent là) ; les extraire dans `i18n.js` est la prochaine étape, à faire en même temps que l'adaptation de `tests/test_ux_static.py`.

## Service 2 — onglet Messagerie (WhatsApp Business / Messenger)

- `backend/chat_reply.py` + `POST /chat/reply` (permission `growth`) : règles pures, **gratuit, sans IA ni API tierce**. Analyse (intention, chaleur, tempérament, canal) puis 3 réponses (express / persuasive / réassurance) structurées Accroche-Valeur-Question fermée, un conseil stratégique et le master prompt rempli.
- Anti-hallucination : prix, garantie, logistique, produit complémentaire et alternative ne viennent que de la configuration saisie ; sinon marqueur « À COMPLÉTER » localisé. Rareté seulement si l'utilisateur déclare son stock limité. Aucune vente croisée sur une réclamation ; aucune remise proposée sur une objection de prix.
- Envoi : copie manuelle ou lien gratuit `wa.me` (WhatsApp) ; aucune connexion à WhatsApp/Messenger, rien n'est conservé côté serveur. La configuration reste dans le navigateur (`carriva_chat_cfg`).
- Mémoire de conversation : le navigateur renvoie les messages précédents du client (10 au plus, en mémoire de la page seulement, jamais enregistrés). Le serveur en tire la tendance d'intérêt, le nombre d'objections de prix (2e objection → conseil d'arrêter de justifier), l'accord implicite (« oui », « ok » après une offre = achat), « prêt à acheter puis hésite » → rassurer, et supprime vente croisée et rareté après une réclamation. Détection de langue automatique, négations gérées, message de relance à 24 h.

## Service 7 (bouton 1) — Identité de marque et site web

- `backend/brand_site.py` + `POST /brand/kit` (permission `growth`) : règles pures, **gratuit, sans IA ni tiers**, rien conservé. Produit : concept de logo + aperçu SVG téléchargeable, charte (style, symbole, polices Google Fonts libres, palette HEX de 4 couleurs dont le primaire reste ≥ 4,5:1 sur blanc, avec psychologie des couleurs), prompt d'image en anglais, structure et textes des 5 pages, outils gratuits selon le niveau (débutant / intermédiaire / développeur), 3 conseils SEO et 3 conseils mobile selon l'objectif, questions de précision, master prompt rempli et **site HTML de départ** (un fichier, responsive, accessible, échappé).
- Anti-hallucination : aucun témoignage, chiffre, prix ni client inventé (marqueurs « À COMPLÉTER »). Toutes les entrées sont échappées (HTML et SVG).
- Numérotation : l'identifiant interne reste `data-svc="7"` pour ne pas casser les autres services ; l'affichage met ce bouton en n° 1 et décale les autres (2 à 7).

## Traitement des saisies (mise en forme + correction IA facultative)

- `backend/ai_input.py` : **toujours** (gratuit, déterministe) nettoyage HTML/espaces/contrôles, ponctuation, majuscule, point final selon le type de champ (`name` inchangé, `label`, `sentence`, `keywords` dédoublonnés). **Si** `ANTHROPIC_API_KEY` est défini (et `AI_INPUT` ≠ `off`) et que l'interrupteur « Correction IA des saisies » (`#aiGlobal`, mémorisé localement) est actif : une seule requête corrige orthographe et grammaire des textes libres, sans traduire ni rien ajouter.
- Garde-fous : la saisie est une donnée, jamais une instruction ; chaque champ est rejeté séparément si les nombres changent, si un lien/e-mail apparaît, si la longueur explose ou si le type est faux ; échec de l'IA → version mise en forme conservée. Limité par `LLM_LIMIT` ; cache par empreinte.
- Branché sur : spots (produit, cible, problème, bénéfice, offre), tuteur (sujet, objectif, contraintes), stratégie (secteur), messagerie (offre, persona, ton, règles, logistique, garantie, alternative), identité de marque (reformulation dédiée `brand_site.refine`). Le CV a son propre pipeline (`processing.py`) ; LinkedIn et les brouillons e-mail ont leur rédaction IA.
- **Volontairement exclus** : factures, devis et avoirs (montants, TVA, IBAN, mentions légales), noms et adresses, messages des clients, descriptions d'offres d'emploi : ils doivent rester fidèles à la lettre.
- Le bilan (statut + liste « avant → après ») s'affiche au-dessus de chaque résultat via `AI.badge` (le serveur renvoie `processing`).

## Bouton 7 Espace Candidat : « Lancer mon entreprise à 0 € » (BootstrapBot)

`backend/bootstrap_biz.py` + `POST /bootstrap/analyze` (permission `cv`). Version déterministe du prompt « BootstrapBot » (`backend/bootstrap_prompt.txt`) : gratuit, sans IA ni tiers, le CV collé n'est pas conservé.
- Étape 0 : domaines et compétences détectés par mots-clés (6 langues, accents ignorés), années d'expérience, avantage injuste présenté comme hypothèse à valider, 3 idées « zéro euro » choisies selon les domaines, chacune avec 3 raisons d'échec (avocat du diable), un test gratuit et des outils.
- Idée choisie (`idea` 0-2) : questions d'entretien, proposition de valeur + Business Model Canvas, MVP en 48 h, seuil de rentabilité.
- Anti-hallucination : champs inconnus = `[⚠️ À COMPLÉTER : …]` ; aucun prix ni chiffre de marché inventé ; calculs uniquement sur les nombres saisis (arrondi supérieur). Outils limités à la boîte à outils gratuite du prompt.
- Chasse aux coûts cachés (6 postes + alternatives gratuites) ; prompt maître prêt à copier dans une IA gratuite (prompt BootstrapBot + CV) ; export PDF du résultat (le prompt maître est exclu du PDF).
- Frontend : `#p-boot`, clés i18n `bt_*` / `b_boot` (6 langues). Tests : `tests/test_bootstrap_biz.py`, `test_ux_static.py`.

## Retraits

- Le **tuteur d'autoformation** (3ᵉ onglet de Formations, `backend/tutor.py`, `POST /tutor/master-prompt`) et le **tableau de progression** (tableau d'étapes par espace, coches ✓ sur les boutons) ont été supprimés à la demande de l'utilisateur. Les sections qui les décrivent plus haut sont historiques.
