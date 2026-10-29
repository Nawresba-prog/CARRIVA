"""E-mail d'envoi de l'attestation à l'utilisateur (PDF en pièce jointe), dans sa langue.

Garde-fous : texte fixe (aucune saisie libre dans le corps), destinataire unique, limite d'envois par utilisateur et par attestation.
L'envoi se fait via le service Gmail (scope gmail.send uniquement), comme les candidatures, mais SANS Approval Gate : c'est le document de
l'utilisateur, envoyé à sa propre adresse à sa demande.
"""
from __future__ import annotations

import base64
import time
from collections import defaultdict, deque

TEXTS = {
    "fr": ("Votre attestation de formation CARRIVA", "Bonjour {name},\n\nFélicitations pour avoir terminé la formation « {training} ». Votre attestation est jointe à ce message (PDF).\n\nVous ou un employeur pouvez vérifier son authenticité ici : {verify_url}\n\nL'équipe CARRIVA"),
    "en": ("Your CARRIVA training certificate", "Hello {name},\n\nCongratulations on completing “{training}”. Your certificate is attached to this message (PDF).\n\nYou or an employer can check its authenticity here: {verify_url}\n\nThe CARRIVA team"),
    "de": ("Ihre CARRIVA Teilnahmebescheinigung", "Guten Tag {name},\n\nHerzlichen Glückwunsch zum Abschluss der Weiterbildung „{training}“. Ihre Bescheinigung finden Sie im Anhang (PDF).\n\nEchtheit prüfbar unter: {verify_url}\n\nIhr CARRIVA Team"),
    "es": ("Su certificado de formación CARRIVA", "Hola {name}:\n\nEnhorabuena por completar «{training}». Su certificado va adjunto en este mensaje (PDF).\n\nPuede comprobar su autenticidad aquí: {verify_url}\n\nEl equipo de CARRIVA"),
    "it": ("Il tuo attestato di formazione CARRIVA", "Ciao {name},\n\ncomplimenti per aver completato «{training}». Il tuo attestato è allegato a questo messaggio (PDF).\n\nPuoi verificarne l'autenticità qui: {verify_url}\n\nIl team CARRIVA"),
    "ar": ("شهادة إتمام التدريب من CARRIVA", "مرحبًا {name}،\n\nتهانينا على إتمام «{training}». شهادتك مرفقة بهذه الرسالة (PDF).\n\nيمكنك أو جهة التوظيف التحقق من صحتها هنا: {verify_url}\n\nفريق CARRIVA"),
}


def clean(s: str, limit: int = 160) -> str:
    """Une seule ligne, sans caractères de contrôle (pas d'injection d'en-têtes dans l'objet ou le corps)."""
    return " ".join("".join(ch if ch.isprintable() else " " for ch in str(s)).split())[:limit]


def build_message(to: str, lang: str, name: str, training: str, verify_url: str, pdf: bytes, cid: str) -> dict:
    subject, body = TEXTS.get(lang, TEXTS["en"])
    return {"to": to, "subject": subject, "body": body.format(name=clean(name, 120), training=clean(training), verify_url=verify_url),
            "attachment": {"filename": f"attestation_{cid}.pdf", "mime": "application/pdf", "data_b64": base64.b64encode(pdf).decode()}}


class Limiter:
    """Au plus `max_events` par clé sur `window` secondes (mémoire du processus ; production : Redis)."""
    def __init__(self, max_events: int, window: float, clock=time.monotonic):
        self.max, self.window, self.clock, self.hits = max_events, window, clock, defaultdict(deque)

    def allow(self, key: str) -> bool:
        now, q = self.clock(), self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.max:
            return False
        q.append(now)
        return True
