"""Persistance JSON légère (écriture atomique) pour les approbations et les abonnements : survit à un redémarrage sans base de données.
Les datetime sont conservés ; `directory` vide ou None = pas de persistance (tests). Production : table SQL."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime


def _enc(o):
    if isinstance(o, datetime):
        return {"__dt__": o.isoformat()}
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    raise TypeError(f"non sérialisable : {type(o).__name__}")


def _dec(d):
    return datetime.fromisoformat(d["__dt__"]) if "__dt__" in d else d


def load(directory: str | None, name: str, default):
    if not directory:
        return default
    try:
        with open(os.path.join(directory, name + ".json"), encoding="utf-8") as f:
            return json.load(f, object_hook=_dec)
    except FileNotFoundError:
        return default
    except (OSError, ValueError):
        return default


def save(directory: str | None, name: str, obj) -> bool:
    if not directory:
        return False
    try:
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=name + ".", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, default=_enc)
        os.replace(tmp, os.path.join(directory, name + ".json"))
        return True
    except OSError:
        return False


DEFAULT_JWT, DEFAULT_INTERNAL = "dev-only-change-me", "dev-internal-secret"


def insecure_defaults(env: str, jwt_secret: str, internal_secret: str) -> list[str]:
    """Problèmes de configuration : secrets par défaut, trop courts, identiques ou route /auth/dev-token ouverte (ENV=dev)."""
    out = []
    if jwt_secret == DEFAULT_JWT or len(jwt_secret) < 16:
        out.append("JWT_SECRET par défaut ou trop court (16 caractères minimum)")
    if internal_secret == DEFAULT_INTERNAL or len(internal_secret) < 16:
        out.append("INTERNAL_SECRET par défaut ou trop court (16 caractères minimum)")
    if jwt_secret == internal_secret:
        out.append("JWT_SECRET et INTERNAL_SECRET identiques")
    if env == "dev":
        out.append("ENV=dev : la route /auth/dev-token délivre des jetons à n'importe qui")
    return out
