"""Design des attestations : un thème par domaine de formation (couleurs, motif géométrique, icône, libellé), rendu moderne en A4 paysage.

Le thème est choisi par `theme_for(formation)` (catégorie du catalogue, puis compétences canoniques). Le motif varie légèrement d'une
formation à l'autre (graine = titre). Langue arabe : mise en page en miroir (bandeau à droite, textes alignés à droite).
Dépend de pdf_gen (cachet, QR, textes arabes) ; importé à la demande par pdf_gen.certificate_pdf (pas d'import circulaire au chargement).
"""
from __future__ import annotations

import hashlib
import math
import random

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics

H = colors.HexColor

# id -> (couleur principale sombre, accent, teinte claire du fond, motif, icône)
THEMES = {
    "languages":  (H("#0B4F5C"), H("#F4A62A"), H("#EAF6F7"), "waves", "speech"),
    "web":        (H("#0B1220"), H("#22D3EE"), H("#EAF3F8"), "dots", "code"),
    "project":    (H("#1E293B"), H("#F97316"), H("#F1F4F8"), "gantt", "gantt"),
    "marketing":  (H("#6B1456"), H("#FBBF24"), H("#FBEFF7"), "arcs", "target"),
    "data":       (H("#0E3B35"), H("#34D399"), H("#E9F7F2"), "bars", "chart"),
    "cloud":      (H("#17306B"), H("#60A5FA"), H("#EAF1FD"), "hex", "cloud"),
    "security":   (H("#2E1065"), H("#A78BFA"), H("#F1EDFB"), "stripes", "shield"),
    "business":   (H("#5A3410"), H("#E6A817"), H("#FBF4E6"), "coins", "growth"),
    "design":     (H("#831843"), H("#FB7185"), H("#FDEFF2"), "shapes", "shapes"),
    "general":    (H("#0F2A4F"), H("#1F5FD6"), H("#EDF2FB"), "stripes", "cap"),
}
PRIORITY = list(THEMES)

CATEGORY_THEME = {"languages": "languages", "web": "web", "project": "project", "marketing": "marketing"}
SKILL_THEME = {
    **dict.fromkeys(["javascript", "typescript", "react", "angular", "vue", "nodejs", "html_css", "java", "csharp", "php", "fastapi", "rest_api", "git", "testing"], "web"),
    **dict.fromkeys(["python", "sql", "nosql", "data_analysis", "machine_learning", "deep_learning", "nlp", "statistics", "power_bi", "tableau", "etl", "big_data", "excel"], "data"),
    **dict.fromkeys(["cloud", "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ci_cd", "linux", "microservices"], "cloud"),
    **dict.fromkeys(["cybersecurity", "networking"], "security"),
    **dict.fromkeys(["digital_marketing", "seo", "content_writing"], "marketing"),
    **dict.fromkeys(["project_management", "agile", "communication", "teaching", "hr"], "project"),
    **dict.fromkeys(["finance", "accounting", "audit", "sales", "customer_service", "logistics"], "business"),
    **dict.fromkeys(["graphic_design", "ux_design"], "design"),
}

NAMES = {  # libellé du domaine, imprimé en bas du bandeau
    "fr": ["LANGUES", "DÉVELOPPEMENT WEB", "GESTION DE PROJET", "MARKETING", "DATA & IA", "CLOUD & DEVOPS", "CYBERSÉCURITÉ & RÉSEAUX", "GESTION & FINANCE", "DESIGN", "FORMATION"],
    "en": ["LANGUAGES", "WEB DEVELOPMENT", "PROJECT MANAGEMENT", "MARKETING", "DATA & AI", "CLOUD & DEVOPS", "SECURITY & NETWORKS", "BUSINESS & FINANCE", "DESIGN", "TRAINING"],
    "de": ["SPRACHEN", "WEBENTWICKLUNG", "PROJEKTMANAGEMENT", "MARKETING", "DATEN & KI", "CLOUD & DEVOPS", "SICHERHEIT & NETZWERKE", "BUSINESS & FINANZEN", "DESIGN", "WEITERBILDUNG"],
    "es": ["IDIOMAS", "DESARROLLO WEB", "GESTIÓN DE PROYECTOS", "MARKETING", "DATOS E IA", "NUBE Y DEVOPS", "SEGURIDAD Y REDES", "NEGOCIOS Y FINANZAS", "DISEÑO", "FORMACIÓN"],
    "it": ["LINGUE", "SVILUPPO WEB", "GESTIONE DI PROGETTI", "MARKETING", "DATI E IA", "CLOUD E DEVOPS", "SICUREZZA E RETI", "BUSINESS E FINANZA", "DESIGN", "FORMAZIONE"],
    "ar": ["اللغات", "تطوير الويب", "إدارة المشاريع", "التسويق", "البيانات والذكاء الاصطناعي", "الحوسبة السحابية", "الأمن والشبكات", "الأعمال والمالية", "التصميم", "التدريب"],
}


def theme_for(training: dict | None) -> str:
    t = training or {}
    if t.get("category") in CATEGORY_THEME:
        return CATEGORY_THEME[t["category"]]
    votes: dict[str, int] = {}
    for s in str(t.get("skills", "")).split():
        th = SKILL_THEME.get(s)
        if th:
            votes[th] = votes.get(th, 0) + 1
    return max(votes, key=lambda k: (votes[k], -PRIORITY.index(k))) if votes else "general"


# --------------------------------------------------------------------------- motifs (dessinés dans le bandeau, clippés)
def _motif(c, kind: str, x: float, y: float, w: float, h: float, col, rnd: random.Random) -> None:
    c.saveState()
    p = c.beginPath(); p.rect(x, y, w, h); c.clipPath(p, stroke=0, fill=0)
    c.setStrokeColor(col); c.setFillColor(col); c.setStrokeAlpha(0.28); c.setFillAlpha(0.22); c.setLineWidth(1.1)
    if kind == "waves":
        for i in range(9):
            yy = y + h * (0.1 + i * 0.1) + rnd.uniform(-3, 3); ph = rnd.uniform(0, 6)
            p = c.beginPath(); p.moveTo(x, yy)
            for k in range(0, 41):
                xx = x + w * k / 40; p.lineTo(xx, yy + 9 * math.sin(k / 40 * 6.28 * 1.5 + ph + i * 0.5))
            c.drawPath(p, stroke=1, fill=0)
    elif kind == "dots":
        step = 0.62 * cm
        for i in range(int(w / step) + 1):
            for j in range(int(h / step) + 1):
                r = 0.05 * cm + 0.07 * cm * (0.5 + 0.5 * math.sin(i * 0.7 + j * 0.45 + rnd.random() * 0.2))
                c.circle(x + i * step, y + j * step, r, stroke=0, fill=1)
    elif kind == "gantt":
        y0 = y + h * 0.08
        while y0 < y + h * 0.92:
            bw = rnd.uniform(0.25, 0.7) * w; bx = x + rnd.uniform(-0.05, 0.4) * w
            c.roundRect(bx, y0, bw, 0.34 * cm, 0.12 * cm, stroke=0, fill=1); y0 += 0.78 * cm
    elif kind == "arcs":
        cx, cy = x + w * rnd.uniform(0.7, 1.0), y + h * rnd.uniform(0.05, 0.3)
        for i in range(1, 9):
            c.circle(cx, cy, i * 1.05 * cm, stroke=1, fill=0)
    elif kind == "bars":
        n = 9; bw = w / n
        for i in range(n):
            bh = h * rnd.uniform(0.12, 0.5); c.rect(x + i * bw + 3, y, bw - 6, bh, stroke=0, fill=1)
    elif kind == "hex":
        r = 0.95 * cm; dx, dy = r * 1.5, r * math.sqrt(3) / 2
        for i in range(-1, int(w / dx) + 2):
            for j in range(-1, int(h / (2 * dy)) + 2):
                cx, cy = x + i * dx, y + j * 2 * dy + (dy if i % 2 else 0)
                p = c.beginPath()
                for k in range(6):
                    a = math.pi / 3 * k; (p.moveTo if k == 0 else p.lineTo)(cx + r * 0.92 * math.cos(a), cy + r * 0.92 * math.sin(a))
                p.close(); c.drawPath(p, stroke=1, fill=0)
    elif kind == "coins":
        for _ in range(16):
            cc = (x + rnd.uniform(0, w), y + rnd.uniform(0, h)); r = rnd.uniform(0.35, 1.15) * cm
            c.circle(*cc, r, stroke=1, fill=0); c.circle(*cc, r * 0.62, stroke=0, fill=1)
    elif kind == "shapes":
        for _ in range(14):
            sx, sy, s = x + rnd.uniform(0, w), y + rnd.uniform(0, h), rnd.uniform(0.4, 1.0) * cm; k = rnd.randrange(3)
            if k == 0: c.circle(sx, sy, s / 2, stroke=1, fill=0)
            elif k == 1: c.rect(sx, sy, s, s, stroke=0, fill=1)
            else:
                p = c.beginPath(); p.moveTo(sx, sy); p.lineTo(sx + s, sy); p.lineTo(sx + s / 2, sy + s); p.close(); c.drawPath(p, stroke=1, fill=0)
    else:  # stripes
        step = 0.7 * cm; off = rnd.uniform(0, step)
        for i in range(int((w + h) / step) + 2):
            c.line(x + i * step - off, y, x + i * step - off - h, y + h)
    c.restoreState()


# --------------------------------------------------------------------------- icônes (unité = rayon 1, centrées en 0,0, traits blancs)
def _icon(c, kind: str, cx: float, cy: float, s: float, col) -> None:
    c.saveState(); c.translate(cx, cy); c.scale(s, s)
    c.setStrokeColor(col); c.setFillColor(col); c.setLineCap(1); c.setLineJoin(1); c.setLineWidth(0.12)
    if kind == "speech":
        c.roundRect(-0.85, -0.05, 1.0, 0.7, 0.18, stroke=1, fill=0)
        c.roundRect(-0.15, -0.65, 1.0, 0.65, 0.18, stroke=0, fill=1)
        c.setFillColor(colors.black); c.setFillAlpha(0.35)
        for dx in (-0.5, -0.2, 0.1): c.circle(dx - 0.0, 0.3, 0.06, stroke=0, fill=1)
    elif kind == "code":
        for sg in (-1, 1):
            p = c.beginPath(); p.moveTo(sg * 0.45, 0.5); p.lineTo(sg * 0.95, 0); p.lineTo(sg * 0.45, -0.5); c.drawPath(p, stroke=1, fill=0)
        c.line(0.18, 0.62, -0.18, -0.62)
    elif kind == "gantt":
        for i, (bx, bw) in enumerate([(-0.8, 0.9), (-0.25, 0.95), (-0.55, 0.7)]):
            c.roundRect(bx, 0.45 - i * 0.55, bw, 0.28, 0.1, stroke=0, fill=1)
        c.line(0.9, 0.75, 0.9, -0.85)
    elif kind == "target":
        for r in (0.85, 0.52, 0.2): c.circle(0, 0, r, stroke=1, fill=0)
        c.line(0.05, 0.05, 0.85, 0.85); c.line(0.85, 0.85, 0.85, 0.5); c.line(0.85, 0.85, 0.5, 0.85)
    elif kind == "chart":
        for i, hh in enumerate((0.5, 0.95, 0.72)): c.rect(-0.8 + i * 0.58, -0.8, 0.4, hh, stroke=0, fill=1)
        p = c.beginPath(); p.moveTo(-0.85, 0.25); p.lineTo(-0.3, 0.55); p.lineTo(0.15, 0.4); p.lineTo(0.85, 0.85); c.drawPath(p, stroke=1, fill=0)
    elif kind == "cloud":
        c.circle(-0.35, -0.05, 0.38, stroke=0, fill=1); c.circle(0.15, 0.2, 0.5, stroke=0, fill=1); c.circle(0.55, -0.1, 0.32, stroke=0, fill=1)
        c.roundRect(-0.7, -0.45, 1.6, 0.4, 0.2, stroke=0, fill=1)
    elif kind == "shield":
        p = c.beginPath(); p.moveTo(0, 0.95); p.lineTo(0.75, 0.62); p.lineTo(0.7, -0.15); p.curveTo(0.6, -0.55, 0.3, -0.8, 0, -0.95)
        p.curveTo(-0.3, -0.8, -0.6, -0.55, -0.7, -0.15); p.lineTo(-0.75, 0.62); p.close(); c.drawPath(p, stroke=1, fill=0)
        p = c.beginPath(); p.moveTo(-0.28, 0); p.lineTo(-0.05, -0.25); p.lineTo(0.33, 0.25); c.drawPath(p, stroke=1, fill=0)
    elif kind == "growth":
        c.circle(0, 0, 0.9, stroke=1, fill=0)
        p = c.beginPath(); p.moveTo(-0.5, -0.35); p.lineTo(-0.1, 0.0); p.lineTo(0.15, -0.2); p.lineTo(0.55, 0.35); c.drawPath(p, stroke=1, fill=0)
        c.line(0.55, 0.35, 0.55, 0.1); c.line(0.55, 0.35, 0.3, 0.35)
    elif kind == "shapes":
        c.circle(-0.45, 0.35, 0.36, stroke=1, fill=0); c.rect(0.12, -0.02, 0.62, 0.62, stroke=0, fill=1)
        p = c.beginPath(); p.moveTo(-0.7, -0.75); p.lineTo(0.0, -0.75); p.lineTo(-0.35, -0.1); p.close(); c.drawPath(p, stroke=1, fill=0)
        c.circle(0.45, -0.5, 0.2, stroke=0, fill=1)
    else:  # cap : toque de diplômé
        p = c.beginPath(); p.moveTo(0, 0.6); p.lineTo(0.95, 0.15); p.lineTo(0, -0.3); p.lineTo(-0.95, 0.15); p.close(); c.drawPath(p, stroke=0, fill=1)
        p = c.beginPath(); p.moveTo(-0.55, -0.1); p.lineTo(-0.55, -0.55); p.curveTo(-0.3, -0.8, 0.3, -0.8, 0.55, -0.55); p.lineTo(0.55, -0.1); c.drawPath(p, stroke=1, fill=0)
        c.line(0.95, 0.15, 0.95, -0.55)
    c.restoreState()


def _spaced(c, x, y, text, font, size, space, center=False):
    c.saveState(); t = c.beginText(); t.setFont(font, size); t.setCharSpace(space)
    if center:
        x -= (pdfmetrics.stringWidth(text, font, size) + space * len(text)) / 2
    t.setTextOrigin(x, y); t.textOut(text); c.drawText(t); c.restoreState()


# --------------------------------------------------------------------------- page
def certificate_page(c, *, cert_id: str, name: str, training: dict, issued: str, verify_url: str, lang: str, verified: bool, pdf) -> None:
    """Dessine l'attestation sur le canvas `c` (A4 paysage). `pdf` = module pdf_gen (labels, para, sign, _seal, _qr)."""
    lb = pdf.labels(lang)
    th = theme_for(training); dark, accent, tint, motif, icon = THEMES[th]
    w, h = landscape(A4); rtl = lang == "ar"
    band = 8.2 * cm
    bx = w - band if rtl else 0.0                     # bandeau coloré : à gauche, ou à droite en arabe
    cx0, cw = (1.9 * cm, w - band - 3.8 * cm) if rtl else (band + 1.9 * cm, w - band - 3.8 * cm)
    rnd = random.Random(int(hashlib.sha256(str(training.get("title", th)).encode()).hexdigest()[:8], 16))

    c.setTitle(f"{lb['cert_title']} {cert_id}")
    c.setFillColor(tint); c.rect(0, 0, w, h, stroke=0, fill=1)                       # fond teinté
    c.setFillColor(colors.white); c.roundRect(0.7 * cm, 0.7 * cm, w - 1.4 * cm, h - 1.4 * cm, 0.5 * cm, stroke=0, fill=1)  # carte blanche
    # bandeau
    c.saveState()
    p = c.beginPath(); p.roundRect(0.7 * cm, 0.7 * cm, w - 1.4 * cm, h - 1.4 * cm, 0.5 * cm); c.clipPath(p, stroke=0, fill=0)
    c.setFillColor(dark); c.rect(bx, 0, band, h, stroke=0, fill=1)
    c.restoreState()
    _motif(c, motif, bx if rtl else bx + 0.7 * cm, 0.7 * cm, band - 0.7 * cm, h - 1.4 * cm, accent, rnd)
    # icône dans un disque
    icx, icy = bx + band / 2, h * 0.62
    c.setFillColor(accent); c.setFillAlpha(1); c.circle(icx, icy, 2.35 * cm, stroke=0, fill=1)
    c.setFillColor(dark); c.circle(icx, icy, 2.05 * cm, stroke=0, fill=1)
    _icon(c, icon, icx, icy, 1.25 * cm, colors.white)
    # marque + domaine
    c.setFillColor(colors.white); _spaced(c, icx, h - 2.6 * cm, "CARRIVA", "Helvetica-Bold", 15, 2.5, center=True)
    c.setFillColor(accent); c.rect(icx - 0.9 * cm, h - 3.05 * cm, 1.8 * cm, 0.1 * cm, stroke=0, fill=1)
    names = NAMES.get(lang, NAMES["en"]); label = names[PRIORITY.index(th)]
    st = ParagraphStyle("dom", fontName="Helvetica-Bold", fontSize=10, leading=14, alignment=TA_CENTER, textColor=colors.white)
    pp = pdf.para(label, st, band - 1.6 * cm, lang, align=TA_CENTER); _, ph = pp.wrap(band - 1.6 * cm, h)
    pp.drawOn(c, bx + 0.8 * cm, 2.0 * cm)
    # contenu
    align = TA_RIGHT if rtl else TA_LEFT
    y = h - 3.3 * cm

    def block(text, size, bold=False, color=colors.black, gap=0.4 * cm, spaced=False):
        nonlocal y
        st = ParagraphStyle("b", fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=size, leading=size * 1.25, alignment=align, textColor=color)
        pp = pdf.para(text, st, cw, lang, align=align); _, ph = pp.wrap(cw, h)
        pp.drawOn(c, cx0, y - ph); y -= ph + gap

    if rtl:
        block(lb["cert_title"], 13, True, accent.clone(alpha=1) if hasattr(accent, "clone") else accent, 0.9 * cm)
    else:
        c.setFillColor(accent); _spaced(c, cx0, y - 0.3 * cm, lb["cert_title"].upper(), "Helvetica-Bold", 12, 3); y -= 1.3 * cm
    block(lb["awarded"], 13, False, pdf.GRAY, 0.3 * cm)
    nsize = 40 if len(name) <= 20 else 32 if len(name) <= 30 else 24
    block(name, nsize, True, dark, 0.45 * cm)
    c.setFillColor(accent); c.rect(cx0 if not rtl else cx0 + cw - 3.2 * cm, y + 0.05 * cm, 3.2 * cm, 0.14 * cm, stroke=0, fill=1); y -= 1.2 * cm
    block(lb["completed"], 13, False, pdf.GRAY, 0.3 * cm)
    block(training.get("title", ""), 26, True, dark, 0.6 * cm)
    meta = " · ".join(x for x in (training.get("provider"), training.get("duration"), training.get("level")) if x)
    if meta:
        block(meta, 12, False, pdf.GRAY, 0.3 * cm)
    # pied : QR, numéro, vérification, cachet
    qr = 3.0 * cm
    qx = cx0 + cw - qr if rtl else cx0
    c.setFillColor(colors.white); c.setStrokeColor(tint); c.setLineWidth(1)
    c.roundRect(qx - 0.25 * cm, 1.55 * cm - 0.25 * cm, qr + 0.5 * cm, qr + 0.5 * cm, 0.25 * cm, stroke=1, fill=1)
    pdf._qr(c, verify_url, qx, 1.55 * cm, qr)
    tx = qx - 0.6 * cm - 5.4 * cm if rtl else qx + qr + 0.6 * cm
    foot = ParagraphStyle("f", fontName="Helvetica", fontSize=9, leading=12.5, alignment=align, textColor=pdf.GRAY)
    lines = [f"{lb['issued']} {issued}", f"{lb['number']} {cert_id}", f"{lb['verify']}: {verify_url}"]
    pp = pdf.para("\n".join(lines), foot, 5.4 * cm, lang, align=align); _, ph = pp.wrap(5.4 * cm, h)
    pp.drawOn(c, tx, 1.55 * cm + qr - ph - 0.1 * cm)
    sx = cx0 + 1.0 * cm + 2.5 * cm if rtl else cx0 + cw - 2.5 * cm - 0.2 * cm
    pdf._seal(c, sx, 3.5 * cm, 2.5 * cm, pdf.sign(cert_id, name, training.get("title", ""), issued)[:8], issued, verified)
