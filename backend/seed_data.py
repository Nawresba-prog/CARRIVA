"""Catalogue de démonstration (offres + formations). En production : alimenté par n8n (WF-1) et le catalogue de formation.
Les compétences utilisent les identifiants canoniques de matching.TAXONOMY."""

_J = [
    # titre, entreprise, pays, ville, compétences, description
    ("Développeur Python backend", "Acme", "FR", "Paris", "python fastapi sql docker rest_api git", "Développement d'API et de services backend"),
    ("Développeur Full Stack JavaScript", "Nova", "FR", "Lyon", "javascript react nodejs sql git html_css", "Applications web full stack"),
    ("Data Analyst", "Globex", "DE", "Berlin", "sql python data_analysis power_bi statistics excel", "Analyse de données et tableaux de bord"),
    ("Data Scientist", "Datalab", "FR", "Toulouse", "python machine_learning statistics sql deep_learning", "Modèles prédictifs et IA"),
    ("Ingénieur DevOps", "Initech", "IT", "Milano", "kubernetes docker terraform ci_cd linux cloud", "Plateforme cloud et automatisation"),
    ("Ingénieur Cloud AWS", "Skyline", "DE", "München", "aws terraform linux docker networking cloud", "Infrastructure cloud AWS"),
    ("Frontend Developer", "Umbrella", "ES", "Madrid", "javascript react html_css typescript ux_design git", "Interfaces web accessibles"),
    ("Développeur Java", "Banque Nord", "FR", "Lille", "java sql microservices rest_api git testing", "Applications bancaires"),
    ("Ingénieur Cybersécurité", "SecureIT", "FR", "Paris", "cybersecurity networking linux audit", "Sécurité des systèmes d'information"),
    ("Administrateur Réseaux", "NetCorp", "MA", "Casablanca", "networking linux cybersecurity", "Administration réseau"),
    ("Ingénieur QA / Test Automation", "Qualix", "DE", "Hamburg", "testing python ci_cd git agile", "Automatisation des tests"),
    ("Data Engineer", "Flux", "NL", "Amsterdam", "python sql etl big_data aws docker", "Pipelines de données"),
    ("Chef de projet IT", "Consulto", "FR", "Nantes", "project_management agile communication", "Pilotage de projets informatiques"),
    ("Product Owner", "Appsy", "DE", "Berlin", "agile project_management communication ux_design", "Pilotage produit"),
    ("Responsable Marketing Digital", "Brandly", "FR", "Bordeaux", "digital_marketing seo content_writing communication data_analysis", "Acquisition et contenu"),
    ("Community Manager", "Social+", "ES", "Barcelona", "digital_marketing content_writing communication graphic_design", "Réseaux sociaux"),
    ("Spécialiste SEO", "Rankup", "IT", "Roma", "seo content_writing data_analysis digital_marketing", "Référencement naturel"),
    ("Comptable", "Fidelis", "FR", "Marseille", "accounting excel finance audit", "Comptabilité générale"),
    ("Contrôleur de gestion", "Indus", "DE", "Frankfurt", "finance excel data_analysis accounting power_bi", "Reporting et budgets"),
    ("Commercial B2B", "Vendor", "FR", "Paris", "sales communication customer_service digital_marketing", "Développement commercial"),
    ("Chargé de recrutement", "TalentHub", "FR", "Paris", "hr communication", "Recrutement et onboarding"),
    ("Responsable Logistique", "Logix", "MA", "Tanger", "logistics project_management excel", "Supply chain et entrepôts"),
    ("UX/UI Designer", "Pixel", "ES", "Madrid", "ux_design graphic_design html_css", "Conception d'interfaces"),
    ("Graphiste", "Studio K", "IT", "Torino", "graphic_design ux_design", "Création visuelle"),
    ("Infirmier(ère)", "Santé Plus", "FR", "Nice", "nursing communication", "Soins hospitaliers"),
    ("Formateur / Enseignant", "EduPro", "MA", "Rabat", "teaching communication", "Formation professionnelle"),
    ("Traducteur arabe-français", "Linguo", "MA", "Casablanca", "arabic_french_translation communication content_writing", "Traduction et localisation"),
    ("مطوّر Python", "Atlas Tech", "MA", "Casablanca", "python sql docker rest_api git", "تطوير واجهات برمجية"),
    ("Développeur PHP / Laravel", "Webforge", "FR", "Rennes", "php sql javascript git html_css", "Sites et applications web"),
    ("Développeur C# .NET", "Nordic Soft", "DE", "Stuttgart", "csharp sql azure rest_api git", "Applications métier .NET"),
    ("Développeur Angular", "Frontier", "IT", "Milano", "angular typescript html_css git testing", "Applications web d'entreprise"),
    ("Développeur Vue.js", "Vuelabs", "ES", "Valencia", "vue javascript html_css git", "Interfaces web réactives"),
    ("Ingénieur Cloud Azure", "Cloudia", "NL", "Rotterdam", "azure terraform cloud linux ci_cd", "Infrastructure Azure"),
    ("Ingénieur Cloud GCP", "Gcloudy", "FR", "Paris", "gcp kubernetes docker terraform cloud", "Plateforme GCP"),
    ("Ingénieur NLP / IA", "Linguaix", "FR", "Grenoble", "nlp python machine_learning deep_learning", "Traitement du langage naturel"),
    ("Data Analyst Tableau", "Insightly", "GB", "London", "tableau sql data_analysis excel statistics", "Reporting décisionnel"),
    ("Ingénieur Big Data", "Datahive", "NL", "Eindhoven", "big_data etl python sql aws", "Plateforme de données"),
    ("Développeur NoSQL / MongoDB", "Docsy", "DE", "Köln", "nosql nodejs javascript rest_api", "Services de données"),
    ("Développeur Python backend", "Medina Tech", "TN", "Tunis", "python fastapi sql docker rest_api git", "API et services backend"),
    ("Développeur Full Stack", "Carthage Digital", "TN", "Sfax", "javascript react nodejs sql git", "Applications web"),
    ("Ingénieur DevOps", "Sahara Cloud", "TN", "Tunis", "docker kubernetes ci_cd linux cloud git", "Automatisation et cloud"),
    ("Data Scientist", "Atlas Data", "MA", "Rabat", "python machine_learning statistics sql", "Modèles prédictifs"),
    ("Développeur Java", "Nile Systems", "EG", "Cairo", "java sql microservices rest_api git", "Applications d'entreprise"),
    ("Chef de projet digital", "Gulf Digital", "AE", "Dubai", "project_management agile digital_marketing communication", "Pilotage de projets digitaux"),
    ("Spécialiste marketing digital", "Riyadh Media", "SA", "Riyadh", "digital_marketing seo content_writing communication", "Campagnes en ligne"),
    ("Ingénieur Cybersécurité", "Emirates Secure", "AE", "Abu Dhabi", "cybersecurity networking audit linux", "Sécurité des systèmes"),
    ("Product Manager", "Swiss Apps", "CH", "Zürich", "agile project_management communication ux_design data_analysis", "Pilotage produit"),
    ("Développeur Backend Java", "Helvetia Bank", "CH", "Genève", "java sql microservices testing ci_cd", "Systèmes bancaires"),
    ("Développeur Python", "Maple Data", "CA", "Montréal", "python sql docker git rest_api", "Services de données"),
    ("Analyste de données", "Northern Insights", "CA", "Toronto", "data_analysis sql power_bi python statistics", "Analyse et visualisation"),
    ("Software Engineer", "Bay Labs", "US", "San Francisco", "python javascript react aws docker", "Produits logiciels"),
    ("Ingénieur DevOps", "Lisboa Cloud", "PT", "Lisbonne", "aws docker kubernetes terraform ci_cd", "Plateforme cloud"),
    ("Responsable e-commerce", "Shopwise", "BE", "Bruxelles", "digital_marketing seo sales data_analysis communication", "Boutique en ligne"),
    ("Gestionnaire RH", "Peopleo", "FR", "Lyon", "hr communication excel", "Administration du personnel"),
    ("Chargé de clientèle", "Relais", "FR", "Toulouse", "customer_service communication sales", "Relation client"),
    ("Responsable supply chain", "Logifreight", "DE", "Hamburg", "logistics project_management excel data_analysis", "Flux logistiques"),
    ("Auditeur financier", "Audix", "FR", "Paris", "audit finance accounting excel", "Audit et conformité"),
    ("Analyste financier", "Capita", "GB", "London", "finance excel data_analysis accounting", "Analyse financière"),
    ("Enseignant / Formateur numérique", "Edulab", "FR", "Nantes", "teaching communication", "Formation aux outils numériques"),
    ("Rédacteur web / Content manager", "Plume", "FR", "Lille", "content_writing seo digital_marketing communication", "Contenus éditoriaux"),
    ("UX Researcher", "Userfirst", "NL", "Amsterdam", "ux_design communication data_analysis", "Recherche utilisateur"),
    ("Designer graphique", "Visuelle", "DE", "Berlin", "graphic_design ux_design", "Création visuelle"),
    ("Technicien réseaux", "Netwise", "ES", "Barcelona", "networking linux cybersecurity", "Réseaux d'entreprise"),
    ("Ingénieur Test / QA", "Qualitas", "TN", "Tunis", "testing python ci_cd git agile", "Automatisation des tests"),
    ("مهندس بيانات", "Najd Data", "SA", "Jeddah", "python sql etl big_data data_analysis", "خطوط معالجة البيانات"),
    ("مسؤول تسويق رقمي", "Khaleej Media", "AE", "Dubai", "digital_marketing seo content_writing", "حملات التسويق الرقمي"),
]

from urllib.parse import quote_plus

from .joblinks import linkedin as _lk

_CITIES = {
    "FR": ["Paris", "Lyon", "Marseille", "Toulouse", "Lille", "Nantes", "Bordeaux", "Nice", "Strasbourg", "Rennes", "Montpellier"],
    "DE": ["Berlin", "München", "Hamburg", "Frankfurt", "Köln", "Stuttgart", "Düsseldorf"],
    "IT": ["Milano", "Roma", "Torino", "Bologna", "Firenze", "Napoli"],
    "ES": ["Madrid", "Barcelona", "Valencia", "Sevilla", "Bilbao"],
    "NL": ["Amsterdam", "Rotterdam", "Utrecht", "Eindhoven"], "BE": ["Bruxelles", "Anvers", "Gand"],
    "CH": ["Zürich", "Genève", "Lausanne", "Bâle"], "GB": ["London", "Manchester", "Edinburgh", "Birmingham"],
    "US": ["New York", "San Francisco", "Austin", "Boston"], "CA": ["Montréal", "Toronto", "Vancouver", "Ottawa"],
    "PT": ["Lisbonne", "Porto"], "MA": ["Casablanca", "Rabat", "Tanger", "Marrakech"], "TN": ["Tunis", "Sfax", "Sousse"],
    "EG": ["Cairo", "Alexandria"], "SA": ["Riyadh", "Jeddah"], "AE": ["Dubai", "Abu Dhabi"],
}
_COMPANIES = ["Acme", "Nova", "Globex", "Datalab", "Initech", "Skyline", "Umbrella", "Orion", "Vertex", "Helios", "Atlas", "Zenith", "Pioneer",
              "Altair", "Nimbus", "Quanta", "Polaris", "Lumen", "Boreal", "Cobalt", "Argon", "Meridian", "Solstice", "Vanguard", "Kappa",
              "Delta Group", "Sigma", "Omega Corp", "Aurora", "Horizon", "Nexus", "Fusion", "Cedar", "Maple", "Olive", "Sahel", "Medina", "Carthage", "Levant", "Gulf"]


def _build() -> list[dict]:
    """Postes types : les offres de base + variantes dans d'autres villes du même pays (plus de choix, aucun filtre sur l'e-mail).
    Seule une offre sur trois a une adresse e-mail de candidature : les autres se postulent via le lien de l'annonce."""
    out, seen = [], set()

    def add(t, c, co, ci, sk, d):
        key = (t, ci, c)
        if key in seen:
            return
        seen.add(key)
        n = len(out)
        email = f"jobs{n + 1}@{c.lower().replace(' ', '').replace('+', 'plus')}.example" if n % 3 == 0 else ""
        out.append({"title": t, "company": c, "country": co, "city": ci, "skills": sk, "description": d,
                    "url": _lk(t, ci, co) + "#" + quote_plus(f"{c}-{ci}".lower()), "email": email})

    for t, c, co, ci, sk, d in _J:
        add(t, c, co, ci, sk, d)
    for i, (t, c, co, ci, sk, d) in enumerate(_J):
        pool = [x for x in _CITIES.get(co, []) if x != ci]
        for j, city in enumerate(pool[:2] if len(pool) >= 2 else pool):
            add(t, _COMPANIES[(i * 3 + j * 7 + 1) % len(_COMPANIES)], co, city, sk, d)
    return out


SEED_JOBS = _build()
