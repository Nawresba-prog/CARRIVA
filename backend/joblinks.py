"""Liens d'emploi : ouvre une RECHERCHE EN DIRECT (poste + ville) sur des plateformes réelles et sur le portail public du pays.

Aucune annonce n'est inventée : les offres du catalogue de démonstration sont des « postes types », et ces liens mènent aux annonces
réelles correspondantes. Pour les offres réellement importées (n8n / scraping), l'URL d'origine est ajoutée en premier.
"""
from __future__ import annotations

from urllib.parse import quote_plus

_INDEED = {"FR": "fr", "DE": "de", "IT": "it", "ES": "es", "NL": "nl", "BE": "be", "GB": "uk", "CA": "ca", "MA": "ma", "TN": "tn", "EG": "eg",
           "SA": "sa", "AE": "ae", "CH": "ch", "PT": "pt", "DZ": "dz", "US": "www"}
EU = {"FR", "DE", "IT", "ES", "NL", "BE", "PT"}


def _country_name(iso: str) -> str:
    try:
        from .processing import COUNTRIES
        return COUNTRIES[iso.upper()][1]
    except Exception:  # noqa: BLE001 — code inconnu : on garde le code tel quel
        return iso


def linkedin(title: str, city: str = "", country: str = "") -> str:
    loc = ", ".join(x for x in (city, _country_name(country) if country else "") if x)
    return f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(title)}&location={quote_plus(loc)}"


def indeed(title: str, city: str = "", country: str = "") -> str:
    sub = _INDEED.get(country.upper(), "www")
    return f"https://{sub}.indeed.com/jobs?q={quote_plus(title)}&l={quote_plus(city)}"


def official_portals(title: str, city: str, country: str) -> list[dict]:
    q, loc, c = quote_plus(title), quote_plus(city), country.upper()
    out: list[dict] = []
    if c == "FR":
        out += [{"name": "France Travail", "url": f"https://candidat.francetravail.fr/offres/recherche?motsCles={q}"},
                {"name": "Welcome to the Jungle", "url": f"https://www.welcometothejungle.com/fr/jobs?query={q}&aroundQuery={loc}"}]
    elif c == "DE":
        out.append({"name": "Bundesagentur für Arbeit", "url": f"https://www.arbeitsagentur.de/jobsuche/suche?was={q}&wo={loc}"})
    elif c == "ES":
        out.append({"name": "InfoJobs", "url": f"https://www.infojobs.net/jobsearch/search-results/list.xhtml?keyword={q}&provinceIds="})
    elif c == "MA":
        out.append({"name": "ANAPEC", "url": "https://www.anapec.org/"})
    elif c == "TN":
        out.append({"name": "Emploi.nat.tn (ANETI)", "url": "https://www.emploi.nat.tn/"})
    elif c == "DZ":
        out.append({"name": "ANEM", "url": "https://www.anem.dz/"})
    if c in EU:
        out.append({"name": "EURES (portail européen)", "url": "https://eures.europa.eu/index_en"})
    return out


def for_job(job: dict) -> list[dict]:
    """Liens d'une offre : [{name, url}], l'URL d'origine d'abord si elle est réelle (http/https), puis recherches en direct."""
    title, city, country = job.get("title", ""), job.get("city", ""), job.get("country", "")
    links: list[dict] = []
    origin = str(job.get("url", ""))
    if job.get("source") not in ("seed", "catalog", None) and origin.startswith(("https://", "http://")):
        links.append({"name": "Offre d'origine", "url": origin})
    links += [{"name": "LinkedIn", "url": linkedin(title, city, country)}, {"name": "Indeed", "url": indeed(title, city, country)}]
    links += official_portals(title, city, country)
    return links
