"""WF-3 n8n : relance J+N d'une candidature, TOUJOURS soumise à l'Approval Gate (rien n'est envoyé sans validation humaine).

Le texte est un gabarit déterministe : il ne contient que des faits déjà présents dans la candidature d'origine (poste, entreprise,
date d'envoi, nom). Pas de pièce jointe. Une seule relance par candidature (sauf si la précédente a expiré sans réponse de l'utilisateur).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

MIN_DAYS = int(os.getenv("FOLLOWUP_MIN_DAYS", "5"))  # n8n attend 7 jours ; marge de tolérance pour les horloges
STOP_STATUSES = {"reply", "rejected", "withdrawn"}  # réponse reçue, refus ou retrait : plus de relance
TRACKING_STATUSES = {"opened", "reply", "rejected", "withdrawn"}

TEMPLATES = {
    "fr": "Madame, Monsieur,\n\nJe me permets de revenir vers vous au sujet de ma candidature au poste de {title} chez {company}, envoyée le {date}. Je reste très intéressé(e) par ce poste et disponible pour un échange à votre convenance.\n\nJe vous remercie de l'attention portée à ma demande.\n\nCordialement,\n{name}",
    "en": "Dear Hiring Team,\n\nI am following up on my application for the {title} position at {company}, sent on {date}. I remain very interested in the role and available to talk whenever suits you.\n\nThank you for your time and consideration.\n\nKind regards,\n{name}",
    "de": "Sehr geehrte Damen und Herren,\n\nich möchte mich nach dem Stand meiner Bewerbung auf die Stelle {title} bei {company} vom {date} erkundigen. Ich interessiere mich weiterhin sehr für die Position und stehe gern für ein Gespräch zur Verfügung.\n\nVielen Dank für Ihre Zeit.\n\nMit freundlichen Grüßen\n{name}",
    "it": "Gentili Signori,\n\nvorrei un aggiornamento sulla mia candidatura per la posizione di {title} presso {company}, inviata il {date}. Resto molto interessato/a al ruolo e disponibile per un colloquio quando preferite.\n\nVi ringrazio per l'attenzione.\n\nCordiali saluti,\n{name}",
    "es": "Estimado equipo de selección:\n\nMe pongo en contacto de nuevo en relación con mi candidatura al puesto de {title} en {company}, enviada el {date}. Sigo muy interesado/a en el puesto y quedo a su disposición para conversar cuando les convenga.\n\nGracias por su tiempo.\n\nAtentamente,\n{name}",
    "ar": "السادة المحترمون،\n\nأعود إليكم بخصوص طلبي لوظيفة {title} لدى {company} الذي أرسلته بتاريخ {date}. ما زلت مهتمًا جدًا بهذه الوظيفة ومستعد لإجراء مقابلة في الوقت المناسب لكم.\n\nشاكرًا لكم اهتمامكم.\n\nمع خالص التقدير،\n{name}",
}


def _date(dt: datetime, lang: str) -> str:
    return dt.strftime("%Y-%m-%d") if lang == "en" else dt.strftime("%d/%m/%Y")


def eligibility(a: dict, existing: dict | None, now: datetime, min_days: int | None = None) -> tuple[bool, str, datetime | None]:
    """-> (ok, raison, date d'éligibilité). Raisons : not_sent, no_email, reply_received, already_proposed, too_early, ok."""
    if a.get("status") != "sent" or a.get("kind") == "followup":
        return False, "not_sent", None
    if a["draft"].get("channel") != "email" or not a["draft"].get("to"):
        return False, "no_email", None
    if a.get("tracking") in STOP_STATUSES:
        return False, "reply_received", None
    if existing and existing.get("status") != "expired":
        return False, "already_proposed", None
    sent_at = a.get("sent_at")
    if sent_at:
        due = sent_at + timedelta(days=MIN_DAYS if min_days is None else min_days)
        if now < due:
            return False, "too_early", due
    return True, "ok", None


def build_draft(parent_aid: str, parent_draft: dict, job: dict, name: str, sent_at: datetime | None) -> dict:
    lang = parent_draft.get("lang") if parent_draft.get("lang") in TEMPLATES else "en"
    when = _date(sent_at or datetime.now(timezone.utc), lang)
    subj = parent_draft["subject"]
    return {"to": parent_draft["to"], "subject": subj if subj.lower().startswith(("re:", "r:", "aw:")) else "Re: " + subj,
            "body": TEMPLATES[lang].format(title=job.get("title", ""), company=job.get("company", ""), date=when, name=name),
            "lang": lang, "channel": "email", "kind": "followup", "parent": parent_aid}
