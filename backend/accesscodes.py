"""Connexion par code d'accès (production sans fournisseur d'identité).

ACCESS_CODES="Code-Secret-1:approver,Autre-Code-2:candidate"  (code:rôle, séparés par des virgules)
- un code = une personne (le « sub » du jeton est dérivé du code par hachage : jamais le code lui-même) ;
- 10 caractères minimum, rôles connus uniquement, doublons ignorés ; comparaison en temps constant, sans arrêt au premier succès ;
- à remplacer par OIDC (Google, Microsoft, Keycloak…) dès que vous avez des comptes utilisateurs réels.
"""
from __future__ import annotations

import hashlib
import hmac

MIN_LEN = 10


def parse(raw: str, roles) -> tuple[dict[str, str], list[str]]:
    """-> ({code: rôle}, avertissements)"""
    codes: dict[str, str] = {}
    warn: list[str] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        code, sep, role = part.rpartition(":")
        code, role = code.strip(), role.strip()
        if not sep or role not in roles:
            warn.append("entrée ignorée (format code:rôle attendu, rôle inconnu)")
        elif len(code) < MIN_LEN:
            warn.append(f"code ignoré (moins de {MIN_LEN} caractères)")
        elif code in codes:
            warn.append("code en double ignoré")
        else:
            codes[code] = role
    return codes, warn


def subject(code: str) -> str:
    return "u-" + hashlib.sha256(("carriva|" + code).encode()).hexdigest()[:16]


def check(codes: dict[str, str], supplied: str) -> tuple[str, str] | None:
    """-> (sub, rôle) ou None. Parcourt tous les codes pour ne pas révéler lequel a été trouvé par le temps de réponse."""
    found = None
    s = (supplied or "").encode()
    for code, role in codes.items():
        if hmac.compare_digest(code.encode(), s):
            found = (subject(code), role)
    return found
