"""CARRIVA — prototype d'agent IA d'entreprise.

Pipeline : User -> Agent -> RAG -> Tools -> Enterprise API -> Human Approval -> Action -> Monitoring
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import threading
import time
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Literal

import httpx
import jwt
import numpy as np
from fastapi import Body, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from qdrant_client import QdrantClient
from langgraph.types import Command
from qdrant_client.models import (Distance, FieldCondition, Filter, Fusion, FusionQuery, MatchValue, PointStruct,
                                  Prefetch, SparseVector, SparseVectorParams, VectorParams)

from . import accesscodes, alerts, bootstrap_biz, catalog, ai_input, brand_site, cert_mail, chat_reply, cv_import, enrich, facturx, followup, growth, invoices, mailbox, strategy, joblinks, jobsources, linkedin, lms, matching, pdf_gen, photo_ai, processing, retouch, report_pdf, spot
from . import replies, store
from .agent import build_graph, make_checkpointer
from .seed_data import SEED_JOBS

# --------------------------------------------------------------------------- config
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-change-me")
JWT_TTL_MIN = 15
GMAIL_SERVICE_URL = os.getenv("GMAIL_SERVICE_URL", "http://localhost:3001")
INTERNAL_SECRET = os.getenv("INTERNAL_SECRET", "dev-internal-secret")
QDRANT_URL = os.getenv("QDRANT_URL", ":memory:")
APPROVAL_TTL = timedelta(hours=24)
APPLY_LIMIT = cert_mail.Limiter(30, 3600)   # 30 demandes de candidature / heure / utilisateur
LLM_LIMIT = cert_mail.Limiter(60, 3600)     # 60 appels IA (chat, boost, brouillons, photo) / heure / utilisateur : maîtrise des coûts
HEAVY_LIMIT = cert_mail.Limiter(120, 3600)  # 120 PDF / imports de fichiers / heure / utilisateur


def _limit(lim, user: dict, what: str = "") -> None:
    if not lim.allow(user["sub"]):
        raise HTTPException(429, "Limite horaire atteinte" + (f" ({what})" if what else "") + " : réessayez dans un moment.")
DIM = 256
FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "index.html"

logging.basicConfig(level=logging.INFO, format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}')
log = logging.getLogger("career")
ENV = os.getenv("ENV", "dev")
DATA_DIR = os.getenv("CAREER_DATA_DIR", str(Path(__file__).resolve().parent.parent / "data"))   # "" = pas de persistance
_weak = store.insecure_defaults(ENV, JWT_SECRET, INTERNAL_SECRET)
if _weak and ENV != "dev":
    raise RuntimeError("Configuration refusée (ENV=%s) : %s. Définissez JWT_SECRET et INTERNAL_SECRET (valeurs longues et aléatoires)." % (ENV, ", ".join(_weak)))
if _weak:
    log.warning("MODE DÉVELOPPEMENT : %s. Ne jamais déployer ainsi (ENV=prod exige des secrets personnalisés).", ", ".join(_weak))

# --------------------------------------------------------------------------- monitoring
HTTP_LAT = Histogram("career_http_seconds", "HTTP latency", ["route"])
TOOL_CALLS = Counter("career_tool_calls_total", "Tool calls", ["tool", "status"])
PENDING = Gauge("career_approvals_pending", "Pending approvals")
SENDS = Counter("career_email_sends_total", "Email sends", ["status"])

# --------------------------------------------------------------------------- RAG
def embed(text: str) -> list[float]:
    """Embedding de repli (hashing trick). En production : modèle multilingue (e5 / OpenAI)."""
    v = np.zeros(DIM)
    for tok in text.lower().split():
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        v[h % DIM] += 1.0 if (h >> 8) & 1 else -1.0
    n = np.linalg.norm(v)
    return (v / n if n else v).tolist()


def sparse_embed(text: str) -> SparseVector:
    """Vecteur creux (termes hachés, poids = fréquence). Production : BM25/SPLADE via fastembed."""
    counts: dict[int, float] = {}
    for tok in text.lower().split():
        idx = int(hashlib.md5(tok.encode()).hexdigest(), 16) % (2**20)
        counts[idx] = counts.get(idx, 0.0) + 1.0
    return SparseVector(indices=list(counts), values=list(counts.values()))


qdrant = QdrantClient(QDRANT_URL)  # ":memory:" (prototype) ou "http://qdrant:6333" / cluster managé
for col in ("jobs", "trainings"):
    if not qdrant.collection_exists(col):
        qdrant.create_collection(
            col,
            vectors_config={"dense": VectorParams(size=DIM, distance=Distance.COSINE)},
            sparse_vectors_config={"sparse": SparseVectorParams()},
        )
        if QDRANT_URL != ":memory:":  # index de payload pour filtrer vite (pays/ville)
            for field in ("country", "city"):
                qdrant.create_payload_index(col, field, "keyword")


def hybrid_search(col: str, text: str, flt: Filter | None, k: int):
    """Recherche hybride : dense + sparse, fusion RRF, filtres de payload appliqués dans chaque prefetch."""
    return qdrant.query_points(
        col,
        prefetch=[
            Prefetch(query=embed(text), using="dense", filter=flt, limit=max(20, k)),
            Prefetch(query=sparse_embed(text), using="sparse", filter=flt, limit=max(20, k)),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=k,
        with_payload=True,
    ).points


def point_id(source: str, url: str) -> str:
    return str(uuid.UUID(hashlib.md5(f"{source}|{url}".encode()).hexdigest()))


def index_doc(col: str, doc: dict) -> None:
    if not str(doc.get("skills", "")).strip():  # offres scrappées sans compétences : on les extrait du texte
        doc["skills"] = " ".join(matching.extract_skills(doc.get("title", ""), doc.get("description", "")))
    text = " ".join(str(doc.get(k, "")) for k in ("title", "description", "skills", "objectives"))
    qdrant.upsert(col, [PointStruct(id=point_id(doc.get("source", "seed"), doc["url"]),
                                    vector={"dense": embed(text), "sparse": sparse_embed(text)}, payload=doc)])


for j in SEED_JOBS:
    index_doc("jobs", {**j, "source": "seed"})
for t in catalog.all_courses():
    index_doc("trainings", {**t, "source": "catalog"})

# --------------------------------------------------------------------------- modèles
class Experience(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, str_max_length=2000)  # borne la taille des saisies

    title: str
    company: str = ""
    city: str = ""
    country: str = ""
    start: str = ""
    end: str = ""
    description: str = ""


class Education(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, str_max_length=2000)  # borne la taille des saisies

    degree: str
    school: str = ""
    city: str = ""
    country: str = ""
    start: str = ""
    end: str = ""
    year: str = ""
    level: str = ""  # niveau CEC (1-8)


class LanguageSkill(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, str_max_length=2000)  # borne la taille des saisies

    name: str
    level: str = "B2"  # niveau CECR global, appliqué aux 5 compétences si le détail est vide
    listening: str = ""
    reading: str = ""
    interaction: str = ""
    production: str = ""
    writing: str = ""


class CV(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, str_max_length=2000)  # borne la taille des saisies

    full_name: str
    email: EmailStr
    phone: str = ""
    website: str = ""
    city: str = ""
    country: str = ""
    nationality: str = ""
    date_of_birth: str = ""
    driving_licence: str = ""
    summary: str = ""
    mother_tongue: str = ""  # séparées par des virgules
    additional_info: str = ""
    experiences: list[Experience] = Field(default_factory=list, max_length=30)
    education: list[Education] = Field(default_factory=list, max_length=30)
    skills: list[str] = Field(default_factory=list, max_length=60)
    languages: list[LanguageSkill] = Field(default_factory=list, max_length=20)
    photo: str = Field(default="", max_length=700_000)  # facultatif : JPEG en data-URI, recadré/amélioré dans le navigateur


class ApplyRequest(BaseModel):
    cv: CV
    job_urls: list[str] = Field(min_length=1, max_length=10)
    cv_pdf_b64: str | None = Field(default=None, max_length=2_000_000)  # CV déjà mis en forme (modèle choisi dans l'interface) ; sinon Europass


class Decision(BaseModel):
    decision: Literal["approve", "reject"]
    body: str | None = Field(None, max_length=8000)  # l'approbateur peut éditer le corps avant validation
    expected_hash: str | None = Field(None, max_length=64)  # empreinte du brouillon relu : refus si le contenu a changé entre-temps


# --------------------------------------------------------------------------- RBAC
ROLES = {
    "candidate": {"cv", "search", "apply", "trainings", "growth"},
    "approver": {"approve", "cv", "search", "apply", "trainings", "growth"},
    "admin": {"index", "metrics", "approve", "cv", "search", "apply", "trainings", "growth"},
}


def current_user(request: Request) -> dict:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Token manquant")
    try:
        return jwt.decode(auth[7:], JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Token invalide ou expiré")


def require(perm: str) -> Callable:
    def dep(user: dict = Depends(current_user)) -> dict:
        if perm not in ROLES.get(user.get("role", ""), set()):
            raise HTTPException(403, f"Permission '{perm}' requise")
        return user
    return dep


# --------------------------------------------------------------------------- tools
TOOLS: dict[str, Callable] = {}


def tool(name: str):
    def deco(fn: Callable) -> Callable:
        def wrapped(*a, **kw):
            try:
                out = fn(*a, **kw)
                TOOL_CALLS.labels(name, "ok").inc()
                log.info("tool=%s status=ok", name)
                return out
            except Exception:
                TOOL_CALLS.labels(name, "error").inc()
                log.exception("tool=%s status=error", name)
                raise
        TOOLS[name] = wrapped
        return wrapped
    return deco


def clean_cv(cv: CV, lang: str = "fr") -> tuple[CV, list[dict]]:
    """Saisie brute -> CV traité (processing.py) puis complété selon le contexte (enrich.py) + rapport des modifications."""
    data, changes = enrich.process_and_enrich(cv.model_dump(), lang)
    return CV(**{**data, "photo": cv.photo}), changes


@tool("build_europass_cv")
def build_europass_cv(cv: CV, lang: str = "fr") -> dict:
    """Traite les données saisies (nettoyage, normalisation, dates, compétences, langues CECR, puces) puis construit le schéma Europass
    localisé dans `lang`. La saisie brute n'est jamais recopiée telle quelle."""
    data, _ = enrich.process_and_enrich(cv.model_dump(), lang)
    eu = processing.maybe_refine(processing.to_europass(data, lang), lang)
    if cv.photo:
        eu = {**eu, "_photo": cv.photo}  # transmise au rendu PDF uniquement ; retirée avant toute réponse JSON
    return eu


def _filter(country: str | None, city: str | None) -> Filter | None:
    must = []
    if country:
        must.append(FieldCondition(key="country", match=MatchValue(value=country.upper())))
    if city:
        must.append(FieldCondition(key="city", match=MatchValue(value=city)))
    return Filter(must=must) if must else None


JOBS_DEMO = os.getenv("JOBS_DEMO", "0") == "1"


@tool("search_jobs")
def search_jobs(query: str, country: str | None = None, city: str | None = None, k: int = 5) -> list[dict]:
    """Candidats via recherche hybride Qdrant (le re-classement par compétences est fait dans /jobs/match)."""
    hits = hybrid_search("jobs", query, _filter(country, None), max(k, 300))  # tout le catalogue : le classement se fait ensuite par compétences
    out = [h.payload for h in hits]
    if not JOBS_DEMO:  # les offres du catalogue de démonstration sont fictives : masquées par défaut (JOBS_DEMO=1 pour les afficher)
        out = [j for j in out if j.get("source") != "seed"]
    if city:
        cn = matching.normalize(city)
        out = [j for j in out if cn and cn in matching.normalize(j.get("city", ""))]
    return out


@tool("search_trainings")
def search_trainings(gaps: list[str], k: int = 6) -> list[dict]:
    hits = hybrid_search("trainings", " ".join(gaps), None, 40)
    return matching.rank_trainings(gaps, [h.payload for h in hits], k)


def _find_job(url: str) -> dict:
    pts, _ = qdrant.scroll("jobs", scroll_filter=Filter(must=[FieldCondition(key="url", match=MatchValue(value=url))]), limit=1)
    if not pts:
        raise HTTPException(404, f"Offre inconnue: {url}")
    return pts[0].payload


COUNTRY_LANG = {"FR": "fr", "DE": "de", "IT": "it", "ES": "es", "GB": "en", "US": "en",
                "MA": "ar", "DZ": "ar", "TN": "ar", "EG": "ar", "SA": "ar", "AE": "ar", "JO": "ar", "LB": "ar", "QA": "ar"}
TEMPLATES = {
    "fr": ("Candidature : {title}", "Madame, Monsieur,\n\n{intro}\n\nJe vous adresse ma candidature pour le poste de {title} au sein de {company}. Vous trouverez mon CV en pièce jointe.\n\nCordialement,\n{name}"),
    "en": ("Application: {title}", "Dear Hiring Team,\n\n{intro}\n\nI am applying for the {title} position at {company}. Please find my CV attached.\n\nKind regards,\n{name}"),
    "de": ("Bewerbung: {title}", "Sehr geehrte Damen und Herren,\n\n{intro}\n\nhiermit bewerbe ich mich auf die Stelle {title} bei {company}. Meinen Lebenslauf finden Sie im Anhang.\n\nMit freundlichen Grüßen\n{name}"),
    "it": ("Candidatura: {title}", "Gentili Signori,\n\n{intro}\n\nMi candido per la posizione di {title} presso {company}. In allegato trovate il mio CV.\n\nCordiali saluti,\n{name}"),
    "es": ("Candidatura: {title}", "Estimado equipo de selección:\n\n{intro}\n\nMe presento como candidato al puesto de {title} en {company}. Adjunto mi CV.\n\nAtentamente,\n{name}"),
    "ar": ("طلب توظيف: {title}", "السادة المحترمون،\n\n{intro}\n\nأتقدّم بطلبي لشغل وظيفة {title} لدى {company}. تجدون سيرتي الذاتية مرفقة.\n\nمع خالص التقدير،\n{name}"),
}


@tool("draft_application_email")
def draft_application_email(cv: CV, job: dict) -> dict:
    """Brouillon dans la langue officielle du pays. Production : LLM (langchain) avec ce gabarit comme repli."""
    lang = COUNTRY_LANG.get(job.get("country", ""), "en")
    subject, body = TEMPLATES[lang]
    data, _ = enrich.process_and_enrich(cv.model_dump(), lang)
    intro = processing.first_sentences(data["summary"] or processing.auto_summary(data, lang))
    fmt = dict(title=job["title"], company=job["company"], name=data["full_name"], intro=intro)
    _, to = mailbox.address(str(job.get("email") or ""))        # une seule adresse valide ; sinon lettre à envoyer via l'annonce (pas d'envoi à des listes ni à des adresses piégées)
    draft = {"to": to, "subject": subject.format(**fmt), "body": body.format(**fmt), "lang": lang,
             "channel": "email" if to else "link"}  # sans e-mail : on rédige la lettre, la candidature se fait via l'annonce
    if not to:
        draft["apply_url"] = (joblinks.for_job(job) or [{"url": ""}])[0]["url"]
    return draft


def send_email_tool(draft: dict, cv_json: dict, pdf_override: bytes | None = None) -> dict:
    """Outil CRITIQUE : appelé uniquement depuis le noeud `send` du graphe, après l'Approval Gate."""
    attachment = None  # une relance n'a pas de pièce jointe
    if draft.get("kind") != "followup":
        pdf = pdf_override or pdf_gen.cv_pdf(cv_json, lang=draft.get("lang", "en"))
        attachment = {"filename": "CV_europass.pdf" if not pdf_override else "CV.pdf", "mime": "application/pdf", "data_b64": base64.b64encode(pdf).decode()}
    payload = {"to": draft["to"], "subject": draft["subject"], "body": draft["body"], **({"attachment": attachment} if attachment else {})}
    # clé d'idempotence : une nouvelle tentative après un délai dépassé ne peut pas produire un deuxième e-mail (le service Gmail mémorise la clé)
    headers = {"x-internal-secret": INTERNAL_SECRET, "x-idempotency-key": content_hash(draft)}
    last: Exception | None = None
    for i in range(3):
        try:
            with httpx.Client(timeout=20) as c:
                r = c.post(f"{GMAIL_SERVICE_URL}/send", headers=headers, json=payload)
            if r.status_code >= 500 and i < 2:
                time.sleep(1.5 * (i + 1)); continue
            r.raise_for_status()
            return r.json()
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last = exc
            if i < 2:
                time.sleep(1.5 * (i + 1))
    raise last or RuntimeError("envoi impossible")


# --------------------------------------------------------------------------- Approval Gate
APPROVALS: dict[str, dict] = store.load(DATA_DIR, "approvals", {})     # persistés (JSON atomique) : survivent à un redémarrage
_STATE_LOCK = threading.Lock()


OPTOUT: set[str] = set(store.load(DATA_DIR, "optout", []))      # destinataires qui ont demandé à ne plus être contactés


def _persist() -> None:
    store.save(DATA_DIR, "optout", sorted(OPTOUT))
    store.save(DATA_DIR, "approvals", APPROVALS)
    store.save(DATA_DIR, "alerts", ALERTS)


def content_hash(d: dict) -> str:
    return hashlib.sha256(f"{d['to']}|{d['subject']}|{d['body']}".encode()).hexdigest()


def _send(draft: dict, cv: dict) -> dict:
    lang = draft.get("lang", "en")  # CV joint dans la langue de l'offre
    if draft.get("channel") == "link":  # pas d'adresse e-mail : rien n'est envoyé, la lettre approuvée est remise à l'utilisateur
        return {"manual": True, "apply_url": draft.get("apply_url", ""), "subject": draft["subject"], "body": draft["body"], "lang": lang}
    if draft.get("kind") == "followup":  # texte seul, pas de CV à construire
        return send_email_tool(draft, {})
    cv = dict(cv)
    pdf_b64 = cv.pop("_pdf_b64", None)  # PDF choisi par l'utilisateur (modèle de CV) : validé à l'entrée de /apply
    return send_email_tool(draft, TOOLS["build_europass_cv"](CV(**cv), lang), base64.b64decode(pdf_b64) if pdf_b64 else None)


# Graphe LangGraph : draft -> approval_gate (interrupt) -> send
if DATA_DIR:
    os.makedirs(DATA_DIR, exist_ok=True)
CHECKPOINTER, GRAPH_PERSISTENT = make_checkpointer(os.path.join(DATA_DIR, "checkpoints.sqlite") if DATA_DIR else None)
GRAPH = build_graph(
    draft_fn=lambda cv, job: TOOLS["draft_application_email"](CV(**cv), job),
    send_fn=_send,
    hash_fn=content_hash,
    checkpointer=CHECKPOINTER,
)
if not GRAPH_PERSISTENT:    # sans checkpointer persistant, une approbation en attente ne peut plus être reprise après redémarrage : on le dit au lieu de la laisser « pending »
    for _a in APPROVALS.values():
        if _a.get("status") in ("pending", "processing"):
            _a["status"] = "expired"; _a["note"] = "lost_on_restart"


# --------------------------------------------------------------------------- app
app = FastAPI(title="CARRIVA")


@app.middleware("http")
async def metrics_mw(request: Request, call_next):
    start = time.perf_counter()
    rid = request.headers.get("x-request-id", uuid.uuid4().hex[:8])
    resp = await call_next(request)
    HTTP_LAT.labels(request.url.path).observe(time.perf_counter() - start)
    resp.headers["x-request-id"] = rid
    return resp


@app.get("/cv-templates.js", include_in_schema=False)
def cv_templates_js():
    """Moteur des modèles de CV (hors Europass), exécuté dans le navigateur : les données du CV ne quittent pas l'appareil pour l'aperçu."""
    return FileResponse(FRONTEND.parent / "cv-templates.js", media_type="text/javascript")


_PWA = {"manifest.webmanifest": "application/manifest+json", "sw.js": "text/javascript"}


@app.get("/app.css", include_in_schema=False)
def app_css():
    return FileResponse(FRONTEND.parent / "app.css", media_type="text/css")


@app.get("/manifest.webmanifest", include_in_schema=False)
def pwa_manifest():
    return FileResponse(FRONTEND.parent / "manifest.webmanifest", media_type=_PWA["manifest.webmanifest"])


@app.get("/sw.js", include_in_schema=False)
def pwa_sw():
    """Service worker servi à la racine (portée « / ») ; jamais mis en cache par le navigateur pour que les mises à jour passent."""
    return FileResponse(FRONTEND.parent / "sw.js", media_type="text/javascript", headers={"cache-control": "no-cache"})


@app.get("/icons/{name}", include_in_schema=False)
def pwa_icon(name: str):
    if name not in {"icon-192.png", "icon-512.png", "icon-maskable-512.png", "apple-touch-icon.png"}:
        raise HTTPException(404)
    return FileResponse(FRONTEND.parent / "icons" / name, media_type="image/png", headers={"cache-control": "public, max-age=86400"})


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(FRONTEND.parent / "icons" / "icon-192.png", media_type="image/png", headers={"cache-control": "public, max-age=86400"})


@app.get("/")
def home():
    return FileResponse(FRONTEND)


class GrowthMsg(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class GrowthReq(BaseModel):
    service: int = Field(ge=1, le=6)
    lang: Literal["fr", "en", "de", "es", "it", "ar"] = "fr"
    company: dict[str, str] = Field(default_factory=dict, max_length=8)
    messages: list[GrowthMsg] = Field(min_length=1, max_length=24)


@app.post("/growth/chat")
def growth_chat(req: GrowthReq, user: dict = Depends(require("growth"))):
    """Growth & Social AI (propriétaires d'entreprise) : 4 services générés par LLM. Aucune action externe n'est exécutée."""
    _limit(LLM_LIMIT, user, "IA")
    if not growth.llm_ready():
        raise HTTPException(503, "ANTHROPIC_API_KEY manquant : renseignez-le dans .env puis relancez le serveur.")
    msgs = [m.model_dump() for m in req.messages]
    if req.service not in growth.SERVICES:                  # 5 = factures (pas de conversation IA)
        raise HTTPException(422, "Service sans conversation IA")
    if msgs[0]["role"] != "user" or msgs[-1]["role"] != "user":
        raise HTTPException(422, "La conversation doit commencer et finir par un message utilisateur")
    company = {k: str(v)[:300] for k, v in req.company.items() if k in {"name", "sector", "audience", "tone", "goals"}}
    try:
        return {"reply": growth.chat(req.service, req.lang, company, msgs)}
    except httpx.HTTPError as exc:
        log.warning("growth chat: %s", exc)
        raise HTTPException(502, "Le service IA n'a pas répondu, réessayez dans un instant.")


# --------------------------------------------------------------------------- boîte de réception (Propriétaire d'entreprise, service 2)
MAIL_SEND = cert_mail.Limiter(10, 3600)   # 10 réponses / heure / utilisateur


def _gmail_call(method: str, path: str, **kw) -> dict:
    try:
        with httpx.Client(timeout=30) as c:
            r = c.request(method, f"{GMAIL_SERVICE_URL}{path}", headers={"x-internal-secret": INTERNAL_SECRET}, **kw)
    except httpx.HTTPError as exc:
        log.warning("gmail service unreachable: %s", exc)
        raise HTTPException(502, "Le service e-mail ne répond pas : vérifiez qu'il est lancé (gmail-service) ou collez un e-mail.")
    if r.status_code == 501:
        raise HTTPException(501, "Lecture de la boîte désactivée : définissez GMAIL_READ=true dans le service Gmail (jeton avec le droit de lecture seule), ou collez un e-mail.")
    if r.status_code == 404:
        raise HTTPException(404, "Message introuvable.")
    if r.status_code >= 400:
        raise HTTPException(502, "Gmail n'a pas répondu, réessayez dans un instant.")
    return r.json()


class MailRaw(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field("", max_length=80)
    thread_id: str = Field("", max_length=80)
    sender: str = Field("", alias="from", max_length=300)
    reply_to: str = Field("", max_length=300)
    to: str = Field("", max_length=300)
    subject: str = Field("", max_length=300)
    date: str = Field("", max_length=80)
    body: str = Field("", max_length=20000)
    message_id: str = Field("", max_length=200)
    references: str = Field("", max_length=600)
    auto: bool = False


class MailParseReq(BaseModel):
    model_config = ConfigDict(extra="ignore")
    eml_b64: str = Field("", max_length=4_500_000)
    message: MailRaw | None = None


class MailMsg(BaseModel):
    """Message déjà analysé, renvoyé par l'interface pour un brouillon ou un rapport (re-nettoyé côté serveur)."""
    model_config = ConfigDict(extra="ignore")
    id: str = Field("", max_length=80)
    thread_id: str = Field("", max_length=80)
    from_name: str = Field("", max_length=120)
    from_email: str = Field("", max_length=200)
    reply_email: str = Field("", max_length=200)
    subject: str = Field("", max_length=300)
    date: str = Field("", max_length=80)
    body: str = Field("", max_length=20000)
    message_id: str = Field("", max_length=200)
    references: str = Field("", max_length=600)


class MailDraftReq(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message: MailMsg
    lang: Literal["fr", "en", "de", "es", "it", "ar"] | None = None
    tone: Literal["professional", "friendly", "short"] = "professional"
    instructions: str = Field("", max_length=300)
    company: dict[str, str] = Field(default_factory=dict, max_length=8)


class MailSendReq(BaseModel):
    model_config = ConfigDict(extra="ignore")
    confirmed: bool = False
    message_id: str = Field("", max_length=80)         # message de la boîte : destinataire retrouvé côté serveur
    to: str = Field("", max_length=300)                # seulement pour un e-mail collé / importé
    subject: str = Field(..., max_length=300)
    body: str = Field(..., max_length=9000)
    thread_id: str = Field("", max_length=80)
    in_reply_to: str = Field("", max_length=200)
    references: str = Field("", max_length=600)


def _analysed(m: MailMsg) -> dict:
    d = m.model_dump()
    d["from"] = f"{d['from_name']} <{d['from_email']}>" if d["from_name"] else d["from_email"]
    d["reply_to"] = d.get("reply_email", "")
    return mailbox.with_analysis(d)


@app.get("/mail/status")
def mail_status(user: dict = Depends(require("growth"))):
    """État du service e-mail : connecté, lecture activée, mode démonstration, envoi réel ou simulé, IA disponible."""
    try:
        with httpx.Client(timeout=4) as c:
            st = c.get(f"{GMAIL_SERVICE_URL}/status", headers={"x-internal-secret": INTERNAL_SECRET}).json()
    except Exception:  # noqa: BLE001
        st = {"ok": False}
    return {"service": bool(st.get("ok")), "read_enabled": bool(st.get("readEnabled")), "connected": bool(st.get("connected")), "demo": bool(st.get("demo")),
            "dry_run": bool(st.get("dryRun", True)), "ai_ready": mailbox.ai_ready()}


@app.get("/mail/inbox")
def mail_inbox(n: int = 15, q: str = "", user: dict = Depends(require("growth"))):
    """Lecture seule des derniers e-mails reçus, classés par règles (catégorie, urgence, résumé). Rien n'est modifié dans la boîte."""
    data = _gmail_call("GET", "/inbox", params={"max": max(1, min(n, 30)), "q": q[:100]})
    msgs = [mailbox.with_analysis(m) for m in data.get("messages", [])]
    return {"demo": bool(data.get("demo")), "messages": msgs, "report": mailbox.report(msgs)}


@app.post("/mail/parse")
def mail_parse(req: MailParseReq, user: dict = Depends(require("growth"))):
    """E-mail collé ou fichier .eml -> message analysé (aucune connexion à une boîte nécessaire)."""
    try:
        if req.eml_b64:
            raw = mailbox.parse_eml(base64.b64decode(req.eml_b64, validate=False))
        elif req.message and (req.message.body.strip() or req.message.subject.strip()):
            raw = req.message.model_dump(by_alias=True)
        else:
            raise ValueError("Collez le contenu de l'e-mail ou choisissez un fichier .eml.")
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except Exception:  # noqa: BLE001
        raise HTTPException(422, "Fichier .eml illisible.")
    m = mailbox.with_analysis(raw)
    if not m["id"]:
        m["id"] = "pasted-" + hashlib.sha1((m["subject"] + m["body"]).encode()).hexdigest()[:10]
    return {"message": m}


@app.post("/mail/report")
def mail_report(msgs: list[MailMsg] = Body(..., max_length=40), user: dict = Depends(require("growth"))):
    """Rapport de boîte de réception (par règles) : à traiter par priorité, suspects, automatiques."""
    return mailbox.report([_analysed(m) for m in msgs])


@app.post("/mail/draft")
def mail_draft(req: MailDraftReq, user: dict = Depends(require("growth"))):
    """Prépare un brouillon de réponse (IA si ANTHROPIC_API_KEY, sinon modèle avec trous à compléter). N'ENVOIE RIEN."""
    _limit(LLM_LIMIT, user, "IA")
    m = _analysed(req.message)
    if not m["from_email"]:
        raise HTTPException(422, "Expéditeur introuvable : impossible de préparer une réponse.")
    company = {k: str(v)[:300] for k, v in req.company.items() if k in {"name", "sector", "tone"}}
    try:
        return mailbox.draft_reply(m, req.lang or m["lang"], company, req.tone, req.instructions)
    except httpx.HTTPError as exc:
        log.warning("mail draft: %s", exc)
        return {**mailbox.template_reply(m, req.lang or m["lang"], company, req.tone), "ai_failed": True}


@app.post("/mail/send")
def mail_send(req: MailSendReq, user: dict = Depends(require("growth"))):
    """Envoie une réponse APRÈS validation explicite (`confirmed: true`). Pour un message de la boîte, le destinataire est retrouvé côté serveur (le client ne peut pas le changer)."""
    if not req.confirmed:
        raise HTTPException(422, "Validation de l'utilisateur requise avant l'envoi.")
    thread, irt, refs = req.thread_id, req.in_reply_to, req.references
    to = req.to
    if req.message_id and not req.message_id.startswith("pasted-"):
        orig = mailbox.with_analysis(_gmail_call("GET", f"/message/{req.message_id}"))
        if not orig["needs_reply"]:
            raise HTTPException(422, "Ce message est automatique ou suspect : réponse refusée.")
        to, thread, irt, refs = mailbox.recipient(orig), orig["thread_id"], orig["message_id"], orig["references"]
    try:
        to, subject, body = mailbox.validate_outgoing(to, req.subject, req.body)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if not MAIL_SEND.allow(user["sub"]):
        raise HTTPException(429, "Limite atteinte : 10 réponses par heure. Réessayez plus tard.")
    payload = {"to": to, "subject": subject, "body": body}
    if irt: payload["inReplyTo"] = irt
    if irt and refs: payload["references"] = refs
    if thread: payload["threadId"] = thread
    try:
        res = _gmail_call("POST", "/send", json=payload)
    except HTTPException:
        SENDS.labels("error").inc()
        raise
    SENDS.labels("ok").inc()
    log.info("mail reply sent to %s (dry_run=%s)", _mask(to), bool(res.get("dryRun")))
    return {"sent": not res.get("dryRun"), "dry_run": bool(res.get("dryRun")), "to": to}


class StrategyReq(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    country: str = Field("FR", max_length=2)
    employees: int = Field(0, ge=0, le=1_000_000)
    turnover_m: float | None = Field(None, ge=0, le=1_000_000)
    sector: str = Field("", max_length=120)
    goal: Literal["growth", "profit", "export", "transition"] = "growth"
    answers: dict[str, int] = Field(default_factory=dict, max_length=40)
    done: list[str] = Field(default_factory=list, max_length=40)
    ai: bool = True


def _proc(user: dict, ai: bool, data: dict, kinds: dict) -> tuple[dict, dict]:
    """Met en forme (gratuit) puis, si la clé ANTHROPIC_API_KEY existe et que l'utilisateur n'a pas désactivé l'IA, corrige les textes libres (ai_input.py).
    Retourne (données traitées, {"ai": statut, "changes": [...]})."""
    if ai and ai_input.enabled() and any(str(data.get(k) or "").strip() for k, kd in kinds.items() if kd != "name"):
        _limit(LLM_LIMIT, user, "IA")
    r = ai_input.process({k: data.get(k, "") for k in kinds}, kinds, ai)
    return {**data, **r["fields"]}, {"ai": r["status"], "changes": r["changes"][:12]}


@app.post("/strategy/diagnostic")
def strategy_diagnostic(req: StrategyReq, user: dict = Depends(require("growth"))):
    """Service 6 (Propriétaire d'entreprise) : diagnostic stratégie / RSE / conformité par règles, sans IA ni tiers ; radar réglementaire indicatif."""
    d, pr = _proc(user, req.ai, req.model_dump(), {"sector": "label"})
    return {**strategy.diagnostic(d), "processing": pr}


class SpotReq(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    product: str = Field(min_length=1, max_length=120)
    audience: str = Field("", max_length=160)
    pain: str = Field("", max_length=160)
    benefit: str = Field("", max_length=160)
    offer: str = Field("", max_length=120)
    tone: Literal["inspiring", "dynamic", "humor", "premium", "educational"] = "dynamic"
    duration: Literal[15, 30, 60] = 30
    platform: Literal["reels", "tiktok", "youtube", "facebook"] = "reels"
    angle: Literal["auto", "ps", "ba", "hu"] = "auto"
    ai: bool = True


@app.post("/spots/campaign")
def spots_campaign(req: SpotReq, user: dict = Depends(require("growth"))):
    """Service 3 : campagne de spot vidéo clé en main (stratégie, storyboard minuté, prompts, outils gratuits, assemblage). Règles, sans IA ni tiers."""
    try:
        d, pr = _proc(user, req.ai, req.model_dump(), {"product": "name", "audience": "label", "pain": "sentence", "benefit": "sentence", "offer": "label"})
        return {**spot.campaign(d), "processing": pr}
    except ValueError as exc:
        raise HTTPException(422, str(exc))


class BrandReq(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(max_length=60); sector: str = Field(max_length=120)
    value: str = Field("", max_length=400); audience: str = Field("", max_length=200); values: str = Field("", max_length=200)
    tones: list[str] = Field(default_factory=list, max_length=7)
    goal: Literal["leads", "sell", "book", "inform"] = "leads"
    level: Literal["beginner", "intermediate", "developer"] = "beginner"
    logo_style: Literal["auto", "mono", "minimal", "bold", "warm", "typo", "badge", "spark"] = "auto"
    site_design: Literal["auto", "modern", "elegant", "bold", "minimal", "playful"] = "auto"
    email: str = Field("", max_length=120)
    lang: Literal["fr", "en", "de", "es", "it", "ar"] = "fr"
    ai: bool = True


@app.post("/brand/kit")
def brand_kit(req: BrandReq, user: dict = Depends(require("growth"))):
    """Service 7 : identité de marque (logo SVG, charte, prompt) et site web (structure, textes, outils gratuits, site HTML de départ). Règles, sans IA ni tiers ; rien n'est conservé."""
    if req.ai and brand_site.llm_enabled() and req.value.strip():
        _limit(LLM_LIMIT, user, "IA")                     # la reformulation IA (clé ANTHROPIC_API_KEY) est limitée ; le reste reste gratuit
    try:
        return brand_site.reply(req.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc))


class ChatReplyReq(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message: str = Field(max_length=2000)
    history: list[str] = Field(default_factory=list, max_length=10)
    channel: Literal["whatsapp", "messenger"] = "whatsapp"
    lang: Literal["auto", "fr", "en", "de", "es", "it", "ar"] = "auto"
    fallback: Literal["fr", "en", "de", "es", "it", "ar"] = "fr"
    brand: str = Field("", max_length=300); sector: str = Field("", max_length=300); offer: str = Field("", max_length=300)
    persona: str = Field("", max_length=300); tone: str = Field("", max_length=300); rules: str = Field("", max_length=300)
    logistics: str = Field("", max_length=300); price: str = Field("", max_length=300); cross: str = Field("", max_length=300)
    guarantee: str = Field("", max_length=300); alt: str = Field("", max_length=300); limited: bool = False
    ai: bool = True


@app.post("/chat/reply")
def chat_reply_route(req: ChatReplyReq, user: dict = Depends(require("growth"))):
    """Service 2, onglet Messagerie : analyse d'un message WhatsApp/Messenger et 3 réponses prêtes à copier. Règles, sans IA ni tiers ; rien n'est conservé."""
    try:
        d, pr = _proc(user, req.ai, req.model_dump(), {"offer": "label", "persona": "sentence", "tone": "label", "rules": "sentence", "logistics": "sentence", "cross": "label", "guarantee": "sentence", "alt": "label"})
        return {**chat_reply.reply(d), "processing": pr}
    except ValueError as exc:
        raise HTTPException(422, str(exc))


class BootstrapReq(BaseModel):
    model_config = ConfigDict(extra="ignore")
    cv_text: str = Field(max_length=6000)
    passions: str = Field("", max_length=300)
    hours: str = Field("", max_length=12); price: str = Field("", max_length=14); var_cost: str = Field("", max_length=14)
    fixed: str = Field("", max_length=14); goal: str = Field("", max_length=14)
    lang: Literal["fr", "en", "de", "es", "it", "ar"] = "fr"
    idea: Literal[0, 1, 2] | None = None


@app.post("/bootstrap/analyze")
def bootstrap_analyze(req: BootstrapReq, user: dict = Depends(require("cv"))):
    """Espace Candidat, bouton 7 : co-fondateur « 0 € » (BootstrapBot). Règles pures, sans IA ni tiers ; le CV collé n'est pas conservé."""
    try:
        return bootstrap_biz.reply(req.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc))


class RetouchPlanReq(BaseModel):
    model_config = ConfigDict(extra="ignore")
    scene: Literal["product", "portrait", "food", "interior"] = "product"
    light: Literal["studio", "natural"] = "studio"
    background: Literal["white", "grey", "lifestyle", "brand", "transparent", "keep"] = "white"
    usage: Literal["web", "social", "marketplace", "print"] = "web"
    ratio: Literal["orig", "1:1", "4:5", "9:16", "16:9"] = "orig"
    src_w: int | None = Field(None, ge=1, le=20000)
    src_h: int | None = Field(None, ge=1, le=20000)


class RetouchEnhanceReq(BaseModel):
    model_config = ConfigDict(extra="ignore")
    image: str = Field(max_length=11_000_000)
    light: Literal["studio", "natural"] = "studio"
    denoise: int = Field(40, ge=0, le=100)
    strength: int = Field(50, ge=0, le=100)
    target_long: int = Field(1600, ge=256, le=4000)


@app.post("/images/plan")
def images_plan(req: RetouchPlanReq, user: dict = Depends(require("growth"))):
    """Service 4 : plan de retouche chiffré avec outils gratuits (règles, sans IA ni tiers)."""
    return retouch.plan(req.model_dump())


@app.post("/images/enhance")
def images_enhance(req: RetouchEnhanceReq, user: dict = Depends(require("growth"))):
    """Service 4 : amélioration locale (Pillow) — niveaux, débruitage léger, agrandissement ≤ x2, netteté. Aucune donnée n'est conservée."""
    _limit(HEAVY_LIMIT, user, "retouche photo")
    try:
        return retouch.enhance(req.image, req.light, req.denoise, req.strength, req.target_long)
    except retouch.ImageError as exc:
        raise HTTPException(422, str(exc))


class ExportReq(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    title: str = Field(max_length=160)
    subtitle: str = Field("", max_length=200)
    lang: Literal["fr", "en", "de", "es", "it", "ar"] = "fr"
    blocks: list[dict] = Field(min_length=1, max_length=800)


@app.post("/export/pdf")
def export_pdf(req: ExportReq, user: dict = Depends(require("cv"))):
    """Export PDF d'un résultat déjà affiché (plan de retouche, dossier de spot, diagnostic, prompt du tuteur…). Rien n'est conservé."""
    _limit(HEAVY_LIMIT, user, "export PDF")
    try:
        pdf = report_pdf.render(req.title, req.blocks, req.lang, req.subtitle)
    except report_pdf.ReportError as exc:
        raise HTTPException(422 if "arabe" not in str(exc) else 503, str(exc))
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="carriva-export.pdf"'})


# --------------------------------------------------------------------------- factures (Propriétaire d'entreprise, service 5)
class InvParty(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field("", max_length=160)
    address: str = Field("", max_length=400)
    postcode: str = Field("", max_length=12)
    city: str = Field("", max_length=80)
    country: str = Field("", max_length=2)
    tax_id: str = Field("", max_length=60)
    vat_number: str = Field("", max_length=40)
    email: str = Field("", max_length=120)
    phone: str = Field("", max_length=40)
    iban: str = Field("", max_length=44)
    bic: str = Field("", max_length=11)
    is_business: bool = True


class InvLine(BaseModel):
    model_config = ConfigDict(extra="ignore")
    description: str = Field("", max_length=300)
    unit: str = Field("", max_length=20)
    qty: str | float | int = 1
    unit_price: str | float | int = 0
    discount: str | float | int = 0
    vat: str | float | int = 0


class InvoiceReq(BaseModel):
    model_config = ConfigDict(extra="ignore")
    lang: Literal["fr", "en", "de", "es", "it", "ar"] = "fr"
    doc_type: Literal["invoice", "credit_note", "quote"] = "invoice"
    ref_number: str = Field("", max_length=40)                                  # avoir : facture d'origine
    ref_date: str = Field("", pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    valid_until: str = Field("", pattern=r"^(\d{4}-\d{2}-\d{2})?$")           # devis : date limite d'acceptation
    currency: str = Field("EUR", max_length=3)
    number: str = Field("", max_length=40)
    issue_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    due_date: str = Field("", pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    service_date: str = Field("", pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    regime: Literal["standard", "franchise", "reverse_charge", "export", "intra_eu"] = "standard"
    payment_method: Literal["transfer", "card", "cash", "cheque", "other"] = "transfer"
    deposit: str | float | int = 0
    late_rate: str = Field("", max_length=80)
    notes: str = Field("", max_length=600)
    seller: InvParty
    client: InvParty
    lines: list[InvLine] = Field(min_length=1, max_length=100)


def _inv_dict(req: InvoiceReq) -> dict:
    d = req.model_dump()
    d["seller"]["country"] = d["seller"]["country"].upper()
    d["client"]["country"] = d["client"]["country"].upper()
    if d["doc_type"] != "invoice":
        d["deposit"] = 0
    d["currency"] = d["currency"].upper()
    return d


@app.post("/invoices/preview")
def invoice_preview(req: InvoiceReq, user: dict = Depends(require("growth"))):
    """Totaux exacts (Decimal), TVA par taux, mentions légales applicables et points de conformité à corriger. Rien n'est enregistré."""
    inv = _inv_dict(req)
    try:
        calc = invoices.compute(inv["lines"], inv["regime"], inv["deposit"])
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return {**invoices.num_json(calc), "currency": inv["currency"], "warnings": invoices.warnings(inv, calc),
            "legal": invoices.legal_mentions(inv["seller"]["country"], inv["regime"], inv["lang"], inv["client"]["is_business"], inv["late_rate"], inv["doc_type"]),
            "facturx_missing": facturx.check_inputs(inv) if inv["doc_type"] != "quote" else None}


@app.post("/invoices/pdf")
def invoice_pdf_route(req: InvoiceReq, user: dict = Depends(require("growth"))):
    _limit(HEAVY_LIMIT, user, "PDF")
    inv = _inv_dict(req)
    try:
        pdf, calc = invoices.invoice_pdf(inv, inv["lang"])
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    name = "".join(ch for ch in (inv["number"] or "facture") if ch.isalnum() or ch in "-_") or "facture"
    return Response(pdf, media_type="application/pdf", headers={"content-disposition": f'attachment; filename="{name}.pdf"',
                    "x-invoice-total": format(calc["total_ttc"], "f"), "x-invoice-due": format(calc["due"], "f"), "access-control-expose-headers": "x-invoice-total, x-invoice-due, content-disposition"})


@app.post("/invoices/facturx")
def invoice_facturx(req: InvoiceReq, user: dict = Depends(require("growth"))):
    """Factur-X (PDF/A-3 + XML CII EN 16931) pour une facture ou un avoir. 422 avec la liste des champs manquants si le XML ne peut pas être valide."""
    _limit(HEAVY_LIMIT, user, "PDF")
    inv = _inv_dict(req)
    try:
        pdf, info = facturx.generate(inv, inv["lang"])
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except ImportError as exc:
        raise HTTPException(501, f"Dépendance manquante pour Factur-X (pip install pikepdf lxml Pillow) : {exc}")
    name = "".join(ch for ch in (inv["number"] or "facture") if ch.isalnum() or ch in "-_") or "facture"
    return Response(pdf, media_type="application/pdf", headers={"content-disposition": f'attachment; filename="{name}_facturx.pdf"', "x-facturx-profile": info["profile"],
                    "x-facturx-pdfa": "ready" if info["pdfa_ready"] else "partial", "x-invoice-total": info["total"],
                    "access-control-expose-headers": "x-facturx-profile, x-facturx-pdfa, x-invoice-total, content-disposition"})


@app.get("/invoices/next-number")
def invoice_next_number(last: str = "", kind: Literal["invoice", "credit_note", "quote"] = "invoice", user: dict = Depends(require("growth"))):
    return {"number": invoices.next_number(last[:40], None, kind)}


_FONT_FILES = {"NotoSansArabic-Regular.ttf", "NotoSansArabic-Bold.ttf"}


@app.get("/fonts/{name}", include_in_schema=False)
def font_file(name: str):
    """Polices arabes (SIL OFL) pour les modèles de CV dessinés dans le navigateur : liste blanche, aucun chemin libre."""
    path = Path(__file__).resolve().parent / "fonts" / name
    if name not in _FONT_FILES or not path.is_file():
        raise HTTPException(404, "Police absente : lancez « python backend/fonts/fetch_fonts.py »")
    return FileResponse(path, media_type="font/ttf", headers={"cache-control": "public, max-age=86400"})


class PhotoCheck(BaseModel):
    image: str = Field(min_length=100, max_length=700_000)  # data-URI JPEG
    lang: Literal["fr", "en", "de", "es", "it", "ar"] = "fr"


class CVImportReq(BaseModel):
    filename: str = Field("", max_length=200)
    data_b64: str = Field(min_length=8, max_length=8_500_000)


@app.post("/cv/import")
def import_cv_file(req: CVImportReq, user: dict = Depends(require("cv"))):
    """CV déjà prêt (PDF, .docx, texte) -> champs du formulaire pré-remplis. Le fichier n'est pas conservé ; l'analyse est faite sur le serveur, sans IA."""
    _limit(HEAVY_LIMIT, user, "import")
    try:
        data = base64.b64decode(req.data_b64, validate=True)
    except Exception:  # noqa: BLE001
        raise HTTPException(422, "Fichier invalide")
    try:
        return cv_import.import_cv(data, req.filename)
    except cv_import.ImportError_ as exc:
        raise HTTPException(422, str(exc))
    except ModuleNotFoundError:
        raise HTTPException(501, "Lecture des PDF indisponible : exécutez « pip install pypdf » puis relancez le serveur.")


# --------------------------------------------------------------------------- profil LinkedIn (menu chercheur d'emploi, bouton 6)
class LiExp(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    title: str = Field("", max_length=160)
    company: str = Field("", max_length=160)
    description: str = Field("", max_length=3000)


class LiChecks(BaseModel):
    model_config = ConfigDict(extra="ignore")
    photo: bool = False
    banner: bool = False
    custom_url: bool = False
    location: bool = False
    featured: bool = False


class LinkedInReq(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    lang: Literal["fr", "en", "de", "es", "it", "ar"] = "fr"
    headline: str = Field("", max_length=300)
    about: str = Field("", max_length=4000)
    experiences: list[LiExp] = Field(default_factory=list, max_length=15)
    skills: list[str] = Field(default_factory=list, max_length=80)
    target_role: str = Field("", max_length=120)
    target_text: str = Field("", max_length=6000)
    value: str = Field("", max_length=140)
    checks: LiChecks = Field(default_factory=LiChecks)
    recommendations: int = Field(0, ge=0, le=99)


@app.post("/linkedin/audit")
def linkedin_audit(req: LinkedInReq, user: dict = Depends(require("cv"))):
    """Audit LinkedIn par règles (sans IA ni tiers) : score /100, constats classés, mots-clés manquants, titres proposés, plan 30 jours, prompt pour Claude."""
    p = req.model_dump()
    a = linkedin.audit(p)
    return {"audit": a, "headlines": linkedin.headline_options(p), "about_template": linkedin.about_template(p),
            "prompt": linkedin.ai_prompt(p, req.lang, a["keywords"]["missing"]), "ai_ready": bool(os.getenv("ANTHROPIC_API_KEY"))}


@app.post("/linkedin/boost")
def linkedin_boost(req: LinkedInReq, user: dict = Depends(require("cv"))):
    """Réécriture IA facultative (titres, À propos, puces d'expérience, plan de posts) sans rien inventer. Nécessite ANTHROPIC_API_KEY."""
    _limit(LLM_LIMIT, user, "IA")
    p = req.model_dump()
    missing = linkedin.audit(p)["keywords"]["missing"]
    try:
        return {"reply": linkedin.boost(p, req.lang, missing)}
    except RuntimeError:
        raise HTTPException(503, "ANTHROPIC_API_KEY manquant : renseignez-le dans .env puis relancez le serveur.")
    except httpx.HTTPError as exc:
        log.warning("linkedin boost: %s", exc)
        raise HTTPException(502, "Le service IA n'a pas répondu, réessayez dans un instant.")


@app.post("/cv/photo/check")
def photo_check(req: PhotoCheck, user: dict = Depends(require("cv"))):
    """Analyse IA (facultative, déclenchée par l'utilisateur) de la photo : cadrage, lumière, fond, tenue. N'identifie personne ; ne modifie rien."""
    _limit(LLM_LIMIT, user, "IA")
    if not photo_ai.llm_ready():
        raise HTTPException(503, "ANTHROPIC_API_KEY manquant : renseignez-le dans .env puis relancez le serveur.")
    try:
        return photo_ai.check(req.image, req.lang)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except httpx.HTTPError as exc:
        log.warning("photo check: %s", exc)
        raise HTTPException(502, "Le service IA n'a pas répondu, réessayez dans un instant.")


ACCESS_CODES, _ac_warn = accesscodes.parse(os.getenv("ACCESS_CODES", ""), ROLES)
for _w in _ac_warn:
    log.warning("ACCESS_CODES : %s", _w)
if ENV != "dev" and not ACCESS_CODES:
    log.warning("ENV=%s sans ACCESS_CODES : aucune connexion possible depuis l'interface (définissez ACCESS_CODES ou branchez OIDC).", ENV)
LOGIN_LIMIT = cert_mail.Limiter(10, 900)     # 10 tentatives / 15 min / adresse IP


class LoginReq(BaseModel):
    model_config = ConfigDict(extra="ignore")
    code: str = Field(max_length=200)


@app.get("/auth/mode")
def auth_mode():
    """Indique à l'interface comment se connecter : « dev » (jeton automatique), « code » (code d'accès) ou « none » (non configuré)."""
    if os.getenv("ENV", "dev") == "dev":
        return {"mode": "dev"}
    return {"mode": "code" if ACCESS_CODES else "none"}


@app.post("/auth/login")
def auth_login(req: LoginReq, request: Request):
    if not ACCESS_CODES:
        raise HTTPException(404)
    ip = request.client.host if request.client else "?"
    if not LOGIN_LIMIT.allow(ip):
        raise HTTPException(429, "Trop de tentatives : réessayez dans 15 minutes.")
    hit = accesscodes.check(ACCESS_CODES, req.code.strip())
    if not hit:
        log.warning("connexion refusée (ip=%s)", ip)
        raise HTTPException(401, "Code d'accès incorrect.")
    sub, role = hit
    exp = datetime.now(timezone.utc) + timedelta(minutes=JWT_TTL_MIN)
    return {"token": jwt.encode({"sub": sub, "role": role, "exp": exp}, JWT_SECRET, algorithm="HS256"), "role": role}


@app.post("/auth/dev-token")
def dev_token(role: str = "candidate", sub: str = "demo-user"):
    """DEV UNIQUEMENT — en production : OIDC."""
    if os.getenv("ENV", "dev") != "dev":
        raise HTTPException(404)
    if role not in ROLES:
        raise HTTPException(400, "rôle inconnu")
    exp = datetime.now(timezone.utc) + timedelta(minutes=JWT_TTL_MIN)
    return {"token": jwt.encode({"sub": sub, "role": role, "exp": exp}, JWT_SECRET, algorithm="HS256")}


@app.post("/cv")
def create_cv(cv: CV, lang: str = "fr", user: dict = Depends(require("cv"))):
    """Retourne le CV Europass TRAITÉ + le rapport de ce qui a été corrigé / normalisé / généré."""
    lang = lang if lang in pdf_gen.LABELS else "en"
    clean, changes = clean_cv(cv, lang)
    eu = TOOLS["build_europass_cv"](clean, lang)
    ai = eu.pop("_ai", "off")
    eu.pop("_photo", None)
    if ai == "ok":
        changes.append({"field": "ai_refined", "ref": "", "before": clean.summary, "after": eu["summary"]})
    elif ai == "failed":
        changes.append({"field": "ai_failed", "ref": "", "before": "", "after": "—"})
    elif eu["summary"] and not clean.summary:
        changes.append({"field": "summary_generated", "ref": "", "before": "", "after": eu["summary"]})
    return {"europass": eu, "changes": changes}


def _cv_profile(cv: CV) -> tuple[list[str], str]:
    """Compétences canoniques du CV (déclarées + déduites des postes, résumé, diplômes) et texte des intitulés."""
    titles = " ".join(e.title for e in cv.experiences)
    descr = " ".join(e.description for e in cv.experiences)
    edu = " ".join(f"{e.degree} {e.school}" for e in cv.education)
    skills = matching.extract_skills(" , ".join(cv.skills), titles, descr, cv.summary, edu)
    return skills, titles


def _candidates(query: str, iso: str, city: str) -> tuple[list[dict], dict]:
    """Vraies offres : fournisseurs en direct (Adzuna, France Travail, Arbeitnow, Remotive), indexées pour pouvoir postuler ensuite,
    puis offres déjà indexées (n8n / imports). Les offres fictives du catalogue de démo n'en font pas partie (sauf JOBS_DEMO=1)."""
    live, status = jobsources.fetch(query, iso, city)
    for j in live:
        j["skills"] = " ".join(matching.extract_skills(j.get("title", ""), j.get("description", "")))
        try:
            index_doc("jobs", dict(j))
        except Exception:  # noqa: BLE001 — l'indexation ne doit jamais bloquer l'affichage
            log.exception("index live job")
    stored = TOOLS["search_jobs"](query or "emploi", iso or None, city or None, 300)
    seen, out = set(), []
    for j in live + stored:
        if j["url"] not in seen:
            seen.add(j["url"]); out.append(j)
    return out, status


def _match_jobs(cv: CV, country: str | None, city: str | None, k: int, min_score: float = 0.15, status_out: dict | None = None) -> tuple[list[str], list[dict]]:
    skills, titles = _cv_profile(cv)
    query = " ".join(skills + [titles])
    iso = (country or "").upper() or processing.country_iso(getattr(cv, "country", "") or "")
    # requête courte pour les API (les mots-clés d'un CV entier ne donnent rien) : intitulé le plus récent, sinon 3 compétences
    short = (cv.experiences[0].title if cv.experiences else "") or " ".join(matching.label(x) for x in skills[:3])
    cands, st = _candidates(short[:80] or "emploi", iso, city or "")
    if status_out is not None:
        status_out.update(st)
    return skills, matching.rank_jobs(skills, titles, cands, k, min_score)


@app.get("/jobs/search")
def search_jobs_endpoint(q: str = "", country: str = "", city: str = "", user: dict = Depends(require("search"))):
    """Recherche libre d'emploi (sans CV) : mots-clés + pays + ville. Offres du catalogue classées par pertinence, plus des liens de
    recherche EN DIRECT (LinkedIn, Indeed, portail du pays) pour la même requête, même si le catalogue ne contient rien."""
    q, city = q.strip()[:120], city.strip()[:80]
    iso = country.strip().upper() if len(country.strip()) == 2 else processing.country_iso(country)
    if not (q or iso or city):
        raise HTTPException(422, "Indiquez des mots-clés, un pays ou une ville")
    jobs: list[dict] = []
    cands, src = _candidates(q or "emploi", iso or "", city or "")
    qn = matching.normalize(q)
    toks = [w for w in qn.split() if len(w) > 2]
    qskills = set(matching.extract_skills(q))
    for pos, j in enumerate(cands):
        title_n = matching.normalize(j.get("title", ""))
        body_n = matching.normalize(f"{j.get('description', '')} {j.get('company', '')}")
        jskills = set(str(j.get("skills", "")).split())
        if toks:
            t_hit = sum(1 for w in toks if w in title_n)
            b_hit = sum(1 for w in toks if w in body_n)
            s_hit = len(qskills & jskills)
            if not (t_hit or b_hit or s_hit):
                continue
            score = min(1.0, 0.55 * t_hit / len(toks) + 0.2 * b_hit / len(toks) + 0.25 * (s_hit / max(len(qskills), 1)) + 0.02 * (1 - pos / max(len(cands), 1)))
        else:  # filtre pays / ville seul : tout le catalogue correspondant
            score = round(0.5 + 0.02 * (1 - pos / max(len(cands), 1)), 3)
        jobs.append({**j, "score": round(score, 3), "matched": sorted(qskills & jskills), "links": joblinks.for_job(j),
                     "apply_mode": "email" if j.get("email") else "link"})
    jobs.sort(key=lambda j: -j["score"])
    live = joblinks.for_job({"title": q or "emploi", "city": city, "country": iso, "source": "search"})
    return {"query": q, "total": len(jobs), "jobs": jobs[:150], "live_links": live, "sources": src}


@app.post("/jobs/match")
def match(cv: CV, country: str | None = None, city: str | None = None, user: dict = Depends(require("search"))):
    src: dict = {}
    skills, jobs = _match_jobs(cv, country, city, 120, 0.08, src)  # le maximum d'offres, avec ou sans e-mail de candidature
    jobs = [{**j, "links": joblinks.for_job(j), "apply_mode": "email" if j.get("email") else "link"} for j in jobs]  # liens d'emploi (recherches en direct + URL d'origine si réelle)
    return {"detected_skills": [matching.label(s) for s in skills], "total": len(jobs), "jobs": jobs, "sources": src}


@app.get("/trainings/standard")
def standard_trainings(lang: str = "fr", user: dict = Depends(require("trainings"))):
    """Parcours standards (langues, développement web, management de projet, marketing digital), cours traduits dans `lang`."""
    return {"categories": [{"id": k, "courses": [catalog.localize(c, lang) for c in v]} for k, v in catalog.STANDARD.items()]}


_FALLBACK_GAPS = ["communication", "project_management", "agile"]  # compétences transverses utiles à tout profil


@app.post("/trainings/recommend")
def recommend(cv: CV, lang: str = "fr", user: dict = Depends(require("trainings"))):
    """Lacunes = compétences exigées par les offres les plus proches du profil et absentes du CV.
    Toujours au moins une proposition : sans offre proche ou sans lacune, on propose le prolongement naturel du profil
    (compétences voisines), puis des compétences transverses."""
    skills, titles = _cv_profile(cv)
    cands = TOOLS["search_jobs"](" ".join(skills + [titles]) or "emploi", None, None, 300)
    jobs = matching.rank_jobs(skills, titles, cands, 3)
    reason = "gaps"
    gaps = matching.find_gaps(jobs)
    if not gaps:  # aucune offre assez proche : on prend les offres les plus proches sans seuil
        loose = matching.rank_jobs(skills, titles, cands, 3, min_score=0.0)
        jobs = jobs or loose
        gaps = matching.find_gaps(loose)
        reason = "nearest_jobs"
    trainings = TOOLS["search_trainings"](gaps) if gaps else []
    if not trainings:
        have = set(skills)
        gaps = [g for g in _FALLBACK_GAPS if g not in have] or _FALLBACK_GAPS
        trainings = TOOLS["search_trainings"](gaps)
        reason = "general"
    return {
        "detected_skills": [matching.label(s) for s in skills],
        "target_jobs": [j["title"] for j in jobs],
        "gaps": [matching.label(g) for g in gaps],
        "reason": reason,
        "trainings": [catalog.localize(t, lang) for t in trainings],
    }


@app.post("/apply", status_code=202)
def apply(req: ApplyRequest, user: dict = Depends(require("apply"))):
    """N'ENVOIE RIEN : crée uniquement des demandes d'approbation (status=pending)."""
    created = []
    cv_pdf_b64 = None
    if req.cv_pdf_b64:  # le fichier doit être un vrai PDF de taille raisonnable
        try:
            raw = base64.b64decode(req.cv_pdf_b64, validate=True)
        except Exception:  # noqa: BLE001
            raise HTTPException(422, "cv_pdf_b64 invalide")
        if not raw.startswith(b"%PDF-") or len(raw) > 1_400_000:
            raise HTTPException(422, "Le CV joint doit être un PDF de moins de 1,4 Mo")
        cv_pdf_b64 = req.cv_pdf_b64
    if not APPLY_LIMIT.allow(user["sub"]):
        raise HTTPException(429, "Limite atteinte : 30 candidatures par heure. Réessayez plus tard.")
    skipped = []
    for url in dict.fromkeys(req.job_urls):                      # doublons de la même requête ignorés
        if any(a.get("job_url") == url and a.get("requester") == user["sub"] and a["status"] in ("pending", "sent", "ready", "simulated", "processing")
               for a in APPROVALS.values()):
            skipped.append({"job_url": url, "reason": "already_requested"})  # déjà en attente ou déjà envoyée : pas de second e-mail au recruteur
            continue
        job = _find_job(url)
        if mailbox.address(str(job.get("email") or ""))[1] in OPTOUT:
            skipped.append({"job_url": url, "reason": "opted_out"})   # ce recruteur a demandé à ne plus être contacté
            continue
        aid = uuid.uuid4().hex
        cfg = {"configurable": {"thread_id": aid}}
        GRAPH.invoke({"cv": {**req.cv.model_dump(), **({"_pdf_b64": cv_pdf_b64} if cv_pdf_b64 else {})}, "job": job}, cfg)  # s'arrête à l'interrupt de l'Approval Gate
        draft = GRAPH.get_state(cfg).values["draft"]
        APPROVALS[aid] = {
            "id": aid, "status": "pending", "requester": user["sub"], "draft": draft, "job_url": url,
            "hash": content_hash(draft), "expires_at": datetime.now(timezone.utc) + APPROVAL_TTL,
        }
        created.append({"approval_id": aid, "to": draft["to"], "channel": draft["channel"], "subject": draft["subject"]})
    PENDING.set(sum(a["status"] == "pending" for a in APPROVALS.values()))
    _persist()
    return {"pending": created, "skipped": skipped}


@app.get("/approvals")
def list_approvals(user: dict = Depends(require("approve"))):
    now = datetime.now(timezone.utc)
    return [{**a, "expires_at": a["expires_at"].isoformat()} for a in APPROVALS.values()
            if a["status"] == "pending" and a["expires_at"] > now and _may_decide(a, user)]


def _may_decide(a: dict, user: dict) -> bool:
    """Un utilisateur ne voit et ne décide que ses propres demandes ; seul l'administrateur voit tout."""
    return user.get("role") == "admin" or a.get("requester") == user.get("sub")


def _forget(aid: str) -> None:
    """Fin de vie d'une demande : on supprime l'état du graphe (il contient le CV complet, donnée personnelle)."""
    try:
        CHECKPOINTER.delete_thread(aid)
    except Exception:  # noqa: BLE001  (anciennes versions de langgraph : pas de delete_thread)
        pass


@app.post("/approvals/{aid}/decision")
def decide(aid: str, d: Decision, user: dict = Depends(require("approve"))):
    body = d.body
    if body is not None:
        body = mailbox.clean_text(body, 8000)
        if d.decision == "approve" and not body.strip():
            raise HTTPException(422, "Le message édité est vide.")
    with _STATE_LOCK:             # contrôle + passage à « processing » atomiques : deux clics ou deux approbateurs ne peuvent pas envoyer deux fois
        a = APPROVALS.get(aid)
        if not a or a["status"] != "pending" or not _may_decide(a, user):
            raise HTTPException(409, "Demande introuvable ou déjà traitée")  # usage unique (404/403 confondus : pas d'indice sur les demandes d'autrui)
        if datetime.now(timezone.utc) > a["expires_at"]:
            a["status"] = "expired"
            _persist()
            raise HTTPException(410, "Approbation expirée")
        if d.decision == "approve" and a["draft"].get("to", "").lower() in OPTOUT:
            raise HTTPException(422, "Ce destinataire a demandé à ne plus être contacté : envoi refusé.")
        if d.expected_hash and d.expected_hash != a["hash"]:
            raise HTTPException(409, "Le brouillon a changé depuis votre relecture : rechargez la demande.")
        a["status"] = "processing"
    cfg = {"configurable": {"thread_id": aid}}
    try:
        out = GRAPH.invoke(Command(resume={"decision": d.decision, "body": body}), cfg)
    except Exception:  # noqa: BLE001
        log.exception("approval=%s graph error", aid)
        a["status"] = "failed"; _persist()
        raise HTTPException(500, "Erreur interne pendant l'envoi : la demande est marquée en échec, aucun second envoi automatique.")
    a["status"] = out["status"]
    if "draft" in out:
        a["draft"] = out["draft"]
    if a["status"] == "sent":
        SENDS.labels("ok").inc()
        a["result"] = out.get("result")
        a["sent_at"] = datetime.now(timezone.utc)
        if a.get("kind") != "followup":
            _notify_n8n({"approval_id": aid, "status": "sent"})  # déclenche WF-3 (relance dans 7 jours)
    elif a["status"] == "simulated":  # DRY_RUN : aucun e-mail réel, donc ni relance J+7 ni statut « envoyé »
        SENDS.labels("simulated").inc()
        a["result"] = out.get("result")
    elif a["status"] == "ready":  # offre sans e-mail : lettre approuvée, à envoyer via le site de l'annonce
        a["result"] = out.get("result")
    elif a["status"] == "failed":
        SENDS.labels("error").inc()
        a["error"] = str(out.get("error", ""))[:200]
        log.error("approval=%s send failed: %s", aid, out.get("error"))
    if a["status"] in ("rejected", "failed", "simulated", "ready"):
        _forget(aid)                       # les relances (J+7) ne concernent que les envois réels : le CV de l'état « sent » est gardé pour elles
    log.info("approval=%s status=%s by=%s", aid, a["status"], user["sub"])
    PENDING.set(sum(x["status"] == "pending" for x in APPROVALS.values()))
    _persist()
    return {"id": aid, "status": a["status"], "result": a.get("result")}


# --------------------------------------------------------------------------- PDF & attestations
class TrainingRef(BaseModel):
    training_url: str


class CertRequest(TrainingRef):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr | None = None  # si fourni : l'attestation est aussi envoyée à cette adresse (sauf cours LMS : e-mail d'inscription)


class InternalCompletion(TrainingRef):
    user: str


COMPLETIONS: set[tuple[str, str]] = set()  # (user, training_url) — production : base de données
COMPLETION_SRC: dict[tuple[str, str], str] = {}  # origine : lms (vérifié par la plateforme) | internal (appel signé) | declared (dev, auto-déclaré)
CERTS: dict[str, dict] = {}

# plateforme de formation (Moodle) : voir backend/lms.py ; sans MOODLE_URL/MOODLE_TOKEN, tout reste comme avant
LMS = lms.from_env()
LMS_COURSES: dict[str, dict] = {c["url"]: c for c in lms.load_courses(base_url=os.getenv("MOODLE_URL", ""))}
ENROLLMENTS: dict[tuple[str, str], dict] = {}  # (user, training_url) -> {email, course_id, at}


def _mark_completed(user: str, url: str, source: str) -> None:
    COMPLETIONS.add((user, url))
    COMPLETION_SRC.setdefault((user, url), source)  # la première preuve (la plus forte si elle vient du LMS) est conservée
    if source == "lms":
        COMPLETION_SRC[(user, url)] = "lms"


def _find_training(url: str) -> dict:
    pts, _ = qdrant.scroll("trainings", scroll_filter=Filter(must=[FieldCondition(key="url", match=MatchValue(value=url))]), limit=1)
    if not pts:
        raise HTTPException(404, "Formation inconnue")
    return pts[0].payload


@app.post("/cv/pdf")
def cv_pdf(cv: CV, lang: str = "fr", user: dict = Depends(require("cv"))):
    lang = lang if lang in pdf_gen.LABELS else "en"
    pdf = pdf_gen.cv_pdf(TOOLS["build_europass_cv"](cv, lang), lang=lang)
    return Response(pdf, media_type="application/pdf", headers={"content-disposition": 'attachment; filename="CV_europass.pdf"'})


@app.post("/trainings/complete")
def complete_training(body: TrainingRef, user: dict = Depends(require("trainings"))):
    """Fin de formation. Cours de la plateforme : vérifiée auprès du LMS (jamais sur la seule parole du navigateur).
    Autres cours (liens de fournisseurs externes) : non vérifiable, donc auto-déclaration en développement uniquement."""
    _find_training(body.training_url)
    key = (user["sub"], body.training_url)
    course = LMS_COURSES.get(body.training_url)
    if course and LMS:
        enr = ENROLLMENTS.get(key)
        if not enr:
            raise HTTPException(409, "Inscrivez-vous d'abord au cours sur la plateforme")
        try:
            st = LMS.completion(enr["email"], course["lms_course_id"])
        except lms.LMSError as exc:
            log.warning("lms completion: %s", exc)
            raise HTTPException(502, "La plateforme de formation ne répond pas, réessayez dans un instant")
        if not st["completed"]:
            raise HTTPException(409, "Cours non terminé sur la plateforme")
        _mark_completed(user["sub"], body.training_url, "lms")
        return {"completed": True, "source": "lms"}
    if os.getenv("ENV", "dev") != "dev":
        raise HTTPException(409, "Formation externe : sa fin ne peut pas être vérifiée, l'attestation n'est délivrée que pour les cours de la plateforme")
    _mark_completed(user["sub"], body.training_url, "declared")
    return {"completed": True, "source": "declared"}


class EnrollReq(TrainingRef):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)


@app.get("/lms/status")
def lms_status(user: dict = Depends(require("trainings"))):
    return {"enabled": bool(LMS), "provider": "moodle" if LMS else None, "courses": sorted(LMS_COURSES) if LMS else []}


@app.post("/trainings/enroll")
def enroll_training(body: EnrollReq, user: dict = Depends(require("trainings"))):
    """Inscrit l'utilisateur (compte retrouvé par e-mail) au cours hébergé sur la plateforme et renvoie le lien d'accès."""
    course = LMS_COURSES.get(body.training_url)
    if not course:
        raise HTTPException(409, "Ce cours n'est pas hébergé sur la plateforme : suivez le lien du fournisseur")
    if not LMS:
        raise HTTPException(503, "Plateforme de formation non configurée (MOODLE_URL / MOODLE_TOKEN)")
    try:
        r = LMS.enroll(str(body.email), body.full_name, course["lms_course_id"])
    except lms.LMSError as exc:
        log.warning("lms enroll: %s", exc)
        raise HTTPException(409 if exc.code == "nouser" else 502, str(exc) if exc.code == "nouser" else "La plateforme de formation ne répond pas, réessayez dans un instant")
    ENROLLMENTS[(user["sub"], body.training_url)] = {"email": str(body.email).lower(), "course_id": course["lms_course_id"], "at": datetime.now(timezone.utc).isoformat()}
    return {"enrolled": True, "launch_url": r["launch_url"]}


@app.post("/internal/lms/webhook")
async def lms_webhook(request: Request):
    """Événement « cours terminé » envoyé par la plateforme, signé HMAC-SHA256 (en-tête x-lms-signature). Idempotent."""
    raw = await request.body()
    if len(raw) > 64_000 or not lms.verify_signature(os.getenv("LMS_WEBHOOK_SECRET", ""), raw, request.headers.get("x-lms-signature", "")):
        raise HTTPException(403)
    try:
        ev = lms.parse_event(json.loads(raw))
    except ValueError:
        raise HTTPException(422, "JSON invalide")
    if not ev:
        return {"ignored": True}
    email, cid = ev
    n = 0
    for (user, url), enr in list(ENROLLMENTS.items()):
        if enr["email"] == email and str(enr["course_id"]) == cid:
            _mark_completed(user, url, "lms")
            n += 1
    log.info("lms webhook: course=%s completions=%d", cid, n)
    return {"completed": n}


@app.post("/internal/trainings/complete")
def internal_complete(body: InternalCompletion, request: Request):
    _internal_only(request)
    _find_training(body.training_url)
    _mark_completed(body.user, body.training_url, "internal")
    return {"completed": True}


@tool("issue_certificate")
def issue_certificate_tool(user_id: str, full_name: str, training: dict, base_url: str, lang: str = "fr") -> tuple[str, bytes]:
    if (user_id, training["url"]) not in COMPLETIONS:
        raise HTTPException(403, "Formation non terminée")
    cid = uuid.uuid4().hex[:12]
    issued = datetime.now(timezone.utc).date().isoformat()
    CERTS[cid] = {"name": full_name, "training": training["title"], "issued": issued, "user": user_id, "source": COMPLETION_SRC.get((user_id, training["url"]), "declared"),
                  "sig": pdf_gen.sign(cid, full_name, training["title"], issued)}
    verified = CERTS[cid]["source"] in ("lms", "internal")  # cachet « vérifié » seulement si la plateforme a confirmé la fin de formation
    return cid, pdf_gen.certificate_pdf(cid, full_name, training, issued, f"{base_url}/certificates/verify/{cid}", lang, verified)


CERT_MAIL_USER = cert_mail.Limiter(5, 3600)  # 5 envois / heure / utilisateur
CERT_MAIL_CERT = cert_mail.Limiter(3, 86400)  # 3 envois / jour / attestation


def _mask(email: str) -> str:
    local, _, dom = email.partition("@")
    return f"{local[:1]}***@{dom}"


def _email_certificate(user: str, cid: str, to: str, lang: str, name: str, training: str, verify_url: str, pdf: bytes) -> str:
    """-> sent | failed | limited. N'échoue jamais : l'attestation reste téléchargeable même si l'e-mail ne part pas."""
    if not (CERT_MAIL_USER.allow(user) and CERT_MAIL_CERT.allow(cid)):
        return "limited"
    try:
        with httpx.Client(timeout=15) as c:
            r = c.post(f"{GMAIL_SERVICE_URL}/send", headers={"x-internal-secret": INTERNAL_SECRET},
                       json=cert_mail.build_message(to, lang, name, training, verify_url, pdf, cid))
            r.raise_for_status()
        SENDS.labels("ok").inc()
        log.info("certificate %s emailed to %s", cid, _mask(to))
        return "sent"
    except Exception as exc:  # noqa: BLE001
        SENDS.labels("error").inc()
        log.warning("certificate %s email failed: %s", cid, exc)
        return "failed"


@app.post("/certificates")
def issue_certificate(body: CertRequest, request: Request, lang: str = "fr", user: dict = Depends(require("trainings"))):
    training = catalog.localize(_find_training(body.training_url), lang)  # titre dans la langue de l'attestation
    lang = lang if lang in pdf_gen.LABELS else "en"
    base = str(request.base_url).rstrip("/")
    cid, pdf = TOOLS["issue_certificate"](user["sub"], body.full_name, training, base, lang)
    enr = ENROLLMENTS.get((user["sub"], body.training_url))
    to = enr["email"] if enr else (str(body.email) if body.email else "")  # cours de la plateforme : toujours l'adresse du compte inscrit
    mail = _email_certificate(user["sub"], cid, to, lang, body.full_name, training["title"], f"{base}/certificates/verify/{cid}", pdf) if to else "skipped"
    return Response(pdf, media_type="application/pdf",
                    headers={"content-disposition": f'attachment; filename="attestation_{cid}.pdf"', "x-certificate-id": cid,
                             "x-certificate-email": mail, "x-certificate-email-to": _mask(to) if to else "",
                             "access-control-expose-headers": "x-certificate-id, x-certificate-email, x-certificate-email-to"})


@app.get("/certificates/verify/{cid}")
def verify_certificate(cid: str):
    c = CERTS.get(cid)
    if not c:
        raise HTTPException(404, "Attestation inconnue")
    valid = hmac.compare_digest(c["sig"], pdf_gen.sign(cid, c["name"], c["training"], c["issued"]))
    return {"valid": valid, "name": c["name"], "training": c["training"], "issued": c["issued"], "completion": c.get("source", "declared"),
            "verified": c.get("source") in ("lms", "internal")}


# endpoints internes appelés par n8n
def _internal_only(request: Request) -> None:
    if not hmac.compare_digest(request.headers.get("x-internal-secret", ""), INTERNAL_SECRET):
        raise HTTPException(403)


def _notify_n8n(payload: dict) -> None:
    """Prévient le webhook n8n `application-status` (WF-3). Au mieux : un échec n'affecte jamais l'envoi déjà effectué."""
    url = os.getenv("N8N_WEBHOOK_URL", "").strip()
    if not url.startswith(("http://", "https://")):
        return

    def go() -> None:
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"content-type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=4).read()
        except Exception as exc:  # noqa: BLE001
            log.warning("n8n webhook: %s", exc)
    threading.Thread(target=go, daemon=True).start()


# --- WF-2 : alertes d'offres (abonnement de l'utilisateur, exécution par n8n)
ALERTS: dict[str, dict] = store.load(DATA_DIR, "alerts", {})  # user -> profil dérivé (persisté en JSON) ; production : table SQL


class AlertReq(BaseModel):
    cv: CV
    country: str | None = Field(default=None, max_length=2)
    city: str | None = Field(default=None, max_length=80)
    min_score: float = Field(default=alerts.DEFAULT_MIN_SCORE, ge=0.3, le=1.0)
    lang: Literal["fr", "en", "de", "es", "it", "ar"] = "fr"
    consent: bool = False  # l'utilisateur accepte de recevoir des alertes et que son profil de compétences soit conservé


@app.post("/jobs/alerts", status_code=201)
def subscribe_alerts(req: AlertReq, user: dict = Depends(require("search"))):
    if not req.consent:
        raise HTTPException(422, "Consentement requis pour activer les alertes")
    skills, titles = _cv_profile(req.cv)
    if not skills and not titles.strip():
        raise HTTPException(422, "Ajoutez des compétences ou une expérience : rien à comparer")
    ALERTS[user["sub"]] = alerts.make_alert(user["sub"], skills, titles, req.country, req.city, req.min_score, req.lang, str(req.cv.email))
    _persist()
    return alerts.public_view(ALERTS[user["sub"]])


@app.get("/jobs/alerts")
def my_alerts(user: dict = Depends(require("search"))):
    if user["sub"] not in ALERTS:
        raise HTTPException(404, "Aucune alerte active")
    return alerts.public_view(ALERTS[user["sub"]])


@app.delete("/jobs/alerts", status_code=204)
def unsubscribe_alerts(user: dict = Depends(require("search"))):
    ALERTS.pop(user["sub"], None)  # idempotent
    _persist()
    return Response(status_code=204)


class MatchRun(BaseModel):
    max_per_user: int = Field(default=5, ge=1, le=20)
    dry_run: bool = False


@app.post("/internal/matching/run")
def internal_matching(request: Request, body: MatchRun | None = None):
    """Appelé par n8n (WF-2) : renvoie une ligne par nouvelle correspondance {user, email, title, url, score, ...}."""
    _internal_only(request)
    body = body or MatchRun()
    res = alerts.run_matching(ALERTS, lambda q, c, city: TOOLS["search_jobs"](q, c, city, 300), body.max_per_user, body.dry_run)
    if not body.dry_run:
        _persist()
    log.info("matching run: alerts=%d matches=%d dry=%s", len(ALERTS), len(res), body.dry_run)
    return res


# --- WF-3 : suivi des candidatures et relance (soumise à l'Approval Gate)
class AppStatus(BaseModel):
    approval_id: str
    status: Literal["opened", "reply", "rejected", "withdrawn"]


@app.post("/internal/applications/status")
def internal_application_status(body: AppStatus, request: Request):
    """Appelé par n8n/Gmail quand un recruteur ouvre, répond ou refuse : stoppe la relance si besoin."""
    _internal_only(request)
    a = APPROVALS.get(body.approval_id)
    if not a:
        raise HTTPException(404, "Candidature inconnue")
    if a.get("tracking") in followup.STOP_STATUSES and body.status == "opened":
        return {"tracking": a["tracking"]}  # « ouvert » ne remplace pas une réponse
    a["tracking"] = body.status
    _persist()
    return {"tracking": a["tracking"]}


@app.post("/internal/applications/scan-replies")
def internal_scan_replies(request: Request, n: int = 30):
    """Appelé par n8n (planifié) : lit la boîte (lecture seule), repère les réponses des recruteurs à des candidatures envoyées, stoppe les relances ;
    un message STOP ajoute l'adresse à la liste d'opposition. Rien n'est envoyé."""
    _internal_only(request)
    data = _gmail_call("GET", "/inbox", params={"max": max(1, min(n, 30)), "q": ""})
    if data.get("demo"):
        return {"demo": True, "scanned": 0, "matched": []}
    msgs = [mailbox.with_analysis(m) for m in data.get("messages", [])]
    found = replies.match(APPROVALS.values(), msgs)
    for f in found:
        a = APPROVALS[f["approval_id"]]
        a["tracking"] = "reply"
        if f["optout"]:
            OPTOUT.add(f["email"])
    if found:
        _persist()
    log.info("scan replies: scanned=%d matched=%d", len(msgs), len(found))
    return {"demo": False, "scanned": len(msgs), "matched": [{"approval_id": f["approval_id"], "optout": f["optout"]} for f in found]}


class FollowupReq(BaseModel):
    approval_id: str


@app.post("/internal/followup/propose")
def internal_followup(body: FollowupReq, request: Request):
    """Appelé par n8n (WF-3, J+7) : crée une demande d'approbation de relance. N'ENVOIE RIEN."""
    _internal_only(request)
    parent = APPROVALS.get(body.approval_id)
    if not parent:
        raise HTTPException(404, "Candidature inconnue")
    existing = APPROVALS.get(parent.get("followup_id", ""))
    if existing and existing["status"] == "pending" and datetime.now(timezone.utc) > existing["expires_at"]:
        existing["status"] = "expired"  # l'utilisateur n'a pas répondu à temps : on peut reproposer
    now = datetime.now(timezone.utc)
    ok, reason, due = followup.eligibility(parent, existing, now)
    if not ok:
        return {"proposed": False, "reason": reason, "approval_id": (existing or {}).get("id") if reason == "already_proposed" else None,
                "eligible_at": due.isoformat() if due else None}
    state = GRAPH.get_state({"configurable": {"thread_id": body.approval_id}}).values
    cv = {k: v for k, v in state.get("cv", {}).items() if k != "_pdf_b64"}
    draft = followup.build_draft(body.approval_id, parent["draft"], state.get("job", {}), cv.get("full_name", ""), parent.get("sent_at"))
    aid = uuid.uuid4().hex
    GRAPH.invoke({"cv": cv, "job": state.get("job", {}), "draft": draft}, {"configurable": {"thread_id": aid}})  # s'arrête à l'Approval Gate
    APPROVALS[aid] = {"id": aid, "status": "pending", "kind": "followup", "parent": body.approval_id, "requester": parent["requester"],
                      "draft": draft, "hash": content_hash(draft), "expires_at": now + APPROVAL_TTL}
    parent["followup_id"] = aid
    _persist()
    PENDING.set(sum(a["status"] == "pending" for a in APPROVALS.values()))
    log.info("followup proposed parent=%s approval=%s", body.approval_id, aid)
    return {"proposed": True, "approval_id": aid, "to": draft["to"], "subject": draft["subject"], "requester": parent["requester"], "lang": draft["lang"]}


@app.post("/internal/jobs/index")
def internal_index(jobs: list[dict], request: Request):
    _internal_only(request)
    n = 0
    for j in jobs:
        if {"title", "url", "country"} <= j.keys():
            index_doc("jobs", j)
            n += 1
    return {"indexed": n}


@app.get("/metrics")
def metrics(user: dict = Depends(require("metrics"))):
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
