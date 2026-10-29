"""WF-2 n8n : alertes d'offres (matching quotidien) pour les utilisateurs qui l'ont demandé.

Principe : l'utilisateur s'abonne (consentement explicite) ; on ne conserve que son PROFIL DÉRIVÉ (compétences canoniques, intitulés,
pays/ville, seuil), jamais le CV complet. n8n déclenche `POST /internal/matching/run` ; le backend renvoie une liste plate de
correspondances nouvelles (une ligne = un utilisateur x une offre), que n8n filtre (score) puis notifie.
Production : remplacer le dictionnaire par une table SQL.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from . import matching

DEFAULT_MIN_SCORE = 0.6
MAX_NOTIFIED = 500  # mémoire des offres déjà signalées, par abonné


def make_alert(user: str, cv_skills: list[str], titles: str, country: str | None, city: str | None, min_score: float,
               lang: str, email: str) -> dict:
    return {"user": user, "skills": sorted(set(cv_skills)), "titles": titles[:600], "country": (country or "").upper() or None,
            "city": city or None, "min_score": float(min_score), "lang": lang, "email": email,
            "created_at": datetime.now(timezone.utc).isoformat(), "notified": [], "last_run": None}


def public_view(a: dict) -> dict:
    return {k: a[k] for k in ("skills", "country", "city", "min_score", "lang", "created_at", "last_run")} | {"notified_count": len(a["notified"])}


def _line(a: dict, j: dict) -> dict:
    loc = ", ".join(x for x in (j.get("city"), j.get("country")) if x)
    return {"user": a["user"], "email": a["email"], "lang": a["lang"], "title": j.get("title", ""), "company": j.get("company", ""),
            "url": j["url"], "country": j.get("country", ""), "city": j.get("city", ""), "score": j["score"],
            "matched": [matching.label(s) for s in j.get("matched", [])], "missing": [matching.label(s) for s in j.get("missing", [])],
            "message": f"{j.get('title', '')} — {j.get('company', '')}{' (' + loc + ')' if loc else ''} : {round(j['score'] * 100)} %"}


def run_matching(alerts: dict[str, dict], search: Callable[[str, str | None, str | None], list[dict]], max_per_user: int = 5,
                 dry_run: bool = False) -> list[dict]:
    """Nouvelles offres au-dessus du seuil de chaque abonné, jamais deux fois la même offre pour un abonné.
    `search(query, country, city)` renvoie les offres candidates (recherche hybride Qdrant) ; le classement se fait ici."""
    out: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()
    for a in alerts.values():
        cands = search(" ".join(a["skills"] + [a["titles"]]).strip() or "emploi", a["country"], a["city"])
        seen = set(a["notified"])
        fresh = [j for j in cands if j.get("url") and j["url"] not in seen]
        ranked = matching.rank_jobs(a["skills"], a["titles"], fresh, max_per_user, a["min_score"])
        out.extend(_line(a, j) for j in ranked)
        if not dry_run:
            a["notified"] = (a["notified"] + [j["url"] for j in ranked])[-MAX_NOTIFIED:]
            a["last_run"] = now
    return out
