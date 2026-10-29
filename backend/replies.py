"""Détection des réponses des recruteurs (boîte de réception, lecture seule) : relie un message reçu à une candidature envoyée.

Règle volontairement stricte : seule l'adresse EXACTE à laquelle la candidature a été envoyée compte (jamais une adresse tirée du corps du message).
Un message de désinscription (STOP, unsubscribe…) ajoute l'adresse à la liste d'opposition : plus aucun envoi vers elle."""
from __future__ import annotations

import re

STOP = re.compile(r"\b(stop|unsubscribe|remove me|opt[- ]?out|désabonn\w*|desinscri\w*|désinscri\w*|ne plus (?:me )?contacter|ne me contactez plus|cancella\w*|baja|abmeld\w*|nicht mehr kontaktieren)\b|إلغاء الاشتراك|لا تراسلوني", re.I)
REAL = ("sent",)


def is_stop(text: str) -> bool:
    return bool(STOP.search(text or ""))


def match(approvals, messages: list[dict]) -> list[dict]:
    """[{approval_id, email, optout}] pour chaque message dont l'expéditeur est le destinataire d'une candidature réellement envoyée (jamais mails automatiques)."""
    by_to: dict[str, list[dict]] = {}
    for a in approvals:
        if a.get("status") in REAL and a.get("kind") != "followup" and a.get("draft", {}).get("to"):
            by_to.setdefault(a["draft"]["to"].lower(), []).append(a)
    out, seen = [], set()
    for m in messages:
        email = (m.get("from_email") or "").lower()
        if not email or m.get("auto") or m.get("category") in ("automated", "suspicious") or email not in by_to:
            continue
        stop = is_stop(f"{m.get('subject', '')}\n{m.get('body', '')}")
        for a in by_to[email]:
            if (a["id"], stop) not in seen:
                seen.add((a["id"], stop))
                out.append({"approval_id": a["id"], "email": email, "optout": stop})
    return out
