"""Intégration d'une plateforme de formation (LMS) : Moodle via ses Web Services REST, + réception signée des événements de fin de cours.

Flux :
  1. L'utilisateur clique « S'inscrire » -> `Moodle.enroll` retrouve (ou crée, si autorisé) son compte par e-mail et l'inscrit au cours.
  2. Il suit le cours sur Moodle (lien `launch_url`).
  3. La fin de cours arrive de deux façons : Moodle appelle `POST /internal/lms/webhook` (signé HMAC, JSON simple ou instruction xAPI),
     ou l'utilisateur clique « Terminé » et le backend interroge Moodle (`Moodle.completion`) : on ne croit jamais le navigateur.
  4. Seule une complétion vérifiée par le LMS donne l'attestation « vérifiée » ; les liens vers des fournisseurs externes ne sont pas vérifiables.

Configuration (.env) : MOODLE_URL (https), MOODLE_TOKEN (jeton du service web, droits minimaux), LMS_WEBHOOK_SECRET,
MOODLE_AUTO_CREATE_USERS=false, LMS_COURSES_FILE (défaut backend/lms_courses.json).
Fonctions Moodle utilisées : core_user_get_users_by_field, core_user_create_users, enrol_manual_enrol_users,
core_completion_get_course_completion_status. Aucune dépendance : bibliothèque standard.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

STUDENT_ROLE_ID = 5  # rôle « Étudiant » par défaut dans Moodle
COMPLETED_VERBS = ("completed", "passed")
GENERIC_EVENTS = {"course_completed", "completed", "passed"}


class LMSError(Exception):
    def __init__(self, message: str, code: str = ""):
        super().__init__(message)
        self.code = code


def _flatten(params: dict, prefix: str = "") -> dict[str, str]:
    """{"values": ["a"]} -> {"values[0]": "a"} : syntaxe attendue par les Web Services Moodle."""
    out: dict[str, str] = {}
    for k, v in params.items():
        key = f"{prefix}[{k}]" if prefix else str(k)
        if isinstance(v, dict):
            out.update(_flatten(v, key))
        elif isinstance(v, (list, tuple)):
            out.update(_flatten({str(i): x for i, x in enumerate(v)}, key))
        elif isinstance(v, bool):
            out[key] = "1" if v else "0"
        elif v is not None:
            out[key] = str(v)
    return out


def _default_post(url: str, data: dict[str, str], timeout: float = 15.0):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as e:
        raise LMSError(f"Plateforme : HTTP {e.code}") from None
    except (OSError, ValueError) as e:
        raise LMSError("Plateforme injoignable") from None  # ne jamais relayer le détail : l'URL contient des paramètres sensibles


class Moodle:
    def __init__(self, base_url: str, token: str, post: Callable = _default_post, auto_create: bool = False, role_id: int = STUDENT_ROLE_ID):
        u = urllib.parse.urlsplit(base_url)
        if u.scheme != "https" and u.hostname not in ("localhost", "127.0.0.1"):
            raise LMSError("MOODLE_URL doit être en https (le jeton transite dans la requête)")
        self.base, self.token, self.post, self.auto_create, self.role_id = base_url.rstrip("/"), token, post, auto_create, role_id

    def call(self, function: str, **params):
        data = {"wstoken": self.token, "wsfunction": function, "moodlewsrestformat": "json", **_flatten(params)}
        res = self.post(f"{self.base}/webservice/rest/server.php", data)
        if isinstance(res, dict) and res.get("exception"):
            raise LMSError(str(res.get("message") or res["exception"])[:200], str(res.get("errorcode", "")))
        return res

    def launch_url(self, course_id: int) -> str:
        return f"{self.base}/course/view.php?id={int(course_id)}"

    def find_user(self, email: str) -> int | None:
        users = self.call("core_user_get_users_by_field", field="email", values=[email.lower()])
        return int(users[0]["id"]) if users else None

    def ensure_user(self, email: str, name: str) -> int:
        uid = self.find_user(email)
        if uid:
            return uid
        if not self.auto_create:
            raise LMSError("Aucun compte sur la plateforme avec cet e-mail : créez-le d'abord ou activez MOODLE_AUTO_CREATE_USERS", "nouser")
        first, _, last = (name.strip() or email.split("@")[0]).partition(" ")
        username = re.sub(r"[^a-z0-9._-]", "", email.lower().split("@")[0])[:60] or "user"
        res = self.call("core_user_create_users", users=[{"username": f"{username}", "createpassword": True, "firstname": first or username,
                                                         "lastname": last or "-", "email": email.lower(), "auth": "manual"}])
        return int(res[0]["id"])

    def enroll(self, email: str, name: str, course_id: int) -> dict:
        uid = self.ensure_user(email, name)
        self.call("enrol_manual_enrol_users", enrolments=[{"roleid": self.role_id, "userid": uid, "courseid": int(course_id)}])
        return {"user_id": uid, "launch_url": self.launch_url(course_id)}

    def completion(self, email: str, course_id: int) -> dict:
        uid = self.find_user(email)
        if not uid:
            return {"enrolled": False, "completed": False}
        try:
            res = self.call("core_completion_get_course_completion_status", courseid=int(course_id), userid=uid)
        except LMSError as e:
            if e.code in ("notenroled", "notenrolled"):
                return {"enrolled": False, "completed": False}
            raise
        return {"enrolled": True, "completed": bool((res or {}).get("completionstatus", {}).get("completed"))}


def from_env(env=None, post: Callable = _default_post) -> Moodle | None:
    env = os.environ if env is None else env
    url, token = (env.get("MOODLE_URL") or "").strip(), (env.get("MOODLE_TOKEN") or "").strip()
    if not url or not token:
        return None
    return Moodle(url, token, post, str(env.get("MOODLE_AUTO_CREATE_USERS", "false")).lower() == "true")


# --------------------------------------------------------------------------- catalogue des cours hébergés sur le LMS
def courses_path(env=None) -> Path:
    env = os.environ if env is None else env
    return Path(env.get("LMS_COURSES_FILE") or Path(__file__).with_name("lms_courses.json"))


def load_courses(path: Path | None = None, base_url: str = "") -> list[dict]:
    """Cours du LMS décrits dans un JSON : [{"lms_course_id": 7, "title": "...", "skills": "python sql", ...}] ; entrées invalides ignorées.
    Format catalogue : même clés que catalog._mk, plus `lms_course_id` ; `url` par défaut = page du cours sur le LMS."""
    path = path or courses_path()
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for r in rows if isinstance(rows, list) else []:
        try:
            cid, title = int(r["lms_course_id"]), str(r["title"]).strip()
        except (KeyError, TypeError, ValueError):
            continue
        url = str(r.get("url") or (f"{base_url.rstrip('/')}/course/view.php?id={cid}" if base_url else "")).strip()
        if cid <= 0 or not title or not url.startswith("https://"):
            continue
        summary = str(r.get("summary", ""))
        out.append({"title": title, "provider": str(r.get("provider", "Plateforme de formation")), "level": str(r.get("level", "")),
                    "duration": str(r.get("duration", "")), "summary": summary, "objectives": summary,
                    "modules": [str(m) for m in r.get("modules", [])][:20], "url": url, "skills": str(r.get("skills", "")),
                    "category": "lms", "lms_course_id": cid})
    return out


# --------------------------------------------------------------------------- événements de fin de cours (webhook)
def verify_signature(secret: str, raw: bytes, header: str) -> bool:
    """`X-LMS-Signature: sha256=<hex(HMAC-SHA256(secret, corps brut))>` ; secret vide = webhook désactivé."""
    if not secret or not header:
        return False
    given = header.split("=", 1)[1] if header.lower().startswith("sha256=") else header
    return hmac.compare_digest(hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest(), given.strip().lower())


def _course_from_iri(iri: str) -> str | None:
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(iri).query).get("id")
    if q and q[0].isdigit():
        return q[0]
    m = re.search(r"/(\d+)/?$", urllib.parse.urlsplit(iri).path)
    return m.group(1) if m else None


def parse_event(p: dict) -> tuple[str, str] | None:
    """-> (e-mail en minuscules, id de cours) pour un événement « cours terminé », sinon None.
    Formats : JSON simple {"event": "course_completed", "user_email": ..., "course_id": ...} ou instruction xAPI (verbe completed/passed)."""
    if not isinstance(p, dict):
        return None
    if str(p.get("event", "")).lower() in GENERIC_EVENTS:
        email, cid = p.get("user_email") or p.get("email"), p.get("course_id") or p.get("courseid")
        return (str(email).strip().lower(), str(cid)) if email and cid else None
    verb = str((p.get("verb") or {}).get("id", "")).rstrip("/").rsplit("/", 1)[-1].lower()
    if verb in COMPLETED_VERBS:
        mbox = str((p.get("actor") or {}).get("mbox", ""))
        cid = _course_from_iri(str((p.get("object") or {}).get("id", "")))
        if mbox.lower().startswith("mailto:") and cid:
            return mbox[7:].strip().lower(), cid
    return None
