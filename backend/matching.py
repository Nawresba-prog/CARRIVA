"""Appariement CV <-> offres / formations par compétences.

Pourquoi : un embedding de repli (hachage) n'a aucun sens sémantique. On extrait donc des compétences
canoniques (taxonomie FR/EN/AR de base) du CV, des offres et des formations, puis on classe par couverture.
La recherche vectorielle (Qdrant hybride) fournit les candidats, ce module les re-classe et explique le résultat
(compétences en commun / manquantes). En production : ESCO/O*NET + embeddings multilingues.
"""
from __future__ import annotations

import re
import unicodedata

# canonique -> alias (déjà en minuscules, sans accents). Les alias multi-mots sont reconnus comme expressions.
TAXONOMY: dict[str, list[str]] = {
    "python": ["python", "django", "flask", "pandas"],
    "javascript": ["javascript", "js", "ecmascript"],
    "typescript": ["typescript"],
    "java": ["java", "spring", "spring boot"],
    "csharp": ["c#", "csharp", "dotnet", ".net"],
    "php": ["php", "laravel", "symfony"],
    "sql": ["sql", "mysql", "postgresql", "postgres", "oracle", "sql server"],
    "nosql": ["nosql", "mongodb", "redis", "elasticsearch"],
    "html_css": ["html", "css", "html5", "css3", "sass"],
    "react": ["react", "reactjs", "react.js", "nextjs"],
    "angular": ["angular"],
    "vue": ["vue", "vuejs"],
    "nodejs": ["nodejs", "node.js", "node", "express"],
    "fastapi": ["fastapi"],
    "rest_api": ["api", "apis", "rest", "restful", "api rest", "graphql"],
    "microservices": ["microservices", "microservice"],
    "docker": ["docker", "conteneurs", "containers"],
    "kubernetes": ["kubernetes", "k8s", "helm"],
    "terraform": ["terraform", "ansible", "infrastructure as code", "iac"],
    "ci_cd": ["ci/cd", "cicd", "ci cd", "jenkins", "gitlab ci", "github actions", "integration continue"],
    "aws": ["aws", "amazon web services"],
    "azure": ["azure"],
    "gcp": ["gcp", "google cloud"],
    "cloud": ["cloud", "nuage"],
    "linux": ["linux", "unix", "bash", "shell"],
    "git": ["git", "github", "gitlab"],
    "testing": ["tests", "testing", "test automation", "selenium", "pytest", "qa", "assurance qualite", "tests automatises"],
    "cybersecurity": ["cybersecurite", "cybersecurity", "securite informatique", "security", "pentest", "securite"],
    "networking": ["reseau", "reseaux", "network", "networking", "tcp/ip", "cisco"],
    "machine_learning": ["machine learning", "ml", "apprentissage automatique", "scikit-learn", "sklearn", "data science"],
    "deep_learning": ["deep learning", "tensorflow", "pytorch", "apprentissage profond", "reseaux de neurones"],
    "nlp": ["nlp", "traitement du langage", "llm", "langchain", "rag", "ia generative"],
    "data_analysis": ["analyse de donnees", "data analysis", "analyse de donnee", "analytics", "data analyst", "analyste de donnees"],
    "statistics": ["statistiques", "statistics", "statistique", "probabilites"],
    "power_bi": ["power bi", "powerbi"],
    "tableau": ["tableau"],
    "excel": ["excel", "tableur", "vba"],
    "etl": ["etl", "data pipeline", "pipelines de donnees", "airflow", "data engineering"],
    "big_data": ["big data", "spark", "hadoop", "kafka"],
    "project_management": ["gestion de projet", "gestion de projets", "chef de projet", "project management", "project manager", "pmp", "prince2"],
    "agile": ["agile", "scrum", "kanban", "product owner"],
    "digital_marketing": ["marketing digital", "digital marketing", "google ads", "sem", "social media", "reseaux sociaux", "community management", "community manager", "growth"],
    "seo": ["seo", "referencement", "referencement naturel"],
    "content_writing": ["redaction", "content writing", "copywriting", "creation de contenu", "redacteur"],
    "communication": ["communication", "relations publiques", "presentation"],
    "accounting": ["comptabilite", "accounting", "comptable", "bookkeeping", "bilan"],
    "finance": ["finance", "analyse financiere", "controle de gestion", "budget", "tresorerie"],
    "audit": ["audit", "auditeur", "conformite", "compliance"],
    "sales": ["vente", "ventes", "commercial", "sales", "negociation", "prospection", "business development"],
    "customer_service": ["service client", "relation client", "customer service", "support client", "customer success"],
    "hr": ["rh", "ressources humaines", "recrutement", "hr", "talent acquisition", "paie"],
    "logistics": ["logistique", "supply chain", "logistics", "approvisionnement", "gestion de stock"],
    "ux_design": ["ux", "ui", "ux/ui", "figma", "design d'interface", "experience utilisateur", "user experience"],
    "graphic_design": ["graphisme", "graphic design", "photoshop", "illustrator", "infographie", "design graphique"],
    "nursing": ["infirmier", "infirmiere", "soins infirmiers", "nursing", "soins"],
    "teaching": ["enseignement", "enseignant", "pedagogie", "teaching", "formateur", "formation d'adultes"],
    "arabic_french_translation": ["traduction", "translation", "interpretariat", "traducteur"],
}

# mots d'intitulé -> compétence implicite (un « développeur python » connaît python)
_ALIAS_INDEX: list[tuple[str, str]] = sorted(
    ((f" {a} ", canon) for canon, aliases in TAXONOMY.items() for a in aliases), key=lambda x: -len(x[0])
)


_TITLE_STOP = {"charge", "chargee", "responsable", "ingenieur", "chef", "manager", "specialiste", "assistant", "technicien", "senior", "junior", "expert", "agent"}


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKD", str(text or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9#+./؀-ۿ' ]", " ", t)
    t = re.sub(r"(?<=[a-z0-9#+])[./]+(?= |$)", "", t)  # « FastAPI. » / « docker/ » : ponctuation finale de mot
    t = re.sub(r"\s+", " ", t).strip()
    return f" {t} "


def extract_skills(*texts: str) -> list[str]:
    """Compétences canoniques détectées dans un ou plusieurs textes (ordre de première apparition)."""
    blob = normalize(" . ".join(t for t in texts if t))
    found: dict[str, int] = {}
    for alias, canon in _ALIAS_INDEX:
        pos = blob.find(alias)
        if pos != -1 and (canon not in found or pos < found[canon]):
            found[canon] = pos
    return sorted(found, key=found.get)


def label(skill: str) -> str:
    return skill.replace("_", " ")


def score_job(cv_skills: set[str], cv_titles_norm: str, job: dict) -> dict:
    req = set(str(job.get("skills", "")).split())
    if not req:
        return {"score": 0.0, "matched": [], "missing": []}
    matched = sorted(req & cv_skills)
    missing = sorted(req - cv_skills)
    coverage = len(matched) / len(req)
    job_title_tokens = [w for w in normalize(job.get("title", "")).split() if len(w) > 3 and w not in _TITLE_STOP]
    title_hit = any(f" {w}" in cv_titles_norm for w in job_title_tokens) if job_title_tokens else False
    # la couverture de compétences domine ; l'intitulé départage ; pas de recouvrement => score nul
    score = 0.0 if not matched and not title_hit else 0.8 * coverage + 0.2 * (1.0 if title_hit else 0.0)
    return {"score": round(score, 3), "matched": matched, "missing": missing}


def rank_jobs(cv_skills: list[str], cv_titles: str, candidates: list[dict], k: int, min_score: float = 0.15) -> list[dict]:
    cs, tn = set(cv_skills), normalize(cv_titles)
    out = []
    for pos, job in enumerate(candidates):
        r = score_job(cs, tn, job)
        r["score"] = round(r["score"] + 0.02 * (1 - pos / max(len(candidates), 1)), 3) if r["score"] else 0.0  # léger bonus rang vectoriel
        if r["score"] >= min_score:
            out.append({**job, **r})
    out.sort(key=lambda j: -j["score"])
    return out[:k]


def find_gaps(top_jobs: list[dict], limit: int = 8) -> list[str]:
    """Compétences manquantes pour les 2 offres les plus proches du profil, classées par fréquence."""
    freq: dict[str, int] = {}
    for j in top_jobs[:2]:
        for s in j.get("missing", []):
            freq[s] = freq.get(s, 0) + 1
    return [s for s, _ in sorted(freq.items(), key=lambda x: (-x[1], x[0]))][:limit]


def rank_trainings(gaps: list[str], candidates: list[dict], k: int) -> list[dict]:
    g = set(gaps)
    out = []
    for t in candidates:
        covered = sorted(set(str(t.get("skills", "")).split()) & g)
        if covered:
            out.append({**t, "covers": covered, "score": round(len(covered) / len(g), 3)})
    out.sort(key=lambda t: (-len(t["covers"]), t.get("title", "")))
    return out[:k]
