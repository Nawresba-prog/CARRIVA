"""Mode « 100 % navigateur » : les agents à règles (sans serveur, sans IA, sans tiers) tournent dans Pyodide (WebAssembly).

`handle(method, path, query, body)` reproduit, pour les routes pures, la même réponse que backend/app.py ; les routes qui ont besoin d'un serveur
(envoi Gmail, offres en direct, PDF, IA…) répondent 501 avec un message clair. Aucune donnée ne quitte le navigateur."""
from __future__ import annotations
import base64
import json
from urllib.parse import parse_qs

from . import ai_input, bootstrap_biz, brand_site, catalog, chat_reply, cv_import, enrich, linkedin, portfolio_site, processing, retouch, spot, strategy

OFF = {"ai": "off", "changes": []}
NEEDS_SERVER = "Cette fonction nécessite la version avec serveur (voir le README) : elle n'est pas disponible dans la version 100 % navigateur."


def _proc(data: dict, kinds: dict):
    r = ai_input.process({k: data.get(k, "") for k in kinds}, kinds, False)
    return {**data, **r["fields"]}, {"ai": "off", "changes": []}


def _chat(b):
    d, pr = _proc(b, {"offer": "label", "persona": "sentence", "tone": "label", "rules": "sentence", "logistics": "sentence", "cross": "label", "guarantee": "sentence", "alt": "label"})
    return {**chat_reply.reply(d), "processing": pr}


def _spot(b):
    d, pr = _proc(b, {"product": "name", "audience": "label", "pain": "sentence", "benefit": "sentence", "offer": "label"})
    return {**spot.campaign(d), "processing": pr}


def _strategy(b):
    d, pr = _proc(b, {"sector": "label"})
    return {**strategy.diagnostic(d), "processing": pr}


def _linkedin(b):
    a = linkedin.audit(b)
    return {"audit": a, "headlines": linkedin.headline_options(b), "about_template": linkedin.about_template(b),
            "prompt": linkedin.ai_prompt(b, b.get("lang", "fr"), a["keywords"]["missing"]), "ai_ready": False}


def _brand(b):
    return brand_site.reply({**b, "ai": False})


def _cv_import(b):
    try:
        data = base64.b64decode(b.get("data_b64", ""), validate=True)
    except Exception:  # noqa: BLE001
        raise ValueError("Fichier invalide")
    try:
        return cv_import.import_cv(data, b.get("filename", ""))
    except ModuleNotFoundError:
        raise ValueError("Lecture des PDF indisponible dans la version navigateur : utilisez un fichier Word (.docx) ou texte (.txt), ou la version avec serveur.")


def _cv(b, q):
    """Même traitement que POST /cv (nettoyage, normalisation, schéma Europass), sans IA ; la photo reste dans le navigateur."""
    lang = (q.get("lang") or ["fr"])[0]
    if lang not in ("fr", "en", "de", "es", "it", "ar"):
        lang = "en"
    b = {**b, "photo": ""}
    data, changes = enrich.process_and_enrich(b, lang)
    eu = processing.to_europass(data, lang)
    for k in ("_ai", "_photo"):
        eu.pop(k, None)
    if eu.get("summary") and not b.get("summary"):
        changes.append({"field": "summary_generated", "ref": "", "before": "", "after": eu["summary"]})
    return {"europass": eu, "changes": changes}


def _trainings(q):
    lang = (q.get("lang") or ["fr"])[0]
    return {"categories": [{"id": k, "courses": [catalog.localize(c, lang) for c in v]} for k, v in catalog.STANDARD.items()]}


POST = {"/bootstrap/analyze": bootstrap_biz.reply, "/brand/kit": _brand, "/chat/reply": _chat, "/spots/campaign": _spot,
        "/strategy/diagnostic": _strategy, "/images/plan": retouch.plan, "/linkedin/audit": _linkedin, "/portfolio/site": portfolio_site.build, "/portfolio/site": portfolio_site.build, "/cv/import": _cv_import}


def handle(method: str, path: str, query: str = "", body: str = "") -> str:
    """Retourne une chaîne JSON : {"status": int, "json": ...}."""
    method = method.upper()
    try:
        if path == "/auth/mode":
            return _out(200, {"mode": "dev"})
        if path == "/auth/dev-token" and method == "POST":
            return _out(200, {"token": "navigateur"})
        if path == "/trainings/standard" and method == "GET":
            return _out(200, _trainings(parse_qs(query)))
        if path == "/cv/pdf":
            return _out(501, {"detail": "Le PDF « Europass » officiel nécessite la version avec serveur : choisissez un autre modèle (Moderne, Classique, Minimaliste…)."})
        if path == "/cv" and method == "POST":
            return _out(200, _cv(json.loads(body or "{}"), parse_qs(query)))
        fn = POST.get(path)
        if fn and method == "POST":
            return _out(200, fn(json.loads(body or "{}")))
        if path == "/jobs/alerts" and method == "GET":
            return _out(200, {"alerts": [], "enabled": False})
        return _out(501, {"detail": NEEDS_SERVER})
    except ValueError as exc:
        return _out(422, {"detail": str(exc)})
    except Exception as exc:  # noqa: BLE001
        return _out(500, {"detail": "Erreur : " + str(exc)[:200]})


def _out(status: int, payload) -> str:
    return json.dumps({"status": status, "json": payload}, ensure_ascii=False)
