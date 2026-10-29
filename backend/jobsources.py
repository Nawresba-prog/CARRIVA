"""Vraies offres d'emploi via des API publiques (aucune offre inventée).

Fournisseurs :
- Adzuna (clé gratuite ADZUNA_APP_ID / ADZUNA_APP_KEY) : FR, DE, IT, ES, GB, US, NL, BE, CH, CA, AT, PL, AU, … recherche par mots-clés + ville.
- France Travail (FT_CLIENT_ID / FT_CLIENT_SECRET) : offres officielles en France, toutes villes.
- Arbeitnow (sans clé) : offres en Allemagne / Europe, filtrées localement.
- Remotive (sans clé) : offres en télétravail dans le monde.
Pas d'API gratuite pour MA/TN/DZ/pays du Golfe : le service renvoie alors 0 offre pour ce pays et l'interface propose les liens de recherche en direct.
Le transport HTTP est injectable (tests sans réseau). Un échec d'un fournisseur n'empêche pas les autres ; chaque statut est renvoyé.
"""
from __future__ import annotations

import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ADZUNA_CC = {"FR": "fr", "DE": "de", "IT": "it", "ES": "es", "GB": "gb", "US": "us", "NL": "nl", "BE": "be", "CH": "ch", "CA": "ca",
             "AT": "at", "PL": "pl", "AU": "au", "NZ": "nz", "BR": "br", "IN": "in", "MX": "mx", "SG": "sg", "ZA": "za"}
TTL = int(os.getenv("JOBS_CACHE_TTL", "900"))
_CACHE: dict[tuple, tuple[float, list]] = {}
_TOKEN: dict[str, tuple[float, str]] = {}


def http_json(url: str, headers: dict | None = None, data: dict | None = None, timeout: float = 8.0) -> dict:
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers={"User-Agent": "carriva/1.0", "Accept": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 — URLs construites ici (https)
        return json.loads(r.read().decode("utf-8", "replace"))


def clean(text: object, limit: int = 1500) -> str:
    t = re.sub(r"<[^>]+>", " ", html.unescape(str(text or "")))
    return re.sub(r"\s+", " ", t).strip()[:limit]


def _job(title, company, country, city, desc, url, source, posted="") -> dict | None:
    url = str(url or "")
    if not title or not url.startswith(("https://", "http://")):
        return None
    return {"title": clean(title, 160), "company": clean(company, 120) or "—", "country": country, "city": clean(city, 80), "skills": "",
            "description": clean(desc), "url": url, "email": "", "source": source, "posted": str(posted)[:10]}


def adzuna(q, iso, city, get=http_json, **_):
    app_id, key = os.getenv("ADZUNA_APP_ID"), os.getenv("ADZUNA_APP_KEY")
    if not (app_id and key):
        raise RuntimeError("clé manquante (ADZUNA_APP_ID / ADZUNA_APP_KEY)")
    ccs = [ADZUNA_CC[iso]] if iso in ADZUNA_CC else []
    if not ccs:
        raise RuntimeError("pays non couvert")
    out = []
    for cc in ccs:
        p = {"app_id": app_id, "app_key": key, "results_per_page": 50, "what": q, "content-type": "application/json"}
        if city:
            p["where"] = city
        d = get(f"https://api.adzuna.com/v1/api/jobs/{cc}/search/1?" + urllib.parse.urlencode(p))
        for r in d.get("results", []):
            j = _job(r.get("title"), (r.get("company") or {}).get("display_name"), iso, (r.get("location") or {}).get("display_name", ""),
                     r.get("description"), r.get("redirect_url"), "adzuna", r.get("created"))
            if j:
                out.append(j)
    return out


def france_travail(q, iso, city, get=http_json, **_):
    cid, sec = os.getenv("FT_CLIENT_ID"), os.getenv("FT_CLIENT_SECRET")
    if not (cid and sec):
        raise RuntimeError("clé manquante (FT_CLIENT_ID / FT_CLIENT_SECRET)")
    if iso not in ("FR", ""):
        raise RuntimeError("France uniquement")
    tok = _TOKEN.get("ft")
    if not tok or tok[0] < time.time():
        r = get("https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire",
                data={"grant_type": "client_credentials", "client_id": cid, "client_secret": sec, "scope": "api_offresdemploiv2 o2dsoffre"})
        tok = (time.time() + int(r.get("expires_in", 1200)) - 60, r["access_token"]); _TOKEN["ft"] = tok
    p = {"motsCles": q, "range": "0-99"}
    d = get("https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search?" + urllib.parse.urlencode(p), headers={"Authorization": "Bearer " + tok[1]})
    out = []
    for r in d.get("resultats", []):
        loc = (r.get("lieuTravail") or {}).get("libelle", "")  # « 75 - PARIS 08 »
        town = re.sub(r"^\d+\s*-\s*", "", loc).title()
        if city and city.lower() not in loc.lower():
            continue
        url = ((r.get("origineOffre") or {}).get("urlOrigine")) or f"https://candidat.francetravail.fr/offres/recherche/detail/{r.get('id')}"
        j = _job(r.get("intitule"), (r.get("entreprise") or {}).get("nom"), "FR", town, r.get("description"), url, "francetravail", r.get("dateCreation"))
        if j:
            out.append(j)
    return out


def _match_local(job: dict, q: str, city: str) -> bool:
    toks = [w for w in re.findall(r"\w{3,}", q.lower())]
    hay = f"{job['title']} {job['description']}".lower()
    if toks and not any(t in hay for t in toks):
        return False
    return not city or city.lower() in job["city"].lower()


def arbeitnow(q, iso, city, get=http_json, **_):
    if iso not in ("DE", "AT", "CH", ""):
        raise RuntimeError("Allemagne / Autriche / Suisse uniquement")
    out = []
    for page in (1, 2, 3):
        d = get(f"https://www.arbeitnow.com/api/job-board-api?page={page}")
        for r in d.get("data", []):
            j = _job(r.get("title"), r.get("company_name"), "DE", r.get("location", ""), r.get("description"), r.get("url"), "arbeitnow",
                     time.strftime("%Y-%m-%d", time.gmtime(r["created_at"])) if isinstance(r.get("created_at"), (int, float)) else "")
            if j and _match_local(j, q, city):
                out.append(j)
    return out


def remotive(q, iso, city, get=http_json, **_):
    if city:
        raise RuntimeError("télétravail : pas de ville")
    d = get("https://remotive.com/api/remote-jobs?" + urllib.parse.urlencode({"search": q, "limit": 40}))
    out = []
    for r in d.get("jobs", []):
        j = _job(r.get("title"), r.get("company_name"), iso or "", "Remote / " + clean(r.get("candidate_required_location"), 40), r.get("description"),
                 r.get("url"), "remotive", r.get("publication_date"))
        if j:
            out.append(j)
    return out


PROVIDERS = {"adzuna": adzuna, "francetravail": france_travail, "arbeitnow": arbeitnow, "remotive": remotive}


def fetch(q: str, iso: str = "", city: str = "", get=http_json, providers: dict | None = None, use_cache: bool = True) -> tuple[list[dict], dict]:
    """(offres dédoublonnées, statut par fournisseur). Jamais d'exception : un fournisseur en échec est signalé dans le statut."""
    q, iso, city = (q or "").strip(), (iso or "").upper(), (city or "").strip()
    key = (q.lower(), iso, city.lower())
    if use_cache and providers is None and key in _CACHE and _CACHE[key][0] > time.time():
        return _CACHE[key][1][0], _CACHE[key][1][1]
    prov = providers or PROVIDERS

    def run(item):
        name, fn = item
        try:
            r = fn(q, iso, city, get=get)
            return name, r, {"ok": True, "count": len(r)}
        except Exception as e:  # noqa: BLE001 — chaque fournisseur est indépendant
            return name, [], {"ok": False, "count": 0, "reason": str(e)[:120]}

    with ThreadPoolExecutor(max_workers=len(prov) or 1) as ex:
        res = list(ex.map(run, prov.items()))
    seen, jobs, status = set(), [], {}
    for name, r, st in res:
        status[name] = st
        for j in r:
            k = (j["title"].lower(), j["company"].lower(), j["city"].lower())
            if j["url"] not in seen and k not in seen:
                seen.add(j["url"]); seen.add(k); jobs.append(j)
    if providers is None:
        _CACHE[key] = (time.time() + TTL, (jobs, status))
    return jobs, status
