import os
"""Test de fumée des routes n8n sans installer FastAPI/Qdrant/LangGraph (ils sont remplacés par des doublures) : python tests/n8n_routes_smoke.py
Pour un test avec le vrai serveur, utilisez TestClient (voir ARCHITECTURE.md)."""
import sys, types, os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pydantic; pydantic.EmailStr = str
class HTTPException(Exception):
    def __init__(s, status_code, detail=None): s.status_code, s.detail = status_code, detail
class _App:
    def __getattr__(s, n): return lambda *a, **k: (lambda f: f)
def mod(name, **kw):
    m = types.ModuleType(name); m.__dict__.update(kw); sys.modules[name] = m; return m
mod('fastapi', FastAPI=lambda **k: _App(), Depends=lambda f=None: None, Body=lambda *a, **k: None, HTTPException=HTTPException, Request=object, Response=lambda *a, **k: ("resp", a, k))
mod('fastapi.responses', FileResponse=MagicMock())
mod('prometheus_client', Counter=MagicMock(), Gauge=MagicMock(), Histogram=MagicMock(), generate_latest=MagicMock(), CONTENT_TYPE_LATEST="x")
mod('jwt', PyJWTError=Exception, decode=MagicMock(), encode=MagicMock())
for n in ['qdrant_client', 'qdrant_client.models', 'langgraph', 'langgraph.types', 'langgraph.checkpoint', 'langgraph.checkpoint.memory', 'langgraph.graph']:
    sys.modules[n] = MagicMock()
for _n in ("httpx", "arabic_reshaper", "bidi", "bidi.algorithm"):  # facultatifs pour ce test
    try:
        __import__(_n)
    except ImportError:
        sys.modules[_n] = MagicMock()
from backend import app
from backend.seed_data import SEED_JOBS
class Req:
    def __init__(s, secret=None): s.headers = {"x-internal-secret": secret} if secret is not None else {}
good = Req(app.INTERNAL_SECRET)
app.TOOLS["search_jobs"] = lambda q, c=None, city=None, k=5: [j for j in SEED_JOBS if not c or j["country"] == c]
def code(f, *a, **k):
    try: return f(*a, **k)
    except HTTPException as e: return e.status_code
CV = app.CV
cv = CV(full_name="Sara Haddad", email="sara@example.com", skills=["python", "sql", "docker", "fastapi", "git"],
        experiences=[app.Experience(title="Développeur Python", company="X", start="2021-01", description="API REST")])
# --- WF-2
assert code(app.internal_matching, Req("bad"), None) == 403 and code(app.internal_matching, Req(), None) == 403
assert code(app.subscribe_alerts, app.AlertReq(cv=cv, country="FR", consent=False), {"sub": "u1"}) == 422
v = app.subscribe_alerts(app.AlertReq(cv=cv, country="FR", lang="fr", consent=True), {"sub": "u1"}); assert v["country"] == "FR" and "email" not in v
assert "sara@example.com" not in str(app.ALERTS["u1"]["skills"])
dry = app.internal_matching(good, app.MatchRun(dry_run=True)); assert dry and app.ALERTS["u1"]["notified"] == []
r1 = app.internal_matching(good, None); r2 = app.internal_matching(good, None)
assert r1 and all(x["score"] >= 0.6 for x in r1) and not ({x["url"] for x in r1} & {x["url"] for x in r2}), (len(r1), len(r2))
assert app.my_alerts({"sub": "u1"})["notified_count"] == len(r1) + len(r2)
app.unsubscribe_alerts({"sub": "u1"}); assert code(app.my_alerts, {"sub": "u1"}) == 404 and app.internal_matching(good, None) == []
# --- WF-3
class G:
    calls = []
    def get_state(s, cfg): return types.SimpleNamespace(values={"cv": {"full_name": "Sara Haddad", "_pdf_b64": "AAAA"}, "job": {"title": "Développeur Python", "company": "Acme"}})
    def invoke(s, st, cfg): s.calls.append((st, cfg))
app.GRAPH = G()
now = datetime.now(timezone.utc)
app.APPROVALS["p1"] = {"id": "p1", "status": "sent", "requester": "u1", "sent_at": now - timedelta(days=7),
                       "draft": {"to": "rh@acme.fr", "subject": "Candidature : Développeur Python", "lang": "fr", "channel": "email"}}
assert code(app.internal_followup, app.FollowupReq(approval_id="p1"), Req("bad")) == 403
assert code(app.internal_followup, app.FollowupReq(approval_id="nope"), good) == 404
r = app.internal_followup(app.FollowupReq(approval_id="p1"), good)
assert r["proposed"] and r["to"] == "rh@acme.fr" and r["subject"].startswith("Re: ") and r["requester"] == "u1", r
st, cfg = G.calls[0]; assert st["draft"]["kind"] == "followup" and "_pdf_b64" not in st["cv"] and cfg["configurable"]["thread_id"] == r["approval_id"]
a2 = app.APPROVALS[r["approval_id"]]; assert a2["status"] == "pending" and a2["kind"] == "followup" and a2["hash"] == app.content_hash(a2["draft"])
assert "Sara Haddad" in a2["draft"]["body"] and "Acme" in a2["draft"]["body"]
again = app.internal_followup(app.FollowupReq(approval_id="p1"), good); assert again == {"proposed": False, "reason": "already_proposed", "approval_id": r["approval_id"], "eligible_at": None}, again
# réponse reçue => plus de relance
app.APPROVALS["p2"] = {**app.APPROVALS["p1"], "id": "p2"}; app.APPROVALS["p2"].pop("followup_id", None)
assert app.internal_application_status(app.AppStatus(approval_id="p2", status="reply"), good) == {"tracking": "reply"}
assert app.internal_application_status(app.AppStatus(approval_id="p2", status="opened"), good) == {"tracking": "reply"}
assert app.internal_followup(app.FollowupReq(approval_id="p2"), good)["reason"] == "reply_received"
# trop tôt / pas envoyé / lien
app.APPROVALS["p3"] = {k: v for k, v in app.APPROVALS["p1"].items() if k != "followup_id"} | {"id": "p3", "sent_at": now - timedelta(days=1)}
t = app.internal_followup(app.FollowupReq(approval_id="p3"), good); assert t["reason"] == "too_early" and t["eligible_at"]
app.APPROVALS["p4"] = {k: v for k, v in app.APPROVALS["p1"].items() if k != "followup_id"} | {"id": "p4", "status": "pending"}; assert app.internal_followup(app.FollowupReq(approval_id="p4"), good)["reason"] == "not_sent"
# relance expirée => nouvelle proposition possible
app.APPROVALS[r["approval_id"]]["expires_at"] = now - timedelta(hours=1)
r3 = app.internal_followup(app.FollowupReq(approval_id="p1"), good); assert r3["proposed"] and r3["approval_id"] != r["approval_id"]
# secret comparé en temps constant : vide refusé ; /internal/jobs/index protégé
assert code(app.internal_index, [], Req("")) == 403 and app.internal_index([], good) == {"indexed": 0}

# --- LMS : inscription, vérification réelle de la fin de cours, webhook signé
import base64, asyncio, hashlib, hmac, json as _json
from backend import lms as _lms
URL = next(t["url"] for t in app.catalog.all_courses())          # une formation connue de l'index (qdrant est une doublure : on la simule)
app._find_training = lambda url: {"url": url, "title": "Cours maison"}
app.LMS_COURSES[URL] = {"url": URL, "lms_course_id": 12}
class FakeLMS:
    done = False; enrolled = []
    def enroll(self, email, name, cid): self.enrolled.append((email, name, cid)); return {"user_id": 1, "launch_url": "https://lms.example.org/course/view.php?id=%d" % cid}
    def completion(self, email, cid): return {"enrolled": True, "completed": self.done}
fl = FakeLMS(); app.LMS = fl
U = {"sub": "u1"}
assert code(app.complete_training, app.TrainingRef(training_url=URL), U) == 409           # pas inscrit
assert code(app.enroll_training, app.EnrollReq(training_url="https://autre.example/x", email="sara@example.com", full_name="Sara"), U) == 409
e = app.enroll_training(app.EnrollReq(training_url=URL, email="Sara@Example.com", full_name="Sara H"), U); assert e["enrolled"] and e["launch_url"].endswith("id=12")
assert code(app.complete_training, app.TrainingRef(training_url=URL), U) == 409           # inscrit mais cours non terminé : le navigateur ne décide pas
fl.done = True; assert app.complete_training(app.TrainingRef(training_url=URL), U) == {"completed": True, "source": "lms"}
fl.done = False; app.COMPLETIONS.clear(); app.COMPLETION_SRC.clear()
class WReq:
    def __init__(s, raw, sig): s.raw, s.headers = raw, ({"x-lms-signature": sig} if sig is not None else {})
    async def body(s): return s.raw
os.environ["LMS_WEBHOOK_SECRET"] = "whsec"
raw = _json.dumps({"event": "course_completed", "user_email": "sara@example.com", "course_id": 12}).encode()
sig = "sha256=" + hmac.new(b"whsec", raw, hashlib.sha256).hexdigest()
run = lambda r: asyncio.run(app.lms_webhook(r))
assert code(run, WReq(raw, "sha256=00")) == 403 and code(run, WReq(raw, None)) == 403
assert run(WReq(raw, sig)) == {"completed": 1} and ("u1", URL) in app.COMPLETIONS and app.COMPLETION_SRC[("u1", URL)] == "lms"
assert run(WReq(raw, sig)) == {"completed": 1}                                              # idempotent
other = _json.dumps({"event": "course_completed", "user_email": "sara@example.com", "course_id": 99}).encode()
assert run(WReq(other, "sha256=" + hmac.new(b"whsec", other, hashlib.sha256).hexdigest())) == {"completed": 0}
assert run(WReq(b"[]", "sha256=" + hmac.new(b"whsec", b"[]", hashlib.sha256).hexdigest())) == {"ignored": True}
# cours externe : auto-déclaration seulement en dev
app.LMS_COURSES.clear(); app.COMPLETIONS.clear(); app.COMPLETION_SRC.clear()
os.environ["ENV"] = "dev"; assert app.complete_training(app.TrainingRef(training_url=URL), U)["source"] == "declared"
os.environ["ENV"] = "prod"; assert code(app.complete_training, app.TrainingRef(training_url=URL), {"sub": "u2"}) == 409
os.environ["ENV"] = "dev"
assert app.lms_status(U)["enabled"] is True

# --- Attestation : cachet + envoi par e-mail à l'utilisateur
class FakeHTTP:
    posts = []; fail = False
    class Client:
        def __init__(self, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, url, headers=None, json=None):
            FakeHTTP.posts.append((url, headers, json))
            if FakeHTTP.fail: raise RuntimeError("gmail down")
            return types.SimpleNamespace(raise_for_status=lambda: None)
    HTTPError = Exception
app.httpx = FakeHTTP
app.LMS_COURSES[URL] = {"url": URL, "lms_course_id": 12}
creq = types.SimpleNamespace(base_url="http://t/")
def cert(user, **kw):
    r = app.issue_certificate(app.CertRequest(training_url=URL, full_name="Sara Haddad", **kw), creq, "fr", {"sub": user})
    return r[2]["headers"], r
app._mark_completed("u1", URL, "lms"); app._mark_completed("u3", URL, "declared"); app._mark_completed("u4", URL, "lms")
h, r = cert("u1", email="sara@example.com")                      # u1 est inscrit (ENROLLMENTS) : l'adresse du compte prime sur celle de la requête
assert h["x-certificate-email"] == "sent" and h["x-certificate-email-to"] == "s***@example.com", h
url, hdr, payload = FakeHTTP.posts[-1]
assert url.endswith("/send") and hdr["x-internal-secret"] == app.INTERNAL_SECRET and payload["to"] == "sara@example.com"
assert base64.b64decode(payload["attachment"]["data_b64"]) == r[1][0] and r[1][0].startswith(b"%PDF") and "http://t/certificates/verify/" in payload["body"]
cid = h["x-certificate-id"]; v = app.verify_certificate(cid); assert v["valid"] and v["verified"] and v["completion"] == "lms"
h, _ = cert("u3", email="x@y.org"); assert h["x-certificate-email"] == "sent" and FakeHTTP.posts[-1][2]["to"] == "x@y.org"
assert app.verify_certificate(h["x-certificate-id"])["verified"] is False                       # auto-déclarée : cachet « DEMO », pas vérifiée
h, _ = cert("u4"); assert h["x-certificate-email"] == "skipped" and h["x-certificate-email-to"] == ""
n = len(FakeHTTP.posts); FakeHTTP.fail = True; app._mark_completed("u5", URL, "lms")
h, _ = cert("u5", email="z@z.org"); assert h["x-certificate-email"] == "failed"                  # le téléchargement marche quand même
FakeHTTP.fail = False
for i in range(6):                                                                             # limite par utilisateur : 5 / heure, la 6e est refusée
    app._mark_completed("u6", URL, "lms"); last, _ = cert("u6", email="l@l.org")
assert last["x-certificate-email"] == "limited"
# --- offres réelles (fournisseurs simulés)
LIVE = [{"title": "Développeur Python", "company": "Réel SAS", "country": "FR", "city": "Lyon", "skills": "", "description": "API REST python sql",
         "url": "https://www.adzuna.fr/land/ad/42", "email": "", "source": "adzuna", "posted": "2026-10-20"}]
seen_q, indexed = [], []
app.jobsources.fetch = lambda q, iso="", city="", **k: (seen_q.append((q, iso, city)) or ([dict(j) for j in LIVE], {"adzuna": {"ok": True, "count": 1}}))
app.index_doc = lambda col, doc: indexed.append(doc)
app.TOOLS["search_jobs"] = lambda q, c=None, city=None, k=5: []
r = app.search_jobs_endpoint("python", "France", "Lyon", {"sub": "u1"})
assert seen_q[-1] == ("python", "FR", "Lyon") and r["total"] == 1 and r["jobs"][0]["url"].endswith("/42") and r["sources"]["adzuna"]["ok"]
assert r["jobs"][0]["links"][0]["name"] == "Offre d'origine" and indexed and indexed[-1]["skills"]
m = app.match(cv, None, None, {"sub": "u1"})
assert seen_q[-1][0] == "Développeur Python" and m["total"] >= 1 and m["jobs"][0]["company"] == "Réel SAS" and "sources" in m, (seen_q, m["total"])
# --- factures
req = app.InvoiceReq(issue_date="2026-10-24", due_date="2026-11-23", number="FA-2026-0001", regime="standard", deposit="0",
                     seller=app.InvParty(name="S", address="A", country="fr", tax_id="1", vat_number="FR1", iban="FR76"), client=app.InvParty(name="C", address="B"),
                     lines=[app.InvLine(description="x", qty="2", unit_price="10,10", vat="20")])
pv = app.invoice_preview(req, {"sub": "u1"}); assert pv["total_ht"] == "20.20" and pv["total_vat"] == "4.04" and pv["total_ttc"] == "24.24" and pv["warnings"] == [], pv
rp = app.invoice_pdf_route(req, {"sub": "u1"}); assert rp[1][0][:5] == b"%PDF-" and rp[2]["headers"]["x-invoice-total"] == "24.24", rp[2]["headers"]
bad = app.InvoiceReq(issue_date="2026-10-24", seller=app.InvParty(), client=app.InvParty(), lines=[app.InvLine(qty="-1", unit_price="5")])
assert code(app.invoice_preview, bad, {"sub": "u1"}) == 422
assert app.invoice_next_number("FA-2025-0009", "invoice", {"sub": "u1"})["number"].endswith("-0001")
cn = app.InvoiceReq(doc_type="credit_note", ref_number="FA-2026-0001", ref_date="2026-10-01", notes="Retour", issue_date="2026-10-24", number="AV-2026-0001", deposit="50",
                    seller=app.InvParty(name="S", address="A", country="fr", tax_id="12345678900012", vat_number="FR1", iban="FR76"), client=app.InvParty(name="C", address="B", country="fr"),
                    lines=[app.InvLine(description="x", qty="1", unit_price="10", vat="20")])
fx = app.invoice_facturx(cn, {"sub": "u1"}); assert fx[1][0][:5] == b"%PDF-" and fx[2]["headers"]["x-facturx-profile"] == "EN 16931" and "attachment" in fx[2]["headers"]["content-disposition"], fx[2]
assert code(app.invoice_facturx, app.InvoiceReq(doc_type="quote", issue_date="2026-10-24", seller=app.InvParty(), client=app.InvParty(), lines=[app.InvLine(unit_price="1")]), {"sub": "u1"}) == 422
assert code(app.invoice_facturx, bad, {"sub": "u1"}) == 422
assert app.invoice_next_number("", "quote", {"sub": "u1"})["number"].startswith("DE-")
# --- LinkedIn
li = app.LinkedInReq(lang="en", headline="Looking for opportunities", about="I look for a job.", target_role="Python developer FastAPI Docker", skills=["Python"],
                     experiences=[app.LiExp(title="Developer", company="Acme", description="APIs")], checks=app.LiChecks(photo=True))
la = app.linkedin_audit(li, {"sub": "u1"})
assert 0 < la["audit"]["score"] < 60 and la["audit"]["keywords"]["missing"] and la["headlines"] and "Acme" in la["prompt"] and isinstance(la["ai_ready"], bool), la["audit"]["score"]
os.environ.pop("ANTHROPIC_API_KEY", None)
assert code(app.linkedin_boost, li, {"sub": "u1"}) == 503
# --- stratégie / RSE / conformité
sd = app.strategy_diagnostic(app.StrategyReq(country="FR", employees=60, turnover_m=8, goal="transition", answers={"cp_data": 0, "st_kpi": 2, "cs_measure": 1}, done=["cp_data"]), {"sub": "u1"})
assert sd["answered"] == 3 and sd["progress"] == 50 and any(g["id"] == "fr_egapro" for g in sd["regulations"]), sd
assert code(app.growth_chat, app.GrowthReq(service=5, messages=[app.GrowthMsg(role="user", content="x")]), {"sub": "u1"}) in (422, 503)
import backend.growth as _g
assert "Strategy, ESG" in _g.build_system(6, "en", {"name": "Acme"}) and "Facebook" not in _g.build_system(6, "fr", {}).split("SERVICE 6")[0]
# --- e-mails reçus (bouton 2) : lecture, brouillon, envoi seulement après validation
_calls = []
_demo = {"id": "m123456", "thread_id": "t123456", "from": "Claire <claire@client.test>", "to": "me@x.test", "subject": "Demande de devis", "date": "Tue, 21 Oct 2026", "body": "Bonjour, pouvez-vous m'envoyer un devis pour 20 postes ? Merci.", "message_id": "<a@x>", "references": ""}
_auto = {**_demo, "id": "n123456", "from": "Promo <newsletter@promo.test>", "auto": True}
def _fake_gmail(method, path, **kw):
    _calls.append((method, path, kw))
    if path == "/inbox": return {"demo": True, "messages": [_demo, _auto]}
    if path.startswith("/message/"): return _auto if path.endswith("n123456") else _demo
    if path == "/send": return {"dryRun": True, "to": kw["json"]["to"]}
    raise AssertionError(path)
app._gmail_call = _fake_gmail
ib = app.mail_inbox(15, "", {"sub": "u1"}); assert ib["report"]["total"] == 2 and len(ib["report"]["to_reply"]) == 1 and len(ib["report"]["ignored"]) == 1
dr = app.mail_draft(app.MailDraftReq(message=app.MailMsg(id="m123456", from_name="Claire", from_email="claire@client.test", subject="Demande de devis", body=_demo["body"])), {"sub": "u1"})
assert dr["to"] == "claire@client.test" and "[" in dr["body"] and not any(c[1] == "/send" for c in _calls)       # brouillon : rien n'est envoyé
assert code(app.mail_send, app.MailSendReq(message_id="m123456", subject="Re: Demande de devis", body="Bonjour"), {"sub": "u1"}) == 422     # sans validation
assert not any(c[1] == "/send" for c in _calls)
ok = app.mail_send(app.MailSendReq(confirmed=True, message_id="m123456", to="pirate@evil.test", subject="Re: Demande de devis", body="Bonjour, voici notre réponse."), {"sub": "u1"})
assert ok["to"] == "claire@client.test" and ok["dry_run"], ok                                                  # le destinataire vient du serveur, pas du client
assert code(app.mail_send, app.MailSendReq(confirmed=True, message_id="n123456", subject="Re: x", body="x"), {"sub": "u1"}) == 422          # message automatique : refusé
# --- limites de débit : les appels IA sont plafonnés par utilisateur
from backend import cert_mail as _cm
app.LLM_LIMIT = _cm.Limiter(2, 3600)
_lg = app.GrowthReq(service=1, messages=[app.GrowthMsg(role="user", content="x")])
assert [code(app.growth_chat, _lg, {"sub": "rl"}) for _ in range(3)] == [503, 503, 429]
assert code(app.growth_chat, _lg, {"sub": "autre"}) == 503                 # le plafond est par utilisateur
# --- service 4 : retouche photo
import base64 as _b64, io as _io
from PIL import Image as _Im
_buf = _io.BytesIO(); _Im.new("RGB", (300, 200), (120, 130, 140)).save(_buf, "JPEG")
_uri = "data:image/jpeg;base64," + _b64.b64encode(_buf.getvalue()).decode()
_pl = app.images_plan(app.RetouchPlanReq(scene="food", usage="social", ratio="4:5", src_w=300, src_h=200), {"sub": "u1"})
assert _pl["output"]["w"] == 1080 and _pl["output"]["h"] == 1350 and any(s["id"] == "upscale" for s in _pl["steps"]), _pl
_en = app.images_enhance(app.RetouchEnhanceReq(image=_uri, target_long=600), {"sub": "u1"})
assert _en["width"] == 600 and _en["height"] == 400 and _en["image"].startswith("data:image/jpeg"), _en
assert code(app.images_enhance, app.RetouchEnhanceReq(image="data:image/png;base64,bm9wZQ=="), {"sub": "u1"}) == 422
app.HEAVY_LIMIT = _cm.Limiter(1, 3600)
app.images_enhance(app.RetouchEnhanceReq(image=_uri), {"sub": "h"})
assert code(app.images_enhance, app.RetouchEnhanceReq(image=_uri), {"sub": "h"}) == 429
# --- service 3 : spot vidéo
_sp = app.spots_campaign(app.SpotReq(product="Crème bio", audience="femmes 30-45", pain="peau sèche", benefit="hydratation douce", offer="-20 % code LAUNCH", tone="humor", duration=60, platform="tiktok"), {"sub": "u1"})
assert _sp["angle"] == "hu" and _sp["beats"][-1]["end"] == 60 and _sp["format"]["ratio"] == "9:16" and len(_sp["beats"]) == 7, _sp
assert code(app.spots_campaign, app.SpotReq.model_construct(product="  ", audience="", pain="", benefit="", offer="", tone="dynamic", duration=30, platform="reels", angle="auto"), {"sub": "u1"}) in (400, 422)
# --- bouton 7 : tuteur d'autoformation
# --- connexion par code d'accès
from types import SimpleNamespace as _NS
app.ACCESS_CODES = {"Code-Test-0001": "approver"}
app.LOGIN_LIMIT = _cm.Limiter(3, 900)
_rq = _NS(client=_NS(host="1.2.3.4"))
_ok = app.auth_login(app.LoginReq(code="Code-Test-0001"), _rq)
assert _ok["role"] == "approver" and _ok["token"]
assert code(app.auth_login, app.LoginReq(code="mauvais"), _rq) == 401
assert code(app.auth_login, app.LoginReq(code="mauvais2"), _rq) == 401
assert code(app.auth_login, app.LoginReq(code="Code-Test-0001"), _rq) == 429       # 3 tentatives max : la 4e est refusée même avec le bon code
app.ACCESS_CODES = {}
assert code(app.auth_login, app.LoginReq(code="x"), _rq) == 404
# --- export PDF générique
app.HEAVY_LIMIT = _cm.Limiter(50, 3600)
_pdf = app.export_pdf(app.ExportReq(title="Plan", lang="fr", blocks=[{"t": "h2", "text": "Titre"}, {"t": "li", "text": "Étape"}, {"t": "table", "head": ["a", "b"], "rows": [["1", "2"]]}]), {"sub": "u1"})
assert _pdf[0] == "resp" and _pdf[1][0][:5] == b"%PDF-" and _pdf[2]["media_type"] == "application/pdf", _pdf[2]
assert code(app.export_pdf, app.ExportReq(title="x", blocks=[{"t": "zzz"}]), {"sub": "u1"}) == 422
app.HEAVY_LIMIT = _cm.Limiter(1, 3600)
app.export_pdf(app.ExportReq(title="x", blocks=[{"t": "p", "text": "a"}]), {"sub": "e"})
assert code(app.export_pdf, app.ExportReq(title="x", blocks=[{"t": "p", "text": "a"}]), {"sub": "e"}) == 429
print("HARNESS OK")
