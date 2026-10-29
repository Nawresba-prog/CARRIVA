"""Complétion contextuelle du CV : renseigne les champs manquants à partir de ce que l'utilisateur a DÉJÀ fourni.

Principe : on complète ce qui se déduit raisonnablement du contexte (ville -> pays, indicatif -> pays, intitulé -> missions
usuelles, textes -> compétences, diplôme -> niveau CEC, pays -> langue probable). On n'invente JAMAIS un fait vérifiable :
employeur, diplôme, établissement, date, chiffre, résultat. Chaque valeur ajoutée est signalée dans le rapport
(champs « filled_* ») pour que l'utilisateur puisse la corriger. La fonction est idempotente.
"""
from __future__ import annotations

import re
from datetime import date

from . import matching
from .processing import (COUNTRIES, DIAL, LANGUAGES, _fold, auto_summary, country_iso, language_display, skills_clean,
                         years_of_experience)

# --------------------------------------------------------------------------- ville -> pays
_CITY_ISO = {
    "tunis": "TN", "sfax": "TN", "sousse": "TN", "bizerte": "TN", "nabeul": "TN", "monastir": "TN", "ariana": "TN",
    "paris": "FR", "lyon": "FR", "marseille": "FR", "toulouse": "FR", "lille": "FR", "nantes": "FR", "bordeaux": "FR", "nice": "FR", "strasbourg": "FR",
    "berlin": "DE", "munich": "DE", "hamburg": "DE", "frankfurt": "DE", "cologne": "DE", "stuttgart": "DE",
    "rome": "IT", "milan": "IT", "turin": "IT", "naples": "IT", "bologna": "IT", "florence": "IT",
    "madrid": "ES", "barcelona": "ES", "barcelone": "ES", "valencia": "ES", "seville": "ES",
    "london": "GB", "londres": "GB", "manchester": "GB", "edinburgh": "GB",
    "new york": "US", "san francisco": "US", "boston": "US", "chicago": "US", "los angeles": "US",
    "casablanca": "MA", "rabat": "MA", "marrakech": "MA", "tanger": "MA", "fes": "MA",
    "alger": "DZ", "algiers": "DZ", "oran": "DZ", "constantine": "DZ",
    "le caire": "EG", "cairo": "EG", "alexandrie": "EG", "alexandria": "EG",
    "riyadh": "SA", "riyad": "SA", "jeddah": "SA", "djeddah": "SA",
    "dubai": "AE", "abu dhabi": "AE", "sharjah": "AE",
    "bruxelles": "BE", "brussels": "BE", "anvers": "BE", "geneve": "CH", "geneva": "CH", "zurich": "CH", "lausanne": "CH",
    "montreal": "CA", "toronto": "CA", "ottawa": "CA", "vancouver": "CA",
    "amsterdam": "NL", "rotterdam": "NL", "lisbonne": "PT", "lisbon": "PT", "porto": "PT",
}
_ISO_LANG = {"FR": "fr", "DE": "de", "IT": "it", "ES": "es", "GB": "en", "US": "en", "MA": "ar", "DZ": "ar", "TN": "ar", "EG": "ar",
             "SA": "ar", "AE": "ar", "PT": "pt", "NL": "nl"}  # BE / CH / CA : plusieurs langues -> pas de supposition
_DIAL_ISO = {v: k for k, v in reversed(list(DIAL.items())) if k not in ("CA",)}  # +1 -> US par défaut ; ambiguïtés levées au mieux

# --------------------------------------------------------------------------- missions usuelles par famille de métier
# (mots-clés dans l'intitulé) -> {langue: [puces]} ; formulation générique, sans chiffres ni employeur.
_ROLES: list[tuple[tuple[str, ...], dict[str, list[str]]]] = [
    (("developpeu", "developer", "programmeu", "ingenieur logiciel", "software", "full stack", "fullstack", "backend", "frontend"), {
        "fr": ["Conception et développement de fonctionnalités logicielles", "Rédaction de tests et revue de code", "Maintenance et amélioration des applications existantes"],
        "en": ["Designed and developed software features", "Wrote tests and took part in code reviews", "Maintained and improved existing applications"]}),
    (("data", "donnees", "analyste", "analyst", "bi "), {
        "fr": ["Collecte, nettoyage et analyse de données", "Construction de tableaux de bord et de rapports", "Présentation des résultats aux équipes métier"],
        "en": ["Collected, cleaned and analysed data", "Built dashboards and reports", "Presented findings to business teams"]}),
    (("devops", "sre", "administrateur systeme", "sysadmin", "cloud"), {
        "fr": ["Déploiement et supervision d'infrastructures", "Automatisation des livraisons et de la configuration", "Suivi de la disponibilité et des incidents"],
        "en": ["Deployed and monitored infrastructure", "Automated delivery pipelines and configuration", "Tracked availability and handled incidents"]}),
    (("chef de projet", "project manager", "product owner", "scrum", "responsable de projet"), {
        "fr": ["Pilotage de projets : planning, budget et suivi des risques", "Coordination des équipes et des parties prenantes", "Suivi de l'avancement et reporting"],
        "en": ["Led projects: planning, budget and risk tracking", "Coordinated teams and stakeholders", "Monitored progress and reported status"]}),
    (("manager", "directeur", "director", "responsable", "head of", "superviseur"), {
        "fr": ["Encadrement et animation d'une équipe", "Définition des objectifs et suivi des résultats", "Coordination avec les autres services"],
        "en": ["Managed and coached a team", "Set objectives and tracked results", "Coordinated with other departments"]}),
    (("marketing", "communication", "community", "social media", "seo"), {
        "fr": ["Élaboration et mise en œuvre d'actions de communication", "Animation des canaux digitaux", "Analyse des performances des campagnes"],
        "en": ["Planned and ran communication activities", "Managed digital channels", "Analysed campaign performance"]}),
    (("commercial", "vente", "sales", "business developer", "account"), {
        "fr": ["Prospection et développement du portefeuille clients", "Négociation et suivi des offres commerciales", "Fidélisation de la clientèle"],
        "en": ["Prospected and grew the client portfolio", "Negotiated and followed up commercial offers", "Built long-term customer relationships"]}),
    (("comptab", "accountant", "finance", "audit", "controleur"), {
        "fr": ["Tenue de la comptabilité et des écritures courantes", "Préparation des clôtures et des déclarations", "Contrôle et suivi des budgets"],
        "en": ["Kept the books and recorded daily entries", "Prepared period-end closings and filings", "Monitored and controlled budgets"]}),
    (("ressources humaines", "rh", "human resources", "recrut", "talent"), {
        "fr": ["Recrutement et intégration des collaborateurs", "Gestion administrative du personnel", "Accompagnement des managers et des équipes"],
        "en": ["Recruited and onboarded staff", "Handled personnel administration", "Supported managers and teams"]}),
    (("design", "graphiste", "ux", "ui "), {
        "fr": ["Conception de maquettes et d'interfaces", "Création de supports visuels cohérents", "Recueil des retours utilisateurs et itérations"],
        "en": ["Designed mock-ups and interfaces", "Created consistent visual assets", "Gathered user feedback and iterated"]}),
    (("enseignant", "professeur", "teacher", "formateur", "trainer", "instituteur"), {
        "fr": ["Préparation et animation de cours ou de formations", "Évaluation et suivi des progrès des apprenants", "Adaptation des méthodes aux publics"],
        "en": ["Prepared and delivered lessons or training", "Assessed and tracked learners' progress", "Adapted methods to different audiences"]}),
    (("infirmier", "nurse", "medecin", "doctor", "aide soignant", "pharmac"), {
        "fr": ["Prise en charge et suivi des patients", "Application des protocoles de soins et d'hygiène", "Collaboration avec l'équipe médicale"],
        "en": ["Cared for and monitored patients", "Applied care and hygiene protocols", "Worked with the medical team"]}),
    (("assistant", "secretaire", "administratif", "administrative", "office"), {
        "fr": ["Gestion de l'agenda, du courrier et des appels", "Préparation et classement de documents", "Appui administratif aux équipes"],
        "en": ["Managed calendars, mail and calls", "Prepared and filed documents", "Provided administrative support to teams"]}),
    (("support", "helpdesk", "service client", "customer", "conseiller"), {
        "fr": ["Accueil et traitement des demandes des clients", "Résolution des incidents et suivi jusqu'à clôture", "Documentation des solutions apportées"],
        "en": ["Handled customer requests", "Resolved incidents and followed up to closure", "Documented the solutions provided"]}),
    (("stagiaire", "intern", "stage", "apprenti", "alternan", "trainee"), {
        "fr": ["Participation aux missions de l'équipe sous la supervision d'un tuteur", "Réalisation de tâches opérationnelles et de suivi", "Montée en compétences sur les outils utilisés"],
        "en": ["Contributed to team assignments under a tutor's supervision", "Carried out operational and follow-up tasks", "Built skills on the tools in use"]}),
]
_GENERIC = {"fr": ["Réalisation des missions liées au poste", "Collaboration avec les équipes et suivi des tâches"],
            "en": ["Carried out the duties of the role", "Collaborated with teams and tracked tasks"]}

# --------------------------------------------------------------------------- niveau CEC (EQF) d'après l'intitulé du diplôme
_EQF = [(("doctorat", "phd", "doctorate"), "8"), (("master", "ingenieur", "engineer", "mastere", "msc", "mba", "magister"), "7"),
        (("licence", "bachelor", "bsc", "laurea", "grado"), "6"), (("bts", "dut", "but ", "deug", "associate", "technicien superieur", "diplome universitaire"), "5"),
        (("baccalaureat", "bac ", "abitur", "high school", "lycee", "maturita", "technicien"), "4"), (("cap", "bep", "certificat d aptitude"), "3")]


def _has(s: str, kw: str) -> bool:
    kw = kw.strip()
    return bool(re.search(r"\b" + re.escape(kw) + (r"\b" if len(kw) <= 4 else ""), s))


def _eqf(degree: str) -> str:
    s = _fold(degree)
    for keys, lvl in _EQF:
        if any(_has(s, k) for k in keys):
            return lvl
    return ""


def _role_bullets(title: str, lang: str) -> list[str]:
    s = _fold(title)
    for keys, tpl in _ROLES:
        if any(_has(s, k) for k in keys):
            return tpl.get(lang, tpl["en"])
    return _GENERIC.get(lang, _GENERIC["en"])


def _skill_label(key: str) -> str:
    return "C#" if key == "csharp" else (skills_clean([matching.label(key)]) or [matching.label(key)])[0]


# --------------------------------------------------------------------------- point d'entrée
def enrich(d: dict, lang: str = "fr", today: date | None = None) -> tuple[dict, list[dict]]:
    """d : CV déjà traité par processing.process_cv. -> (CV complété, rapport [{field, ref, before:'', after}])."""
    today = today or date.today()
    lang = lang if lang in ("fr", "en", "de", "it", "es", "ar") else "en"
    tl = lang if lang in ("fr", "en") else "en"  # gabarits de texte disponibles
    out = {**d, "experiences": [dict(e) for e in d.get("experiences", [])], "education": [dict(e) for e in d.get("education", [])]}
    ch: list[dict] = []

    def add(field: str, after, ref: str = "") -> None:
        a = ", ".join(after) if isinstance(after, list) else str(after)
        if a.strip() and len(ch) < 40:
            ch.append({"field": "filled_" + field, "ref": ref, "before": "", "after": a})

    # pays : ville connue, sinon indicatif téléphonique
    if not out["country"]:
        iso = _CITY_ISO.get(_fold(out["city"]), "")
        if not iso and out["phone"].startswith("+"):
            digits = out["phone"][1:].replace(" ", "")
            cc = next((c for c in sorted(_DIAL_ISO, key=len, reverse=True) if digits.startswith(c)), "")
            iso = _DIAL_ISO.get(cc, "")
        if iso:
            out["country"] = COUNTRIES[iso][1]
            add("country", out["country"])
    iso = country_iso(out["country"])

    # langue maternelle probable d'après le pays (uniquement si rien n'est renseigné)
    if not out["mother_tongue"] and not out.get("languages") and iso in _ISO_LANG:
        out["mother_tongue"] = LANGUAGES[_ISO_LANG[iso]][1]
        add("mother_tongue", language_display(out["mother_tongue"], lang))

    # compétences (avant les missions générées, pour ne déduire que de la saisie réelle) : celles que révèlent les intitulés, missions, diplômes et résumé
    if len(out["skills"]) < 8:
        text = [out["summary"]] + [f"{e['title']} {e['description']}" for e in out["experiences"]] + [e["degree"] for e in out["education"]]
        have = {_fold(s) for s in out["skills"]}
        new = [lab for lab in (_skill_label(k) for k in matching.extract_skills(*text)) if _fold(lab) not in have][: 12 - len(out["skills"])]
        if new:
            out["skills"] = out["skills"] + new
            add("skills", new)

    # expériences : pays du poste, missions usuelles si aucune description
    for e in out["experiences"]:
        if not e["country"] and out["country"] and (not e["city"] or _fold(e["city"]) == _fold(out["city"])):
            e["country"] = out["country"]
        if not e["description"] and e["title"]:
            e["description"] = "\n".join("• " + b + "." for b in _role_bullets(e["title"], tl))
            add("description", e["description"].replace("\n", " "), e["title"])

    # formations : pays, niveau CEC déduit du diplôme
    for e in out["education"]:
        if not e["country"] and out["country"] and (not e["city"] or _fold(e["city"]) == _fold(out["city"])):
            e["country"] = out["country"]
        if not e["level"]:
            lvl = _eqf(e["degree"])
            if lvl:
                e["level"] = lvl
                add("level", f"CEC {lvl}", e["degree"])

    # résumé : généré, ou étoffé s'il est trop court
    if len(out["summary"]) < 60:
        base = out["summary"]
        gen = auto_summary(out, lang, today)
        extra = ""
        exps, edus = out["experiences"], out["education"]
        if edus and edus[0]["degree"] and tl == "fr" and lang == "fr":
            extra = f"Formation : {edus[0]['degree']}" + (f" ({edus[0]['school']})" if edus[0]["school"] else "") + "."
        elif edus and edus[0]["degree"] and lang == "en":
            extra = f"Education: {edus[0]['degree']}" + (f" ({edus[0]['school']})" if edus[0]["school"] else "") + "."
        if lang == "fr" and out["languages"]:
            extra += " Langues : " + ", ".join(f"{l['name']} ({l['level']})" for l in out["languages"][:3]) + "."
        elif lang == "en" and out["languages"]:
            extra += " Languages: " + ", ".join(f"{l['name']} ({l['level']})" for l in out["languages"][:3]) + "."
        parts = [p for p in (base if base.endswith((".", "!", "?")) or not base else base + ".", gen, extra.strip()) if p]
        new = " ".join(parts).strip()
        if new and new != base and (exps or edus or out["skills"]):
            out["summary"] = new
            add("summary", new)
    return out, ch


def process_and_enrich(cv: dict, lang: str = "fr", today: date | None = None) -> tuple[dict, list[dict]]:
    from .processing import process_cv

    data, changes = process_cv(cv, today)
    data, filled = enrich(data, lang, today)
    return data, changes + filled
