"""Génération PDF : CV Europass (simplifié) et attestation de formation signée (HMAC).

Multilingue (fr, en, de, it, es, ar) avec prise en charge de l'arabe :
- mise en forme des lettres (arabic-reshaper) + ordre visuel RTL (python-bidi) ;
- police Noto Sans Arabic, enregistrée depuis backend/fonts/ (voir fonts/fetch_fonts.py) ;
- retour à la ligne calculé en ordre logique AVANT l'inversion visuelle, sinon les paragraphes
  arabes de plusieurs lignes s'afficheraient dans le mauvais ordre ;
- alignement à droite pour les textes arabes et pour tout le document en langue arabe.

Si la police est absente, l'arabe ne s'affichera pas correctement (carrés) : un avertissement est journalisé.
"""
from __future__ import annotations

import hashlib
import hmac
import io
import logging
import os
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import arabic_reshaper
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

try:  # python-bidi : l'emplacement de get_display varie selon les versions
    from bidi.algorithm import get_display
except ImportError:  # pragma: no cover
    from bidi import get_display

log = logging.getLogger("career.pdf")

EMERALD = colors.HexColor("#1F5FD6")
DEEP = colors.HexColor("#0F2A4F")
GRAY = colors.HexColor("#5b6770")
EU_BLUE = colors.HexColor("#0E4194")  # bleu du modèle Europass
EU_LINE = colors.HexColor("#c9d3e3")
CERT_SECRET = os.getenv("CERT_SECRET", "dev-cert-secret")

FONT_DIR = Path(os.getenv("CAREER_FONT_DIR", Path(__file__).resolve().parent / "fonts"))
AR_REG, AR_BOLD = "NotoArabic", "NotoArabic-Bold"
_ar_ok = False

LABELS = {
    "fr": dict(profile="Profil", work="Expérience professionnelle", edu="Éducation et formation", skills="Compétences", langs="Langues", present="en cours",
               cert_title="ATTESTATION DE FORMATION", awarded="Décernée à", completed="pour avoir terminé la formation", issued="Délivrée le", number="N°", signature="Signature", verify="Vérification"),
    "en": dict(profile="Profile", work="Work experience", edu="Education and training", skills="Skills", langs="Languages", present="present",
               cert_title="CERTIFICATE OF COMPLETION", awarded="Awarded to", completed="for completing the training", issued="Issued on", number="No.", signature="Signature", verify="Verify"),
    "de": dict(profile="Profil", work="Berufserfahrung", edu="Ausbildung", skills="Kenntnisse", langs="Sprachen", present="heute",
               cert_title="TEILNAHMEBESCHEINIGUNG", awarded="Verliehen an", completed="für den erfolgreichen Abschluss der Weiterbildung", issued="Ausgestellt am", number="Nr.", signature="Signatur", verify="Prüfung"),
    "it": dict(profile="Profilo", work="Esperienza professionale", edu="Istruzione e formazione", skills="Competenze", langs="Lingue", present="in corso",
               cert_title="ATTESTATO DI FORMAZIONE", awarded="Rilasciato a", completed="per aver completato il corso", issued="Rilasciato il", number="N.", signature="Firma", verify="Verifica"),
    "es": dict(profile="Perfil", work="Experiencia profesional", edu="Educación y formación", skills="Competencias", langs="Idiomas", present="actualidad",
               cert_title="CERTIFICADO DE FORMACIÓN", awarded="Otorgado a", completed="por completar la formación", issued="Expedido el", number="N.º", signature="Firma", verify="Verificación"),
    "ar": dict(profile="الملف الشخصي", work="الخبرة المهنية", edu="التعليم والتدريب", skills="المهارات", langs="اللغات", present="حتى الآن",
               cert_title="شهادة إتمام تدريب", awarded="تُمنح إلى", completed="عن إتمام التدريب", issued="صدرت بتاريخ", number="رقم", signature="التوقيع", verify="للتحقق"),
}


_EXTRA = {
    "fr": dict(cv="Curriculum vitae", personal="Informations personnelles", work_h="Expérience professionnelle", edu_h="Éducation et formation",
               pskills="Compétences personnelles", mother="Langue(s) maternelle(s)", other_langs="Autre(s) langue(s)", understanding="Comprendre", speaking="Parler", writing="Écrire",
               listening="Écouter", reading="Lire", interaction="Prendre part à une conversation", production="S'exprimer oralement en continu", digital="Compétences numériques",
               licence="Permis de conduire", additional="Informations complémentaires", nationality="Nationalité", dob="Date de naissance", website="Site web", address="Adresse",
               phone_l="Téléphone", email_l="E-mail", eqf="Niveau CEC", levels="Niveaux : A1/A2 utilisateur élémentaire - B1/B2 utilisateur indépendant - C1/C2 utilisateur expérimenté (CECRL)"),
    "en": dict(cv="Curriculum Vitae", personal="Personal information", work_h="Work experience", edu_h="Education and training",
               pskills="Personal skills", mother="Mother tongue(s)", other_langs="Other language(s)", understanding="Understanding", speaking="Speaking", writing="Writing",
               listening="Listening", reading="Reading", interaction="Spoken interaction", production="Spoken production", digital="Digital skills",
               licence="Driving licence", additional="Additional information", nationality="Nationality", dob="Date of birth", website="Website", address="Address",
               phone_l="Phone", email_l="E-mail", eqf="EQF level", levels="Levels: A1/A2 Basic user - B1/B2 Independent user - C1/C2 Proficient user (Common European Framework of Reference for Languages)"),
    "de": dict(cv="Lebenslauf", personal="Persönliche Informationen", work_h="Berufserfahrung", edu_h="Schul- und Berufsbildung",
               pskills="Persönliche Fähigkeiten", mother="Muttersprache(n)", other_langs="Weitere Sprache(n)", understanding="Verstehen", speaking="Sprechen", writing="Schreiben",
               listening="Hören", reading="Lesen", interaction="An Gesprächen teilnehmen", production="Zusammenhängendes Sprechen", digital="Digitale Kompetenzen",
               licence="Führerschein", additional="Zusätzliche Angaben", nationality="Staatsangehörigkeit", dob="Geburtsdatum", website="Website", address="Adresse",
               phone_l="Telefon", email_l="E-Mail", eqf="EQR-Niveau", levels="Niveau: A1/A2 Elementare Sprachverwendung - B1/B2 Selbstständige Sprachverwendung - C1/C2 Kompetente Sprachverwendung (GER)"),
    "it": dict(cv="Curriculum vitae", personal="Informazioni personali", work_h="Esperienza professionale", edu_h="Istruzione e formazione",
               pskills="Competenze personali", mother="Lingua madre", other_langs="Altre lingue", understanding="Comprensione", speaking="Parlato", writing="Produzione scritta",
               listening="Ascolto", reading="Lettura", interaction="Interazione", production="Produzione orale", digital="Competenze digitali",
               licence="Patente di guida", additional="Ulteriori informazioni", nationality="Cittadinanza", dob="Data di nascita", website="Sito web", address="Indirizzo",
               phone_l="Telefono", email_l="E-mail", eqf="Livello QEQ", levels="Livelli: A1/A2 Utente base - B1/B2 Utente autonomo - C1/C2 Utente avanzato (QCER)"),
    "es": dict(cv="Curriculum vitae", personal="Información personal", work_h="Experiencia profesional", edu_h="Educación y formación",
               pskills="Competencias personales", mother="Lengua(s) materna(s)", other_langs="Otro(s) idioma(s)", understanding="Comprensión", speaking="Expresión oral", writing="Expresión escrita",
               listening="Comprensión auditiva", reading="Comprensión de lectura", interaction="Interacción oral", production="Expresión oral", digital="Competencias digitales",
               licence="Permiso de conducir", additional="Información adicional", nationality="Nacionalidad", dob="Fecha de nacimiento", website="Sitio web", address="Dirección",
               phone_l="Teléfono", email_l="Correo electrónico", eqf="Nivel MEC", levels="Niveles: A1/A2 Usuario básico - B1/B2 Usuario independiente - C1/C2 Usuario competente (MCER)"),
    "ar": dict(cv="السيرة الذاتية", personal="المعلومات الشخصية", work_h="الخبرة المهنية", edu_h="التعليم والتدريب",
               pskills="المهارات الشخصية", mother="اللغة الأم", other_langs="اللغات الأخرى", understanding="الفهم", speaking="التحدث", writing="الكتابة",
               listening="الاستماع", reading="القراءة", interaction="التفاعل الشفهي", production="الإنتاج الشفهي", digital="المهارات الرقمية",
               licence="رخصة القيادة", additional="معلومات إضافية", nationality="الجنسية", dob="تاريخ الميلاد", website="الموقع الإلكتروني", address="العنوان",
               phone_l="الهاتف", email_l="البريد الإلكتروني", eqf="مستوى الإطار الأوروبي للمؤهلات", levels="المستويات: A1/A2 مستخدم مبتدئ - B1/B2 مستخدم مستقل - C1/C2 مستخدم متمكن (الإطار الأوروبي المرجعي للغات)"),
}
for _k, _v in _EXTRA.items():
    LABELS[_k].update(_v)


def labels(lang: str) -> dict:
    return LABELS.get(lang, LABELS["en"])


# --------------------------------------------------------------------------- polices
def register_fonts() -> bool:
    """Enregistre Noto Sans Arabic. Chemins surchargeables : ARABIC_FONT_REGULAR / ARABIC_FONT_BOLD / CAREER_FONT_DIR."""
    global _ar_ok
    reg = Path(os.getenv("ARABIC_FONT_REGULAR", FONT_DIR / "NotoSansArabic-Regular.ttf"))
    bold = Path(os.getenv("ARABIC_FONT_BOLD", FONT_DIR / "NotoSansArabic-Bold.ttf"))
    if not reg.exists():
        log.warning("Police arabe introuvable (%s). Lancez `python backend/fonts/fetch_fonts.py`. L'arabe ne s'affichera pas.", reg)
        _ar_ok = False
        return False
    pdfmetrics.registerFont(TTFont(AR_REG, str(reg)))
    pdfmetrics.registerFont(TTFont(AR_BOLD, str(bold if bold.exists() else reg)))
    # Le reshaper produit des formes de présentation (U+FB50–FEFF) : la police doit les contenir.
    cmap = pdfmetrics.getFont(AR_REG).face.charToGlyph
    if 0xFEE3 not in cmap:
        log.warning("La police arabe n'a pas les formes de présentation (U+FExx) : utilisez Noto Naskh Arabic ou Amiri.")
    _ar_ok = True
    return True


register_fonts()

# --------------------------------------------------------------------------- texte arabe / RTL
_ARAB = "؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿"
_AR_CH = re.compile(f"[{_ARAB}]")
_AR_RUN = re.compile(f"[{_ARAB}]+(?:[\\s‎‏]+[{_ARAB}]+)*")


def has_arabic(text: str) -> bool:
    return bool(_AR_CH.search(text))


def _first_strong_is_arabic(text: str) -> bool:
    for ch in text:
        if ch.isalpha():
            return bool(_AR_CH.match(ch))
    return False


def _mark(displayed: str, bold: bool) -> str:
    """Échappe le XML et entoure les segments arabes d'une balise <font> (le reste reste en Helvetica)."""
    font = AR_BOLD if bold else AR_REG
    out, pos = [], 0
    for m in _AR_RUN.finditer(displayed):
        out.append(escape(displayed[pos:m.start()]))
        seg = escape(m.group())
        out.append(f'<font name="{font}">{seg}</font>' if _ar_ok else seg)
        pos = m.end()
    out.append(escape(displayed[pos:]))
    return "".join(out)


def _word_width(word: str, size: float, bold: bool) -> float:
    if _ar_ok and has_arabic(word):
        return pdfmetrics.stringWidth(word, AR_BOLD if bold else AR_REG, size)
    return pdfmetrics.stringWidth(word, "Helvetica-Bold" if bold else "Helvetica", size)


def _wrap_rtl(text: str, size: float, bold: bool, width: float) -> list[str]:
    """Coupe en lignes en ORDRE LOGIQUE, puis applique l'ordre visuel (bidi) ligne par ligne."""
    words = arabic_reshaper.reshape(text).split(" ")
    space = pdfmetrics.stringWidth(" ", "Helvetica", size)
    lines: list[list[str]] = [[]]
    cur_w = 0.0
    for w in words:
        ww = _word_width(w, size, bold)
        if lines[-1] and cur_w + space + ww > width:
            lines.append([w])
            cur_w = ww
        else:
            cur_w += (space if lines[-1] else 0) + ww
            lines[-1].append(w)
    return [get_display(" ".join(ln)) for ln in lines]


def shape(text: str, bold: bool = False) -> str:
    """Balisage ReportLab d'une ligne (sans retour à la ligne automatique). Utile pour les tests et les libellés courts."""
    text = str(text or "")
    if not has_arabic(text):
        return escape(text)
    return _mark(get_display(arabic_reshaper.reshape(text)), bold)


def para(text: str, style: ParagraphStyle, width: float, lang: str = "fr", align: int | None = None) -> Paragraph:
    text = str(text or "")
    if align is None:
        align = TA_RIGHT if (lang == "ar" or _first_strong_is_arabic(text)) else style.alignment
    st = ParagraphStyle(style.name + "_x", parent=style, alignment=align)
    if has_arabic(text):
        bold = "Bold" in style.fontName
        lines = [ln for raw in text.split("\n") for ln in _wrap_rtl(raw, style.fontSize, bold, width * 0.96)]
        markup = "<br/>".join(_mark(ln, bold) for ln in lines)
    else:
        markup = "<br/>".join(escape(ln) for ln in text.split("\n"))
    return Paragraph(markup, st)


# --------------------------------------------------------------------------- CV (modèle Europass)
def fmt_date(v: str) -> str:
    """2021-03 -> 03/2021 ; 1995-04-12 -> 12/04/1995 ; autre texte inchangé."""
    v = (v or "").strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})(?:-(\d{2}))?", v)
    if not m:
        return v
    y, mo, d = m.groups()
    return f"{d}/{mo}/{y}" if d else f"{mo}/{y}"


def period(start: str, end: str, present: str) -> str:
    s, e = fmt_date(start), fmt_date(end)
    if s:
        return f"{s} – {e or present}"
    return e


def _photo_flowable(data_uri):
    """Photo JPEG facultative (data-URI) -> Image ReportLab (portrait, proportions conservées) ; None si absente ou invalide."""
    import base64
    import re

    m = re.fullmatch(r"data:image/jpe?g;base64,([A-Za-z0-9+/=\s]+)", data_uri or "")
    if not m:
        return None
    try:
        raw = base64.b64decode(re.sub(r"\s", "", m.group(1)), validate=True)
        if raw[:2] != b"\xff\xd8" or len(raw) > 900_000:
            return None
        from reportlab.lib.utils import ImageReader
        from reportlab.platypus import Image

        iw, ih = ImageReader(io.BytesIO(raw)).getSize()
        box_w, box_h = 2.6 * cm, 3.3 * cm
        k = min(box_w / iw, box_h / ih)
        return Image(io.BytesIO(raw), width=iw * k, height=ih * k)
    except Exception:  # noqa: BLE001 - une photo illisible ne doit jamais empêcher la création du CV
        return None


def cv_pdf(eu: dict, lang: str = "en") -> bytes:
    """CV au format Europass classique : en-tête, colonne gauche (dates / libellés bleus), tableau CECR des langues."""
    lb = labels(lang)
    rtl = lang == "ar"
    pers = eu.get("personal", {})
    name = pers.get("name", "")
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.5 * cm, bottomMargin=1.6 * cm,
                            title=f"{lb['cv']} - {name}", author=name)
    W = doc.width
    LW = 4.6 * cm
    CW = W - LW
    ss = getSampleStyleSheet()
    base = ParagraphStyle("eb", parent=ss["BodyText"], fontSize=9.5, leading=12.5, textColor=colors.black)
    bold = ParagraphStyle("ebb", parent=base, fontName="Helvetica-Bold")
    lab = ParagraphStyle("elab", parent=base, textColor=EU_BLUE, fontName="Helvetica-Bold", fontSize=9)
    gray = ParagraphStyle("eg", parent=base, textColor=GRAY)
    small = ParagraphStyle("es", parent=base, textColor=GRAY, fontSize=7.5, leading=10)
    sec = ParagraphStyle("esec", parent=base, textColor=EU_BLUE, fontName="Helvetica-Bold", fontSize=10.5, spaceBefore=11, spaceAfter=1)
    kicker = ParagraphStyle("ek", parent=base, textColor=EU_BLUE, fontName="Helvetica-Bold", fontSize=11)
    title = ParagraphStyle("et", parent=base, fontName="Helvetica-Bold", fontSize=22, leading=27)

    def P(text, st, width=W, align=None):
        return para(text, st, width, lang, align)

    def entry(left: str, items: list) -> Table:
        """Ligne à deux colonnes (libellé/dates | contenu). Inversée pour l'arabe."""
        l = P(left, lab, LW - 8)
        r = [P(x, base, CW - 8) if isinstance(x, str) else x for x in items if x not in ("", None)]
        row, widths = ([r, l], [CW, LW]) if rtl else ([l, r], [LW, CW])
        t = Table([row], colWidths=widths)
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        return t

    def section(label: str) -> list:
        return [P(label.upper(), sec), HRFlowable(width="100%", color=EU_LINE, thickness=0.8, spaceBefore=1, spaceAfter=6)]

    head = P(name, title)
    photo = _photo_flowable(eu.get("_photo"))
    if photo is not None:  # photo facultative : à droite du nom (à gauche en arabe)
        pw = 3.0 * cm
        cells, widths = ([photo, head], [pw, W - pw]) if rtl else ([head, photo], [W - pw, pw])
        head = Table([cells], colWidths=widths)
        head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                  ("ALIGN", (1 if not rtl else 0, 0), (1 if not rtl else 0, 0), "RIGHT" if not rtl else "LEFT")]))
    out: list = [P(lb["cv"], kicker), Spacer(1, 4), head, HRFlowable(width="100%", color=EU_BLUE, thickness=2.5, spaceBefore=6, spaceAfter=2)]

    # --- informations personnelles
    out += section(lb["personal"])
    for key, val in ((lb["address"], pers.get("address", "")), (lb["phone_l"], pers.get("phone", "")), (lb["email_l"], pers.get("email", "")),
                     (lb["website"], pers.get("website", "")), (lb["nationality"], pers.get("nationality", "")),
                     (lb["dob"], fmt_date(pers.get("birth_date", "")))):
        if val and str(val).strip(", "):
            out.append(entry(key, [str(val).strip(", ")]))
    if eu.get("summary"):
        out.append(entry(lb["profile"], [eu["summary"]]))

    # --- expérience professionnelle
    if eu.get("work_experience"):
        out += section(lb["work_h"])
        for e in eu["work_experience"]:
            place = ", ".join(x for x in (e.get("company"), e.get("city"), e.get("country")) if x)
            out.append(entry(period(e.get("start", ""), e.get("end", ""), lb["present"]),
                             [P(e.get("title", ""), bold, CW - 8), P(place, gray, CW - 8) if place else "", e.get("description", "")]))

    # --- éducation et formation
    if eu.get("education_training"):
        out += section(lb["edu_h"])
        for e in eu["education_training"]:
            place = ", ".join(x for x in (e.get("school"), e.get("city"), e.get("country")) if x)
            lvl = f"{lb['eqf']} {e['level']}" if e.get("level") else ""
            when = period(e.get("start", ""), e.get("end", ""), lb["present"]) or e.get("year", "")
            out.append(entry(when, [P(e.get("degree", ""), bold, CW - 8), P(place, gray, CW - 8) if place else "", lvl]))

    # --- compétences personnelles
    langs = eu.get("language_skills", [])
    mother = eu.get("mother_tongue", [])
    if mother or langs or eu.get("digital_skills") or eu.get("driving_licence") or eu.get("additional_info"):
        out += section(lb["pskills"])
        if mother:
            out.append(entry(lb["mother"], [", ".join(mother)]))
        if langs:
            gw = CW - 10
            first = 2.5 * cm
            cw = (gw - first) / 5
            hs = ParagraphStyle("gh", parent=base, fontSize=7, leading=9, textColor=EU_BLUE, fontName="Helvetica-Bold")
            ls = ParagraphStyle("gl", parent=base, fontSize=8.5, leading=11)
            cell = lambda txt, st, w: para(txt, st, w, lang, align=TA_CENTER)
            rows = [
                ["", cell(lb["understanding"].upper(), hs, cw * 2), "", cell(lb["speaking"].upper(), hs, cw * 2), "", cell(lb["writing"].upper(), hs, cw)],
                ["", cell(lb["listening"], hs, cw), cell(lb["reading"], hs, cw), cell(lb["interaction"], hs, cw), cell(lb["production"], hs, cw), ""],
            ]
            for l in langs:
                rows.append([P(l.get("name", ""), ParagraphStyle("gn", parent=ls, fontName="Helvetica-Bold"), first - 4)] +
                            [cell(str(l.get(k, "")), ls, cw) for k in ("listening", "reading", "interaction", "production", "writing")])
            spans = [(1, 0, 2, 0), (3, 0, 4, 0), (5, 0, 5, 1)]
            widths = [first] + [cw] * 5
            if rtl:  # miroir : la colonne « langue » passe à droite
                rows = [r[::-1] for r in rows]
                widths = widths[::-1]
                spans = [(5 - b, a2, 5 - a, b2) for a, a2, b, b2 in spans]
            t = Table(rows, colWidths=widths)
            style = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                     ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                     ("LINEBELOW", (0, 1), (-1, 1), 0.8, EU_BLUE), ("GRID", (0, 2), (-1, -1), 0.4, EU_LINE)]
            style += [("SPAN", (a, a2), (b, b2)) for a, a2, b, b2 in spans]
            t.setStyle(TableStyle(style))
            out.append(entry(lb["other_langs"], [t, Spacer(1, 3), P(lb["levels"], small, CW - 8)]))
        if eu.get("digital_skills"):
            out.append(entry(lb["digital"], [", ".join(eu["digital_skills"])]))
        if eu.get("driving_licence"):
            out.append(entry(lb["licence"], [eu["driving_licence"]]))
        if eu.get("additional_info"):
            out.append(entry(lb["additional"], [eu["additional_info"]]))

    def footer(c, d):
        c.saveState()
        c.setFont("Helvetica", 8)
        c.setFillColor(GRAY)
        c.drawCentredString(A4[0] / 2, 1.0 * cm, f"- {d.page} -")
        c.restoreState()

    doc.build(out, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


# --------------------------------------------------------------------------- attestation
def sign(cert_id: str, name: str, training: str, issued: str) -> str:
    msg = f"{cert_id}|{name}|{training}|{issued}".encode()
    return hmac.new(CERT_SECRET.encode(), msg, hashlib.sha256).hexdigest()


def _ring_text(c: canvas.Canvas, cx: float, cy: float, radius: float, text: str, font: str, size: float) -> None:
    """Écrit `text` tout autour d'un cercle (sens horaire, départ en haut), réparti sur la circonférence entière."""
    import math
    total = pdfmetrics.stringWidth(text, font, size)
    scale = 2 * math.pi * radius / total  # agrandit/rétrécit les caractères pour que le texte referme exactement le cercle
    size2 = max(5.5, min(size * scale, 10))
    widths = [pdfmetrics.stringWidth(ch, font, size2) for ch in text]
    step = 2 * math.pi / sum(widths)
    pos = 0.0
    for ch, w in zip(text, widths):
        ang = math.pi / 2 - (pos + w / 2) * step
        c.saveState()
        c.translate(cx + radius * math.cos(ang), cy + radius * math.sin(ang))
        c.rotate(math.degrees(ang) - 90)
        c.setFont(font, size2)
        c.drawCentredString(0, 0, ch)
        c.restoreState()
        pos += w


def _arc_text(c: canvas.Canvas, cx: float, cy: float, radius: float, text: str, font: str, size: float, bottom: bool = False) -> None:
    """Texte courbé centré en haut (lecture horaire) ou en bas (lecture de gauche à droite, lettres à l'endroit).
    `radius` = ligne de base : lettres vers l'extérieur en haut, vers le centre en bas."""
    import math
    widths = [pdfmetrics.stringWidth(ch, font, size) for ch in text]
    half = sum(widths) / radius / 2  # demi-ouverture angulaire du texte
    pos = 0.0
    for ch, w in zip(text, widths):
        mid = (pos + w / 2) / radius
        ang = (-math.pi / 2 - half + mid) if bottom else (math.pi / 2 + half - mid)
        c.saveState()
        c.translate(cx + radius * math.cos(ang), cy + radius * math.sin(ang))
        c.rotate(math.degrees(ang) + (90 if bottom else -90))
        c.setFont(font, size)
        c.drawCentredString(0, 0, ch)
        c.restoreState()
        pos += w


def _seal(c: canvas.Canvas, cx: float, cy: float, r: float, code: str, issued: str, verified: bool) -> None:
    """Cachet circulaire de CARRIVA : double anneau, « CARRIVA » en haut, mention en bas, coche, date et code court de la signature.
    Cachet bleu « COMPLETION VERIFIED » seulement si la fin de formation a été vérifiée ; sinon cachet gris « NOT VERIFIED · DEMO »."""
    ink = DEEP if verified else GRAY
    band = 0.62 * cm
    c.saveState()
    c.translate(cx, cy)
    c.rotate(-10)
    c.setStrokeAlpha(0.92)
    c.setFillAlpha(0.92)
    c.setStrokeColor(ink)
    c.setFillColor(ink)
    c.setLineWidth(2.8)
    c.circle(0, 0, r, stroke=1, fill=0)
    c.setLineWidth(1)
    c.circle(0, 0, r - band, stroke=1, fill=0)
    c.setLineWidth(0.6)
    c.circle(0, 0, r - band - 0.1 * cm, stroke=1, fill=0)
    _arc_text(c, 0, 0, r - 0.44 * cm, "CARRIVA", "Helvetica-Bold", 11)
    _arc_text(c, 0, 0, r - 0.12 * cm, "COMPLETION VERIFIED" if verified else "NOT VERIFIED \u2022 DEMO", "Helvetica-Bold", 8, bottom=True)
    for sx in (-1, 1):  # petits losanges de séparation à gauche et à droite
        c.saveState()
        c.translate(sx * (r - band / 2), 0)
        c.rotate(45)
        c.rect(-0.07 * cm, -0.07 * cm, 0.14 * cm, 0.14 * cm, stroke=0, fill=1)
        c.restoreState()
    c.setStrokeColor(EMERALD if verified else GRAY)
    c.setLineWidth(3.2)
    c.setLineCap(1)
    c.setLineJoin(1)
    k = r / (2.3 * cm)
    p = c.beginPath()
    p.moveTo(-0.55 * cm * k, 0.55 * cm * k); p.lineTo(-0.15 * cm * k, 0.15 * cm * k); p.lineTo(0.62 * cm * k, 0.95 * cm * k)
    c.drawPath(p, stroke=1, fill=0)
    c.setFillColor(ink)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawCentredString(0, -0.3 * cm * k, issued)
    c.setFont("Helvetica", 6.5)
    c.drawCentredString(0, -0.72 * cm * k, code.upper())
    c.restoreState()


def _qr(c: canvas.Canvas, url: str, x: float, y: float, size: float) -> None:
    w = QrCodeWidget(url)
    b = w.getBounds()
    d = Drawing(size, size, transform=[size / (b[2] - b[0]), 0, 0, size / (b[3] - b[1]), 0, 0])
    d.add(w)
    renderPDF.draw(d, c, x, y)


def certificate_pdf(cert_id: str, name: str, training: str | dict, issued: str, verify_url: str, lang: str = "fr", verified: bool = False) -> bytes:
    """Attestation A4 paysage. `training` : titre (str) ou fiche du catalogue (dict : title, provider, duration, level, category, skills) ;
    le thème visuel (couleurs, motif, icône) dépend de la formation : voir cert_design."""
    from . import cert_design  # import à la demande : cert_design utilise les aides de ce module
    info = {"title": training} if isinstance(training, str) else dict(training)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A4))
    cert_design.certificate_page(c, cert_id=cert_id, name=name, training=info, issued=issued, verify_url=verify_url, lang=lang, verified=verified, pdf=sys.modules[__name__])
    c.showPage()
    c.save()
    return buf.getvalue()
