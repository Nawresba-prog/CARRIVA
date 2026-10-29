"""Catalogue de formations CARRIVA : cours concrets, avec fournisseur, niveau, durée indicative, plan et lien.

- STANDARD : 4 parcours « standards » (langues, développement web, management de projet, marketing digital).
- SKILL_COURSES : cours rattachés à une compétence canonique (matching.TAXONOMY), utilisés pour les « formations proposées »
  selon les lacunes du profil.

Les plans (« modules ») sont des repères indicatifs rédigés pour l'application ; durées et contenus exacts : voir la page du fournisseur.
Les liens pointent vers la page du cours / du programme chez le fournisseur : à revérifier avant mise en production (les catalogues évoluent).
En production ce fichier est remplacé par l'import du catalogue réel (LMS, API Coursera/edX, etc.).
"""

import os

# (titre, fournisseur, niveau, durée, résumé, modules, url, compétences canoniques)
_STANDARD_RAW = {
    "languages": [
        ("Anglais général A1 → B2", "BBC Learning English", "Débutant → Intermédiaire", "≈ 60 h",
         "Parcours progressif de grammaire, vocabulaire et compréhension orale.",
         ["Grammaire essentielle et temps verbaux", "Vocabulaire du quotidien et du travail", "Compréhension orale (podcasts, vidéos)", "Expression écrite : e-mails et messages", "Mise en situation : réunions et entretiens"],
         "https://www.bbc.co.uk/learningenglish", ""),
        ("Préparation TOEIC / IELTS", "IELTS", "Intermédiaire → Avancé", "≈ 30 h",
         "Se préparer à un test reconnu par les employeurs et les universités.",
         ["Format et barème de l'examen", "Compréhension écrite et orale chronométrées", "Rédaction : lettres et essais", "Expression orale : entretien simulé", "Tests blancs et correction"],
         "https://www.ielts.org/for-test-takers/how-to-prepare", ""),
        ("Français langue étrangère (A1 → B2)", "TV5MONDE – Apprendre le français", "Débutant → Intermédiaire", "≈ 60 h",
         "Exercices guidés à partir de documents authentiques, par niveau CECR.",
         ["Se présenter et communiquer au quotidien", "Compréhension de documents vidéo", "Grammaire et conjugaison", "Écrire un e-mail professionnel", "Préparation au DELF"],
         "https://apprendre.tv5monde.com/fr", ""),
        ("Allemand : Nicos Weg (A1 → B1)", "Deutsche Welle", "Débutant → Intermédiaire", "≈ 100 h",
         "Cours vidéo gratuit en 3 niveaux, avec exercices interactifs.",
         ["A1 : se présenter, nombres, courses", "A2 : travail, logement, santé", "B1 : démarches et vie professionnelle", "Grammaire : cas et ordre des mots", "Préparation Goethe-Zertifikat"],
         "https://learngerman.dw.com/fr/nicos-weg/c-36519687", ""),
        ("Espagnol : parcours A1 → B2", "Instituto Cervantes – Aula Virtual de Español", "Débutant → Intermédiaire", "≈ 80 h",
         "Cours en ligne de l'institut officiel de langue espagnole.",
         ["Communication de base", "Vie quotidienne et voyages", "Monde du travail", "Grammaire et verbes irréguliers", "Préparation au DELE"],
         "https://ave.cervantes.es/", ""),
        ("Italien et arabe : bases A1 → A2", "Duolingo", "Débutant", "≈ 40 h",
         "Pratique quotidienne courte : vocabulaire, phrases types, prononciation.",
         ["Alphabet et prononciation", "Salutations et présentations", "Vocabulaire du quotidien", "Phrases utiles au travail", "Révisions espacées"],
         "https://www.duolingo.com/", ""),
    ],
    "web": [
        ("Responsive Web Design : HTML & CSS", "freeCodeCamp", "Débutant", "≈ 300 h (par projets)",
         "Construire 5 pages web responsives et accessibles.",
         ["Balises HTML et structure sémantique", "Mise en page CSS : Flexbox et Grid", "Responsive design", "Accessibilité", "Projets : portfolio, page produit"],
         "https://www.freecodecamp.org/learn/2022/responsive-web-design/", "html_css"),
        ("JavaScript moderne", "javascript.info", "Débutant → Intermédiaire", "≈ 60 h",
         "Le tutoriel de référence : langage, DOM, événements et asynchrone.",
         ["Variables, fonctions, objets", "Modules et classes", "DOM et événements", "Promesses et async/await", "Appels d'API avec fetch"],
         "https://javascript.info/", "javascript"),
        ("React : apprendre React", "react.dev", "Intermédiaire", "≈ 25 h",
         "Documentation officielle interactive : composants, état, effets.",
         ["Composants et JSX", "Props et état", "Listes et formulaires", "Effets et données distantes", "Projet : morpion puis application complète"],
         "https://react.dev/learn", "react javascript"),
        ("Node.js : introduction et API", "Node.js Foundation", "Intermédiaire", "≈ 20 h",
         "Créer un serveur et des API avec Node.js.",
         ["Modules et npm", "Serveur HTTP et routage", "Accès fichiers et bases de données", "API REST", "Tests et déploiement"],
         "https://nodejs.org/en/learn", "nodejs rest_api javascript"),
        ("Développement web complet (Full Stack)", "The Odin Project", "Débutant → Avancé", "≈ 1 000 h",
         "Parcours gratuit et complet : front, back, Git, base de données.",
         ["Fondations : Git et ligne de commande", "HTML, CSS, JavaScript", "Node.js et bases de données", "Projets portfolio", "Recherche d'emploi"],
         "https://www.theodinproject.com/", "javascript html_css git nodejs sql"),
        ("API web avec Python et FastAPI", "FastAPI", "Intermédiaire", "≈ 15 h",
         "Tutoriel officiel pas à pas : routes, validation, sécurité, tests.",
         ["Premières routes", "Validation avec Pydantic", "Authentification JWT", "Base de données SQL", "Tests"],
         "https://fastapi.tiangolo.com/tutorial/", "fastapi python rest_api testing"),
    ],
    "project": [
        ("Certificat Google Project Management", "Google via Coursera", "Débutant", "≈ 6 mois (10 h/sem.)",
         "Certificat professionnel couvrant tout le cycle de projet, avec méthodes agiles.",
         ["Fondamentaux de la gestion de projet", "Lancement : objectifs et périmètre", "Planification : budget, risques, calendrier", "Exécution et suivi", "Méthodes agiles et Scrum"],
         "https://www.coursera.org/professional-certificates/google-project-management", "project_management agile communication"),
        ("Scrum : le guide officiel et l'évaluation ouverte", "Scrum.org", "Débutant → Intermédiaire", "≈ 10 h",
         "Comprendre rôles, événements et artefacts Scrum, puis s'évaluer.",
         ["Les valeurs et la théorie Scrum", "Rôles : Product Owner, Scrum Master, équipe", "Événements : sprint, daily, revue, rétrospective", "Backlog et définition de « terminé »", "Test d'évaluation ouverte"],
         "https://www.scrum.org/open-assessments", "agile project_management"),
        ("Agile : coaching et pratiques (Kanban, Scrum)", "Atlassian", "Débutant", "≈ 8 h",
         "Tutoriels sur les pratiques agiles et leur mise en œuvre en équipe.",
         ["Principes agiles", "Kanban : limiter le travail en cours", "Rédiger des user stories", "Estimation et planification de sprint", "Indicateurs : vélocité et cycle time"],
         "https://www.atlassian.com/agile", "agile project_management"),
        ("Préparation CAPM / PMP", "Project Management Institute", "Intermédiaire → Avancé", "≈ 35 h",
         "Préparer une certification reconnue dans le monde entier.",
         ["Cadre PMBOK : domaines de performance", "Gestion du périmètre, du temps et des coûts", "Qualité, ressources et communications", "Risques et approvisionnements", "Questions d'entraînement"],
         "https://www.pmi.org/certifications", "project_management"),
        ("Planifier avec Excel : budget et diagramme de Gantt", "Microsoft", "Débutant", "≈ 6 h",
         "Construire planning, budget et suivi d'avancement dans Excel.",
         ["Tableaux et formules de base", "Diagramme de Gantt", "Suivi budgétaire", "Tableau de bord d'avancement", "Mise en forme conditionnelle"],
         "https://support.microsoft.com/fr-fr/excel#planification", "excel project_management"),
        ("Communication et leadership d'équipe", "Coursera – Université du Michigan", "Intermédiaire", "≈ 20 h",
         "Animer une équipe, conduire des réunions, gérer les conflits.",
         ["Écoute et feedback", "Conduite de réunion", "Gestion des conflits", "Motivation d'équipe", "Prise de parole"],
         "https://www.coursera.org/learn/leading-teams", "communication"),
    ],
    "marketing": [
        ("Fondamentaux du marketing digital", "Google – Digital Garage", "Débutant", "≈ 40 h",
         "Cours gratuit avec certificat : stratégie en ligne, SEO, publicité, réseaux sociaux.",
         ["Construire sa présence en ligne", "Référencement et publicité de recherche", "Réseaux sociaux et contenu", "E-mailing", "Analyse et mesure"],
         "https://learndigital.withgoogle.com/digitalgarage/course/digital-marketing", "digital_marketing seo"),
        ("Marketing de contenu", "HubSpot Academy", "Débutant → Intermédiaire", "≈ 5 h",
         "Planifier, produire et diffuser des contenus qui attirent des clients.",
         ["Stratégie de contenu et personas", "Rédiger pour le web", "Calendrier éditorial", "Diffusion et promotion", "Mesure des résultats"],
         "https://academy.hubspot.com/courses/content-marketing", "content_writing digital_marketing"),
        ("SEO : guide de démarrage", "Google Search Central", "Débutant", "≈ 6 h",
         "Les bonnes pratiques de référencement naturel, par la documentation officielle.",
         ["Comment fonctionne la recherche", "Titres, descriptions et contenus", "Structure du site et liens", "Images et vitesse", "Suivi avec Search Console"],
         "https://developers.google.com/search/docs/fundamentals/seo-starter-guide", "seo"),
        ("Google Analytics 4 : certification", "Google Skillshop", "Débutant → Intermédiaire", "≈ 4 h",
         "Mesurer le trafic et les conversions, puis passer la certification gratuite.",
         ["Modèle de données GA4", "Rapports d'acquisition et d'engagement", "Événements et conversions", "Audiences", "Passer la certification"],
         "https://skillshop.withgoogle.com/", "data_analysis digital_marketing"),
        ("Publicité sur les réseaux sociaux", "Meta Blueprint", "Débutant → Intermédiaire", "≈ 8 h",
         "Créer et optimiser des campagnes Facebook et Instagram.",
         ["Objectifs et ciblage", "Formats publicitaires", "Budgets et enchères", "Pixel et mesure", "Optimisation"],
         "https://www.facebook.com/business/learn", "digital_marketing"),
        ("E-mail marketing", "HubSpot Academy", "Débutant", "≈ 4 h",
         "Concevoir des campagnes d'e-mails efficaces et conformes au RGPD.",
         ["Construire sa liste de contacts", "Rédiger objet et contenu", "Segmentation", "Tests A/B", "Conformité RGPD"],
         "https://academy.hubspot.com/courses/email-marketing", "digital_marketing content_writing"),
    ],
}

# compétence(s) -> cours ciblés pour combler les lacunes (titre, fournisseur, niveau, durée, résumé, modules, url, compétences)
_SKILL_RAW = [
    ("Python pour la data science", "Kaggle Learn", "Débutant", "≈ 15 h", "Python, pandas et visualisation en notebooks.", ["Syntaxe Python", "pandas", "Visualisation", "Nettoyage de données", "Mini-projet"], "https://www.kaggle.com/learn/python", "python data_analysis"),
    ("SQL pour l'analyse de données", "SQLBolt", "Débutant", "≈ 8 h", "Leçons interactives : SELECT, jointures, agrégations.", ["SELECT et filtres", "Jointures", "Agrégations", "Sous-requêtes", "Modification de données"], "https://sqlbolt.com/", "sql data_analysis"),
    ("Java : apprendre le langage", "dev.java (Oracle)", "Débutant → Intermédiaire", "≈ 40 h", "Parcours officiel : syntaxe, objets, collections, API.", ["Syntaxe et types", "Programmation orientée objet", "Collections", "Gestion des erreurs", "Applications console"], "https://dev.java/learn/", "java"),
    ("C# : visite guidée du langage", "Microsoft Learn", "Débutant", "≈ 20 h", "Découvrir C# et .NET avec exercices.", ["Types et contrôle de flux", "Classes", "LINQ", "Async", "Application console"], "https://learn.microsoft.com/fr-fr/dotnet/csharp/tour-of-csharp/", "csharp"),
    ("PHP : premiers pas", "PHP Manual", "Débutant", "≈ 15 h", "Bases du langage PHP côté serveur.", ["Syntaxe", "Formulaires", "Sessions", "Accès base de données", "Sécurité de base"], "https://www.php.net/manual/fr/getting-started.php", "php"),
    ("TypeScript : manuel officiel", "TypeScript", "Intermédiaire", "≈ 12 h", "Typage statique pour JavaScript.", ["Types de base", "Interfaces", "Génériques", "Modules", "Configuration"], "https://www.typescriptlang.org/docs/handbook/intro.html", "typescript javascript"),
    ("Angular : tutoriels officiels", "Angular", "Intermédiaire", "≈ 20 h", "Construire une application Angular.", ["Composants", "Templates", "Services", "Routage", "Formulaires"], "https://angular.dev/tutorials", "angular typescript"),
    ("Vue.js : tutoriel interactif", "Vue.js", "Débutant → Intermédiaire", "≈ 12 h", "Les bases de Vue en exercices.", ["Rendu déclaratif", "Réactivité", "Composants", "Routage", "Projet"], "https://vuejs.org/tutorial/", "vue javascript"),
    ("Base de données NoSQL avec MongoDB", "MongoDB University", "Débutant", "≈ 10 h", "Modéliser et interroger des documents.", ["Documents et collections", "Requêtes", "Agrégation", "Index", "Modélisation"], "https://learn.mongodb.com/", "nosql"),
    ("Docker : démarrer", "Docker", "Débutant", "≈ 6 h", "Images, conteneurs, volumes et Compose.", ["Conteneurs", "Dockerfile", "Volumes", "Compose", "Bonnes pratiques"], "https://docs.docker.com/get-started/", "docker"),
    ("Kubernetes : bases", "Kubernetes", "Intermédiaire", "≈ 10 h", "Déployer et exposer une application sur un cluster.", ["Cluster et pods", "Déploiements", "Services", "Mise à l'échelle", "Mises à jour"], "https://kubernetes.io/docs/tutorials/kubernetes-basics/", "kubernetes docker cloud"),
    ("Terraform : infrastructure as code", "HashiCorp", "Intermédiaire", "≈ 12 h", "Décrire et provisionner l'infrastructure.", ["Providers et ressources", "Variables", "État", "Modules", "Environnements"], "https://developer.hashicorp.com/terraform/tutorials", "terraform cloud"),
    ("CI/CD avec GitHub Actions", "GitHub Docs", "Intermédiaire", "≈ 6 h", "Automatiser tests et déploiements.", ["Workflows", "Jobs et étapes", "Secrets", "Déploiement", "Cache"], "https://docs.github.com/fr/actions/quickstart", "ci_cd git testing"),
    ("AWS Cloud Practitioner Essentials", "AWS Training", "Débutant", "≈ 6 h", "Fondamentaux du cloud AWS, préparation à la certification.", ["Services de base", "Sécurité", "Tarification", "Architecture", "Examen blanc"], "https://aws.amazon.com/training/digital/", "aws cloud"),
    ("Azure Fundamentals (AZ-900)", "Microsoft Learn", "Débutant", "≈ 10 h", "Concepts cloud et services Azure.", ["Concepts cloud", "Services Azure", "Sécurité", "Gouvernance", "Examen blanc"], "https://learn.microsoft.com/fr-fr/training/azure/", "azure cloud"),
    ("Google Cloud : parcours de formation", "Google Cloud Skills", "Débutant", "≈ 10 h", "Parcours de base sur GCP.", ["Compute", "Stockage", "Réseau", "IAM", "Laboratoires"], "https://cloud.google.com/learn/training", "gcp cloud"),
    ("Administration Linux : Linux Journey", "Linux Journey", "Débutant", "≈ 15 h", "Ligne de commande, fichiers, permissions, réseau.", ["Ligne de commande", "Fichiers et permissions", "Processus", "Réseau", "Scripts shell"], "https://linuxjourney.com/", "linux"),
    ("Git : Pro Git (livre officiel)", "git-scm.com", "Débutant → Intermédiaire", "≈ 10 h", "Maîtriser le versionnage et la collaboration.", ["Commandes de base", "Branches", "Dépôts distants", "Workflows", "Résolution de conflits"], "https://git-scm.com/book/fr/v2", "git"),
    ("Tests avec pytest", "pytest", "Intermédiaire", "≈ 6 h", "Écrire des tests unitaires et d'intégration.", ["Premiers tests", "Fixtures", "Paramétrage", "Mocks", "Couverture"], "https://docs.pytest.org/en/stable/getting-started.html", "testing python"),
    ("API REST : concevoir et documenter", "Microsoft Learn", "Intermédiaire", "≈ 6 h", "Principes REST, codes HTTP, versionnage, OpenAPI.", ["Ressources et verbes HTTP", "Codes de réponse", "Versionnage", "Sécurité", "OpenAPI"], "https://learn.microsoft.com/fr-fr/azure/architecture/best-practices/api-design", "rest_api microservices"),
    ("Microservices : architecture", "Microsoft Learn", "Avancé", "≈ 8 h", "Découper un système en services indépendants.", ["Découpage par domaine", "Communication", "Données", "Résilience", "Observabilité"], "https://learn.microsoft.com/fr-fr/azure/architecture/microservices/", "microservices"),
    ("Cybersécurité : SecNumacadémie", "ANSSI", "Débutant", "≈ 20 h", "MOOC gratuit de l'agence nationale française de sécurité.", ["Panorama de la sécurité", "Sécurité de l'authentification", "Sécurité sur Internet", "Sécurité du poste de travail", "Sécurité de l'appareil nomade"], "https://secnumacademie.gouv.fr/", "cybersecurity audit"),
    ("Réseaux : Cisco Networking Academy", "Cisco", "Débutant → Intermédiaire", "≈ 70 h", "Fondamentaux des réseaux et préparation CCNA.", ["Modèle OSI et TCP/IP", "Adressage IP", "Commutation", "Routage", "Sécurité réseau"], "https://www.netacad.com/", "networking"),
    ("Machine Learning Crash Course", "Google", "Intermédiaire", "≈ 15 h", "Apprentissage automatique avec exercices pratiques.", ["Régression", "Classification", "Données", "Réseaux de neurones", "Évaluation"], "https://developers.google.com/machine-learning/crash-course", "machine_learning statistics"),
    ("Deep learning et NLP : cours Hugging Face", "Hugging Face", "Avancé", "≈ 30 h", "Transformers, traitement du langage et modèles pré-entraînés.", ["Transformers", "Fine-tuning", "Tokenisation", "Tâches NLP", "Déploiement"], "https://huggingface.co/learn/nlp-course", "nlp deep_learning machine_learning"),
    ("Statistiques et probabilités", "Khan Academy", "Débutant → Intermédiaire", "≈ 30 h", "Statistiques descriptives et inférentielles.", ["Description des données", "Probabilités", "Lois usuelles", "Estimation", "Tests d'hypothèse"], "https://fr.khanacademy.org/math/statistics-probability", "statistics"),
    ("Power BI : parcours Microsoft", "Microsoft Learn", "Débutant → Intermédiaire", "≈ 15 h", "Modéliser des données et créer des rapports.", ["Connexion aux données", "Modélisation", "DAX", "Visualisations", "Publication"], "https://learn.microsoft.com/fr-fr/training/powerplatform/power-bi", "power_bi data_analysis"),
    ("Tableau : formation gratuite", "Tableau", "Débutant", "≈ 10 h", "Visualiser des données et créer des tableaux de bord.", ["Connexion", "Graphiques", "Calculs", "Tableaux de bord", "Partage"], "https://www.tableau.com/learn/training", "tableau data_analysis"),
    ("Excel : formation officielle", "Microsoft", "Débutant → Intermédiaire", "≈ 10 h", "Formules, tableaux croisés dynamiques, graphiques.", ["Formules", "Fonctions de recherche", "Tableaux croisés", "Graphiques", "Automatisation"], "https://support.microsoft.com/fr-fr/excel", "excel"),
    ("Data engineering avec Apache Spark", "Apache Spark", "Avancé", "≈ 12 h", "Traitements distribués de gros volumes.", ["RDD et DataFrames", "Spark SQL", "Transformations", "Optimisation", "Pipeline ETL"], "https://spark.apache.org/docs/latest/quick-start.html", "etl big_data sql"),
    ("Comptabilité : introduction", "edX", "Débutant", "≈ 30 h", "Bilan, compte de résultat, écritures.", ["Principes comptables", "Écritures", "Bilan", "Compte de résultat", "Analyse"], "https://www.edx.org/learn/accounting", "accounting finance"),
    ("Finance d'entreprise : introduction", "Coursera", "Intermédiaire", "≈ 20 h", "Valeur, risque, financement et décisions d'investissement.", ["Valeur temps de l'argent", "Évaluation", "Risque", "Structure financière", "Budget"], "https://www.coursera.org/browse/business/finance", "finance audit"),
    ("Vente B2B : ventes entrantes", "HubSpot Academy", "Débutant", "≈ 4 h", "Prospecter, qualifier, présenter et conclure.", ["Qualification", "Découverte", "Présentation", "Négociation", "Suivi"], "https://academy.hubspot.com/courses/inbound-sales", "sales communication"),
    ("Service client : relation et fidélisation", "HubSpot Academy", "Débutant", "≈ 4 h", "Écouter, résoudre et fidéliser.", ["Écoute active", "Gestion des plaintes", "Canaux", "Indicateurs", "Fidélisation"], "https://academy.hubspot.com/courses/customer-service", "customer_service communication"),
    ("Ressources humaines : fondamentaux", "OpenLearn", "Débutant", "≈ 15 h", "Recrutement, gestion des talents et droit du travail.", ["Recrutement", "Intégration", "Évaluation", "Formation", "Droit du travail"], "https://www.open.edu/openlearn/money-business/", "hr communication"),
    ("Supply chain : introduction", "edX", "Débutant → Intermédiaire", "≈ 30 h", "Prévision, stocks, approvisionnement et transport.", ["Prévision de la demande", "Gestion des stocks", "Approvisionnement", "Transport", "Indicateurs"], "https://www.edx.org/learn/supply-chain-management", "logistics project_management"),
    ("UX Design : certificat Google", "Google via Coursera", "Débutant", "≈ 6 mois", "Recherche utilisateur, wireframes, prototypes Figma.", ["Recherche utilisateur", "Wireframes", "Prototypes Figma", "Tests d'usabilité", "Portfolio"], "https://www.coursera.org/professional-certificates/google-ux-design", "ux_design graphic_design"),
    ("Design graphique avec Canva", "Canva Design School", "Débutant", "≈ 6 h", "Principes de design et création de supports.", ["Typographie", "Couleurs", "Mise en page", "Réseaux sociaux", "Charte graphique"], "https://www.canva.com/designschool/", "graphic_design"),
    ("Apprendre à apprendre / pédagogie", "Coursera", "Débutant", "≈ 15 h", "Techniques d'apprentissage efficaces à transmettre.", ["Mémorisation", "Concentration", "Procrastination", "Pratique", "Transmission"], "https://www.coursera.org/learn/learning-how-to-learn", "teaching communication"),
]


def _mk(row, category=""):
    title, provider, level, duration, summary, modules, url, skills = row
    return {"title": title, "provider": provider, "level": level, "duration": duration, "summary": summary,
            "objectives": summary, "modules": modules, "url": url, "skills": skills, "category": category}


STANDARD = {cat: [_mk(r, cat) for r in rows] for cat, rows in _STANDARD_RAW.items()}
SKILL_COURSES = [_mk(r, "skill") for r in _SKILL_RAW]


def all_courses() -> list[dict]:
    """Tous les cours, dédoublonnés par URL (priorité aux parcours standards), prêts à indexer."""
    from . import lms  # cours hébergés sur la plateforme de formation de l'organisme (backend/lms_courses.json), s'il y en a
    seen, out = set(), []
    for c in [c for rows in STANDARD.values() for c in rows] + SKILL_COURSES + lms.load_courses(base_url=os.environ.get("MOODLE_URL", "")):
        key = c["url"]
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


# --------------------------------------------------------------------------- traductions (catalog_i18n.json : url -> langue -> champs)
import json as _json
from pathlib import Path as _Path

_I18N: dict | None = None


def localize(course: dict, lang: str) -> dict:
    """Cours traduit (titre, résumé, programme, niveau, durée) ; repli sur le français si la langue ou le cours est absent."""
    global _I18N
    if _I18N is None:
        try:
            _I18N = _json.loads((_Path(__file__).with_name("catalog_i18n.json")).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _I18N = {}
    tr = _I18N.get(course.get("url", ""), {}).get(lang)
    if not tr:
        return course
    return {**course, "title": tr["title"], "summary": tr["summary"], "objectives": tr["summary"], "modules": tr["modules"],
            "level": tr["level"], "duration": tr["duration"]}
