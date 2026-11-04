"""Bouton 1 (Espace Candidat) : portfolio + CV interactif en UNE page HTML (Tailwind CSS + Font Awesome), mode nuit, responsive.

Générateur par règles (gratuit, sans IA ni tiers, rien n'est conservé) : le HTML est construit à partir du CV saisi.
Anti-hallucination : rien n'est inventé (pas de faux projets, témoignages ni chiffres) ; ce qui manque est signalé par `[⚠️ À COMPLÉTER : …]`.
Les niveaux des compétences viennent de la saisie (« Python:90 ») ; sans niveau, la barre est déduite du nombre de postes qui citent la compétence.
Sécurité : tout texte saisi est échappé ; seuls les liens http(s), tel: et mailto: sont produits ; le JavaScript de la page est fixe (aucune donnée saisie n'y est injectée)."""
from __future__ import annotations
import html as _html
import re
import unicodedata

import json
from urllib.parse import quote

from . import bootstrap_biz
from .qr_js import QR_JS

LANGS = ("fr", "en", "de", "es", "it", "ar")
FIELDS = bootstrap_biz.DOMAINS + ("general",)
MAXF = 400
TAILWIND = "https://cdn.tailwindcss.com/3.4.17"
FONTAWESOME = "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css"

PALETTE = {  # (couleur 1, couleur 2, couleur 3) : dégradé adapté au domaine
    "tech": ("#22d3ee", "#6366f1", "#a855f7"), "marketing": ("#f472b6", "#fb923c", "#facc15"), "finance": ("#34d399", "#22d3ee", "#facc15"),
    "education": ("#818cf8", "#38bdf8", "#fbbf24"), "health": ("#2dd4bf", "#38bdf8", "#a7f3d0"), "creative": ("#e879f9", "#818cf8", "#fb7185"),
    "sales": ("#fb923c", "#f43f5e", "#fbbf24"), "ops": ("#38bdf8", "#f59e0b", "#94a3b8"), "hospitality": ("#f59e0b", "#ef4444", "#fde68a"),
    "admin": ("#60a5fa", "#8b5cf6", "#22d3ee"), "general": ("#60a5fa", "#8b5cf6", "#22d3ee"),
}

L = {
    "fr": dict(**{'theme': 'Mode clair / nuit', 'print': 'Enregistrer en PDF / imprimer', 'vcard': 'Ajouter aux contacts', 'qr': 'QR code de cette page', 'top': 'Haut de page', 'close': 'Fermer', 'qr_hint': 'Scannez pour ouvrir ce portfolio sur un téléphone.', 'menu': 'Sections'}, about="À propos", exp="Expériences", skills="Compétences", projects="Projets", edu="Formation", langs="Langues", contact="Contact", call="Appeler", wa="WhatsApp",
               li="LinkedIn", mail="E-mail", present="Présent", hello="Bonjour, je suis", cta="Me contacter", view="Voir le projet", ph="[⚠️ À COMPLÉTER : {x}]", nav="Navigation",
               ph_project="titre et description d'un projet", ph_exp="vos expériences", ph_headline="votre titre professionnel", ph_name="votre nom", rights="Tous droits réservés"),
    "en": dict(**{'theme': 'Light / dark mode', 'print': 'Save as PDF / print', 'vcard': 'Add to contacts', 'qr': 'QR code of this page', 'top': 'Back to top', 'close': 'Close', 'qr_hint': 'Scan to open this portfolio on a phone.', 'menu': 'Sections'}, about="About", exp="Experience", skills="Skills", projects="Projects", edu="Education", langs="Languages", contact="Contact", call="Call", wa="WhatsApp",
               li="LinkedIn", mail="Email", present="Present", hello="Hello, I'm", cta="Contact me", view="View project", ph="[⚠️ TO COMPLETE: {x}]", nav="Navigation",
               ph_project="a project title and description", ph_exp="your experience", ph_headline="your professional title", ph_name="your name", rights="All rights reserved"),
    "de": dict(**{'theme': 'Hell / Dunkel', 'print': 'Als PDF speichern / drucken', 'vcard': 'Zu Kontakten hinzufügen', 'qr': 'QR-Code dieser Seite', 'top': 'Nach oben', 'close': 'Schließen', 'qr_hint': 'Scannen, um dieses Portfolio auf dem Handy zu öffnen.', 'menu': 'Bereiche'}, about="Über mich", exp="Berufserfahrung", skills="Kompetenzen", projects="Projekte", edu="Ausbildung", langs="Sprachen", contact="Kontakt", call="Anrufen", wa="WhatsApp",
               li="LinkedIn", mail="E-Mail", present="Heute", hello="Hallo, ich bin", cta="Kontakt aufnehmen", view="Projekt ansehen", ph="[⚠️ ZU ERGÄNZEN: {x}]", nav="Navigation",
               ph_project="Titel und Beschreibung eines Projekts", ph_exp="Ihre Berufserfahrung", ph_headline="Ihre Berufsbezeichnung", ph_name="Ihr Name", rights="Alle Rechte vorbehalten"),
    "es": dict(**{'theme': 'Modo claro / oscuro', 'print': 'Guardar como PDF / imprimir', 'vcard': 'Añadir a contactos', 'qr': 'Código QR de esta página', 'top': 'Subir', 'close': 'Cerrar', 'qr_hint': 'Escanee para abrir este portfolio en el móvil.', 'menu': 'Secciones'}, about="Sobre mí", exp="Experiencia", skills="Competencias", projects="Proyectos", edu="Formación", langs="Idiomas", contact="Contacto", call="Llamar", wa="WhatsApp",
               li="LinkedIn", mail="Correo", present="Actualidad", hello="Hola, soy", cta="Contactar", view="Ver proyecto", ph="[⚠️ POR COMPLETAR: {x}]", nav="Navegación",
               ph_project="título y descripción de un proyecto", ph_exp="su experiencia", ph_headline="su título profesional", ph_name="su nombre", rights="Todos los derechos reservados"),
    "it": dict(**{'theme': 'Modalità chiara / scura', 'print': 'Salva come PDF / stampa', 'vcard': 'Aggiungi ai contatti', 'qr': 'Codice QR di questa pagina', 'top': 'Torna su', 'close': 'Chiudi', 'qr_hint': 'Inquadra per aprire questo portfolio sul telefono.', 'menu': 'Sezioni'}, about="Chi sono", exp="Esperienze", skills="Competenze", projects="Progetti", edu="Formazione", langs="Lingue", contact="Contatti", call="Chiama", wa="WhatsApp",
               li="LinkedIn", mail="E-mail", present="Presente", hello="Ciao, sono", cta="Contattami", view="Vedi il progetto", ph="[⚠️ DA COMPLETARE: {x}]", nav="Navigazione",
               ph_project="titolo e descrizione di un progetto", ph_exp="le tue esperienze", ph_headline="il tuo titolo professionale", ph_name="il tuo nome", rights="Tutti i diritti riservati"),
    "ar": dict(**{'theme': 'الوضع الفاتح / الداكن', 'print': 'حفظ PDF / طباعة', 'vcard': 'إضافة إلى جهات الاتصال', 'qr': 'رمز QR لهذه الصفحة', 'top': 'أعلى الصفحة', 'close': 'إغلاق', 'qr_hint': 'امسح الرمز لفتح هذا المعرض على الهاتف.', 'menu': 'الأقسام'}, about="نبذة عني", exp="الخبرات", skills="المهارات", projects="المشاريع", edu="التكوين", langs="اللغات", contact="التواصل", call="اتصال", wa="واتساب",
               li="لينكدإن", mail="البريد", present="حتى الآن", hello="مرحباً، أنا", cta="تواصل معي", view="عرض المشروع", ph="[⚠️ يُستكمل: {x}]", nav="التنقل",
               ph_project="عنوان ووصف مشروع", ph_exp="خبراتك", ph_headline="مسماك الوظيفي", ph_name="اسمك", rights="جميع الحقوق محفوظة"),
}

_e = lambda s: _html.escape(str(s or ""), quote=True)
_ws = re.compile(r"\s+")


def _c(v, n=MAXF) -> str:
    s = "".join(ch for ch in str(v or "") if ch == "\n" or unicodedata.category(ch)[0] != "C")
    return _ws.sub(" ", s).strip()[:n]


def _url(v: str) -> str:
    v = _c(v, 300)
    if not v:
        return ""
    if not re.match(r"^[a-z][a-z0-9+.-]*:", v, re.I):
        v = "https://" + v
    return v if re.fullmatch(r"https?://[^\s<>\"'`\\]+\.[^\s<>\"'`\\]+", v, re.I) else ""


def _data_img(v) -> str:
    """Photo du CV (JPEG/PNG/WebP en data-URI, ≤ 600 Ko) intégrée à la page : le fichier HTML reste autonome."""
    v = str(v or "")
    return v if len(v) <= 600_000 and re.fullmatch(r"data:image/(?:jpeg|png|webp);base64,[A-Za-z0-9+/=]+", v) else ""


def _linkedin(v: str) -> str:
    v = _c(v, 300)
    if not v:
        return ""
    if re.fullmatch(r"[A-Za-z0-9\-_%.]{3,100}", v):
        return "https://www.linkedin.com/in/" + v
    u = _url(v)
    return u if re.match(r"https://([a-z]{2,3}\.)?linkedin\.com/", u, re.I) else ""


def _digits(v: str) -> str:
    raw = _c(v, 40)
    d = re.sub(r"\D", "", raw)
    if raw.strip().startswith("00"):
        d = d[2:]
    return d if 8 <= len(d) <= 15 else ""


def _ph(T, k):
    return T["ph"].format(x=T[k])


def _mark(s: str) -> str:
    return re.sub(r"(\[⚠️[^\]]*\])", r'<mark class="ph">\1</mark>', _e(s))


def _date(s: str, T) -> str:
    s = _c(s, 20)
    m = re.fullmatch(r"(\d{4})-(\d{2})", s)
    return f"{m.group(2)}/{m.group(1)}" if m else s


def _initials(name: str) -> str:
    parts = [w for w in re.split(r"[\s\-]+", name) if w]
    return ("".join(w[0] for w in parts[:2]) or "•").upper()


def _skills(cv: dict, exps: list[dict]):
    corpus = _fold(" ".join(f"{x['title']} {x['description']}" for x in exps) + " " + _c(cv.get("summary"), 800))
    out = []
    for raw in (cv.get("skills") or [])[:24]:
        raw = _c(raw, 60)
        m = re.fullmatch(r"(.+?)\s*[:=]\s*(\d{1,3})\s*%?", raw)
        name, given = (m.group(1).strip(), min(100, int(m.group(2)))) if m else (raw, None)
        if not name:
            continue
        if given is None:
            n = len(re.findall(r"(?<!\w)" + re.escape(_fold(name)) + r"(?!\w)", corpus))
            level, shown = min(90, 55 + 12 * n), None
        else:
            level, shown = max(10, given), given
        out.append({"name": name, "level": level, "shown": shown})
    return out[:16]


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(s).lower()) if unicodedata.category(c) != "Mn")


def _projects(text: str) -> list[dict]:
    out = []
    for line in str(text or "").splitlines()[:6]:
        parts = [p.strip() for p in line.split("|")]
        if not parts or not parts[0]:
            continue
        out.append({"title": _c(parts[0], 80), "desc": _c(parts[1], 220) if len(parts) > 1 else "", "url": _url(parts[2]) if len(parts) > 2 else ""})
    return out


def detect_field(cv: dict, field: str) -> str:
    if field in FIELDS and field != "general":
        return field
    text = _fold(" ".join([_c(cv.get("summary"), 800), " ".join(_c(s, 60) for s in (cv.get("skills") or [])[:30])] +
                          [f"{x.get('title', '')} {x.get('description', '')}" for x in (cv.get("experiences") or [])[:10]]))
    hits = bootstrap_biz._matches(text, bootstrap_biz.DOM_KW)
    return max(hits, key=lambda k: (len(hits[k]), -bootstrap_biz.DOMAINS.index(k))) if hits else "general"


def build(p: dict) -> dict:
    lang = p.get("lang") if p.get("lang") in LANGS else "fr"
    T = L[lang]
    cv = p.get("cv") or {}
    name = _c(cv.get("full_name"), 80)
    warn = []
    exps = [{"title": _c(x.get("title"), 90), "company": _c(x.get("company"), 90), "city": _c(x.get("city"), 60), "start": _date(x.get("start"), T), "end": _date(x.get("end"), T),
             "description": "\n".join(_c(l, 220) for l in str(x.get("description") or "").replace(";", "\n").splitlines() if _c(l))[:900]}
            for x in (cv.get("experiences") or [])[:12] if _c(x.get("title")) or _c(x.get("company"))]
    edus = [{"degree": _c(x.get("degree"), 100), "school": _c(x.get("school"), 100), "start": _date(x.get("start"), T), "end": _date(x.get("end"), T)}
            for x in (cv.get("education") or [])[:8] if _c(x.get("degree")) or _c(x.get("school"))]
    langs = [{"name": _c(x.get("name"), 40), "level": _c(x.get("level"), 12)} for x in (cv.get("languages") or [])[:8] if _c(x.get("name"))]
    skills = _skills(cv, exps)
    projects = _projects(p.get("projects"))
    headline = _c(p.get("headline"), 90) or (exps[0]["title"] if exps else "")
    summary = _c(cv.get("summary"), 700)
    field = detect_field(cv, p.get("field") or "auto")
    c1, c2, c3 = PALETTE[field]
    email = _c(cv.get("email"), 120)
    email = email if re.fullmatch(r"[^@\s<>\"'`]+@[^@\s<>\"'`]+\.[^@\s<>\"'`]+", email) else ""
    phone_raw = _c(cv.get("phone"), 40)
    phone = _digits(phone_raw)
    wa = _digits(p.get("whatsapp")) or phone
    li = _linkedin(p.get("linkedin") or "") or _linkedin(cv.get("website") or "")
    web = _url(cv.get("website") or "")
    web = "" if web and "linkedin.com" in web.lower() else web
    photo = _url(p.get("photo_url") or "") or _data_img(cv.get("photo"))
    city = ", ".join(x for x in (_c(cv.get("city"), 60), _c(cv.get("country"), 60)) if x)
    if not name:
        warn.append("name")
    if not headline:
        warn.append("headline")
    if not exps:
        warn.append("experience")
    if not projects:
        warn.append("projects")
    if not phone:
        warn.append("phone")
    if not li:
        warn.append("linkedin")
    if not skills:
        warn.append("skills")
    rtl = lang == "ar"
    nm = name or _ph(T, "ph_name")
    hl = headline or _ph(T, "ph_headline")
    gradtxt = "bg-gradient-to-r from-[var(--c1)] via-[var(--c2)] to-[var(--c3)] bg-clip-text text-transparent"

    # ---- sections -----------------------------------------------------------------------------------------------------------------
    def title(icon, label):
        return f'<h2 class="reveal mb-8 flex items-center gap-3 text-2xl font-extrabold tracking-tight sm:text-3xl"><span class="ico"><i class="{icon}" aria-hidden="true"></i></span><span class="{gradtxt}">{_e(label)}</span></h2>'

    hide = ' style="display:none"' if photo else ""
    avatar_inner = '<span class="avatar-fallback"' + hide + '>' + _e(_initials(name) if name else "•") + '</span>'
    img = ""
    if photo:
        img = ('<img src="' + _e(photo) + '" alt="' + _e(name) + '" class="h-full w-full rounded-full object-cover" referrerpolicy="no-referrer" '
               "onerror=\"this.style.display='none';this.nextElementSibling.style.display='flex'\">")
    avatar = '<div class="avatar" role="img" aria-label="' + _e(name or T["ph_name"]) + '">' + img + avatar_inner + '</div>'

    btns = [f'<a href="#contact" class="btn-main">{_e(T["cta"])}<i class="fa-solid fa-arrow-{"left" if rtl else "right"} ms-2" aria-hidden="true"></i></a>']
    if li:
        btns.append(f'<a href="{_e(li)}" target="_blank" rel="noopener noreferrer" class="btn-ghost"><i class="fa-brands fa-linkedin-in me-2" aria-hidden="true"></i>{_e(T["li"])}</a>')
    hero = f"""<header class="relative overflow-hidden px-5 pb-16 pt-14 text-center sm:pt-20">
  <div class="aurora" aria-hidden="true"></div>
  <div class="relative mx-auto max-w-3xl">
    {avatar}
    <p class="mt-6 text-sm uppercase tracking-[.25em] text-slate-400">{_e(T["hello"])}</p>
    <h1 class="mt-2 text-4xl font-black leading-tight sm:text-6xl"><span class="{gradtxt}">{_mark(nm)}</span></h1>
    <p class="mt-3 text-lg font-semibold text-slate-200 sm:text-2xl">{_mark(hl)}</p>
    {f'<p class="mx-auto mt-5 max-w-2xl text-slate-300 sm:text-lg">{_e(summary)}</p>' if summary else ""}
    <div class="mt-8 flex flex-wrap items-center justify-center gap-3">{"".join(btns)}</div>
  </div>
</header>"""

    skills_html = ""
    if skills:
        bars = ""
        for sk in skills:
            pct = '<span class="text-slate-400">' + str(sk["shown"]) + '%</span>' if sk["shown"] is not None else ""
            bars += ('<li class="reveal"><div class="mb-1.5 flex justify-between text-sm font-semibold"><span>' + _e(sk["name"]) + '</span>' + pct + '</div>'
                     '<div class="bar-track"><div class="bar" style="--w:' + str(sk["level"]) + '%"></div></div></li>')
        skills_html = '<section id="skills" class="section">' + title("fa-solid fa-bolt", T["skills"]) + '<ul class="grid gap-5 sm:grid-cols-2">' + bars + '</ul></section>'

    if exps:
        items = []
        for x in exps:
            when = " – ".join(v for v in (x["start"], x["end"] or (T["present"] if x["start"] else "")) if v)
            where = " · ".join(v for v in (x["company"], x["city"]) if v)
            lines = "".join(f"<li>{_e(l)}</li>" for l in x["description"].splitlines() if l)
            ul = '<ul class="tl-list">' + lines + '</ul>' if lines else ""
            items.append('<li class="tl-item reveal"><span class="tl-dot" aria-hidden="true"></span><p class="text-sm font-semibold text-[var(--c1)]">' + _e(when) + '</p>'
                         '<h3 class="text-lg font-bold">' + _e(x["title"]) + '</h3><p class="text-slate-400">' + _e(where) + '</p>' + ul + '</li>')
        timeline = "".join(items)
    else:
        timeline = f'<li class="tl-item reveal"><span class="tl-dot" aria-hidden="true"></span><p>{_mark(_ph(T, "ph_exp"))}</p></li>'
    exp_html = f'<section id="experience" class="section">{title("fa-solid fa-briefcase", T["exp"])}<ol class="timeline">{timeline}</ol></section>'

    if projects:
        cards = ""
        for pr in projects:
            d = '<p class="mt-2 text-slate-300">' + _e(pr["desc"]) + '</p>' if pr["desc"] else ""
            lk = ('<a href="' + _e(pr["url"]) + '" target="_blank" rel="noopener noreferrer" class="card-link">' + _e(T["view"]) +
                  ' <i class="fa-solid fa-arrow-up-right-from-square ms-1" aria-hidden="true"></i></a>') if pr["url"] else ""
            cards += ('<article class="card reveal" tabindex="0"><div class="card-ico"><i class="fa-solid fa-diagram-project" aria-hidden="true"></i></div>'
                      '<h3 class="mt-4 text-lg font-bold">' + _e(pr["title"]) + '</h3>' + d + lk + '</article>')
    else:
        cards = ('<article class="card reveal"><div class="card-ico"><i class="fa-solid fa-diagram-project" aria-hidden="true"></i></div><p class="mt-4">'
                 + _mark(_ph(T, "ph_project")) + '</p></article>')
    proj_html = f'<section id="projects" class="section">{title("fa-solid fa-rocket", T["projects"])}<div class="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{cards}</div></section>'

    extra = ""
    if edus:
        ed = "".join(f'<li class="reveal"><p class="font-bold">{_e(x["degree"])}</p><p class="text-slate-400">{_e(" · ".join(v for v in (x["school"], " – ".join(w for w in (x["start"], x["end"]) if w)) if v))}</p></li>' for x in edus)
        extra += f'<div><h3 class="mb-4 flex items-center gap-2 text-xl font-bold"><i class="fa-solid fa-graduation-cap text-[var(--c1)]" aria-hidden="true"></i>{_e(T["edu"])}</h3><ul class="space-y-4">{ed}</ul></div>'
    if langs:
        lg = ""
        for x in langs:
            lv = ' <b>' + _e(x["level"]) + '</b>' if x["level"] else ""
            lg += '<li class="chip reveal">' + _e(x["name"]) + lv + '</li>'
        extra += f'<div><h3 class="mb-4 flex items-center gap-2 text-xl font-bold"><i class="fa-solid fa-language text-[var(--c1)]" aria-hidden="true"></i>{_e(T["langs"])}</h3><ul class="flex flex-wrap gap-2">{lg}</ul></div>'
    extra_html = f'<section id="education" class="section"><div class="grid gap-10 sm:grid-cols-2">{extra}</div></section>' if extra else ""

    ct = []
    if email:
        ct.append(f'<a class="contact" href="mailto:{_e(email)}"><i class="fa-solid fa-envelope" aria-hidden="true"></i><span dir="ltr">{_e(email)}</span></a>')
    if phone:
        ct.append(f'<a class="contact" href="tel:+{phone}"><i class="fa-solid fa-phone" aria-hidden="true"></i><span dir="ltr">{_e(phone_raw)}</span></a>')
    if city:
        ct.append(f'<p class="contact"><i class="fa-solid fa-location-dot" aria-hidden="true"></i><span>{_e(city)}</span></p>')
    if web:
        ct.append(f'<a class="contact" href="{_e(web)}" target="_blank" rel="noopener noreferrer"><i class="fa-solid fa-globe" aria-hidden="true"></i><span dir="ltr">{_e(web)}</span></a>')
    if li:
        ct.append(f'<a class="contact" href="{_e(li)}" target="_blank" rel="noopener noreferrer"><i class="fa-brands fa-linkedin-in" aria-hidden="true"></i><span dir="ltr">LinkedIn</span></a>')
    if not ct:
        ct.append(f'<p class="contact">{_mark(_ph(T, "ph_name").replace(T["ph_name"], T["mail"]))}</p>')
    contact_html = f'<section id="contact" class="section">{title("fa-solid fa-paper-plane", T["contact"])}<div class="grid gap-3 sm:grid-cols-2">{"".join(ct)}</div></section>'

    bar = []
    if phone:
        bar.append(f'<a href="tel:+{phone}" class="dock-btn" aria-label="{_e(T["call"])}"><i class="fa-solid fa-phone" aria-hidden="true"></i><span>{_e(T["call"])}</span></a>')
    if wa:
        bar.append(f'<a href="https://wa.me/{wa}" target="_blank" rel="noopener noreferrer" class="dock-btn dock-wa" aria-label="{_e(T["wa"])}"><i class="fa-brands fa-whatsapp" aria-hidden="true"></i><span>{_e(T["wa"])}</span></a>')
    if li:
        bar.append(f'<a href="{_e(li)}" target="_blank" rel="noopener noreferrer" class="dock-btn" aria-label="{_e(T["li"])}"><i class="fa-brands fa-linkedin-in" aria-hidden="true"></i><span>{_e(T["li"])}</span></a>')
    dock = f'<nav class="dock" aria-label="{_e(T["contact"])}">{"".join(bar)}</nav>' if bar else ""

    # ---- barre de navigation, outils, vCard, données structurées, QR ------------------------------------------------------------
    links = [("skills", T["skills"], bool(skills_html)), ("experience", T["exp"], True), ("projects", T["projects"], True), ("education", T["edu"] + " / " + T["langs"], bool(extra_html)), ("contact", T["contact"], True)]
    nav_links = "".join(f'<a href="#{i}" data-spy="{i}">{_e(lb)}</a>' for i, lb, ok in links if ok)
    vc = ""
    if name and (phone or email):
        def _v(x):
            return str(x).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", " ")
        lines = ["BEGIN:VCARD", "VERSION:3.0", "FN:" + _v(name)]
        if headline:
            lines.append("TITLE:" + _v(headline))
        if phone:
            lines.append("TEL;TYPE=CELL:+" + phone)
        if email:
            lines.append("EMAIL:" + _v(email))
        for u in (li, web):
            if u:
                lines.append("URL:" + u)
        if city:
            lines.append("ADR:;;" + _v(city) + ";;;;")
        lines.append("END:VCARD")
        vc = (f'<a class="tool" download="{_e(re.sub(r"[^A-Za-z0-9]+", "-", _fold(name)).strip("-") or "contact")}.vcf" href="data:text/vcard;charset=utf-8,{quote(chr(13) + chr(10)).join(quote(x, safe="") for x in lines)}" '
              f'aria-label="{_e(T["vcard"])}" title="{_e(T["vcard"])}"><i class="fa-solid fa-address-card" aria-hidden="true"></i></a>')
    tools = (f'<button type="button" class="tool" id="themeBtn" aria-label="{_e(T["theme"])}" title="{_e(T["theme"])}"><i class="fa-solid fa-circle-half-stroke" aria-hidden="true"></i></button>'
             f'<button type="button" class="tool" id="printBtn" aria-label="{_e(T["print"])}" title="{_e(T["print"])}"><i class="fa-solid fa-file-pdf" aria-hidden="true"></i></button>'
             + vc +
             f'<button type="button" class="tool" id="qrBtn" hidden aria-label="{_e(T["qr"])}" title="{_e(T["qr"])}"><i class="fa-solid fa-qrcode" aria-hidden="true"></i></button>')
    topnav = (f'<div class="progress" id="progress" aria-hidden="true"></div><nav class="topnav" aria-label="{_e(T["menu"])}"><a href="#top" class="brand" aria-label="{_e(T["top"])}">{_e(_initials(name) if name else "•")}</a>'
              f'<div class="navlinks">{nav_links}</div><div class="tools">{tools}</div></nav>')
    qrdlg = (f'<dialog id="qrDlg" class="qrdlg" aria-label="{_e(T["qr"])}"><h2 class="text-lg font-bold">{_e(T["qr"])}</h2><div id="qrBox"></div><p class="text-sm text-slate-400">{_e(T["qr_hint"])}</p>'
             f'<button type="button" class="btn-main" id="qrClose">{_e(T["close"])}</button></dialog>')
    ld = {"@context": "https://schema.org", "@type": "Person", "name": name, "jobTitle": headline, "email": email, "telephone": ("+" + phone) if phone else "", "address": city,
          "sameAs": [u for u in (li, web) if u]}
    ld = {k: v for k, v in ld.items() if v}
    jsonld = ('<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026") + "</script>") if name else ""
    totop = f'<button type="button" class="totop" id="toTop" aria-label="{_e(T["top"])}"><i class="fa-solid fa-arrow-up" aria-hidden="true"></i></button>'

    desc = _c(summary or f"{name} — {headline}", 160)
    page = (_TEMPLATE
            .replace("@@LANG@@", lang).replace("@@DIR@@", "rtl" if rtl else "ltr").replace("@@TITLE@@", _e(f"{name} — {headline}" if name and headline else name or "Portfolio"))
            .replace("@@DESC@@", _e(desc)).replace("@@C1@@", c1).replace("@@C2@@", c2).replace("@@C3@@", c3).replace("@@TAILWIND@@", TAILWIND).replace("@@FA@@", FONTAWESOME)
            .replace("@@JSONLD@@", jsonld).replace("@@QRJS@@", QR_JS).replace("@@OGIMG@@", f'<meta property="og:image" content="{_e(photo)}">' if photo else "").replace("@@BODY@@", f'<span id="top"></span>{topnav}{hero}\n<main class="mx-auto max-w-5xl px-5">{skills_html}{exp_html}{proj_html}{extra_html}{contact_html}</main>\n'
            f'<footer class="px-5 pb-28 pt-10 text-center text-sm text-slate-500 md:pb-10">&copy; {_e(name or "")} · {_e(T["rights"])}</footer>\n{dock}{totop}{qrdlg}'))
    return {"html": page, "field": field, "warnings": warn, "lang": lang}


_TEMPLATE = """<!doctype html>
<html lang="@@LANG@@" dir="@@DIR@@" class="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>@@TITLE@@</title>
<meta name="description" content="@@DESC@@">
<meta name="theme-color" content="#020617">
<meta property="og:title" content="@@TITLE@@">
<meta property="og:description" content="@@DESC@@">
<meta property="og:type" content="profile">
@@OGIMG@@
@@JSONLD@@
<script>try{var _t=localStorage.getItem("pf-theme");if(!_t)_t=matchMedia("(prefers-color-scheme: light)").matches?"light":"dark";if(_t=="light"){document.documentElement.classList.remove("dark");document.documentElement.classList.add("light");}}catch(e){}</script>
<script src="@@TAILWIND@@"></script>
<script>document.documentElement.classList.add('js');try{tailwind.config={darkMode:'class'}}catch(e){}</script>
<link rel="stylesheet" href="@@FA@@" crossorigin="anonymous" referrerpolicy="no-referrer">
<style>
:root{--c1:@@C1@@;--c2:@@C2@@;--c3:@@C3@@}
html{scroll-behavior:smooth}
body{margin:0;background:#020617;color:#e2e8f0;font-family:system-ui,-apple-system,'Segoe UI',Roboto,'Noto Sans Arabic',Arial,sans-serif;line-height:1.65;-webkit-font-smoothing:antialiased}
.aurora{position:absolute;inset:-30% -10% auto;height:130%;background:radial-gradient(40% 40% at 25% 30%,color-mix(in srgb,var(--c1) 38%,transparent),transparent 70%),radial-gradient(38% 38% at 78% 25%,color-mix(in srgb,var(--c2) 38%,transparent),transparent 70%),radial-gradient(35% 35% at 55% 75%,color-mix(in srgb,var(--c3) 28%,transparent),transparent 70%);filter:blur(30px);animation:drift 14s ease-in-out infinite alternate}
@keyframes drift{to{transform:translate3d(0,24px,0) scale(1.06)}}
.avatar{position:relative;margin:0 auto;height:9.5rem;width:9.5rem;border-radius:9999px;padding:4px;background:conic-gradient(from 0deg,var(--c1),var(--c2),var(--c3),var(--c1));box-shadow:0 0 0 6px rgba(255,255,255,.04),0 0 60px color-mix(in srgb,var(--c2) 60%,transparent),0 0 120px color-mix(in srgb,var(--c1) 35%,transparent);animation:glow 4s ease-in-out infinite alternate}
.avatar>*{height:100%;width:100%;border-radius:9999px;background:#0b1224}
.avatar-fallback{display:flex;align-items:center;justify-content:center;font-size:3rem;font-weight:900;color:#fff;background:linear-gradient(135deg,color-mix(in srgb,var(--c1) 35%,#0b1224),color-mix(in srgb,var(--c2) 35%,#0b1224))}
@keyframes glow{to{box-shadow:0 0 0 6px rgba(255,255,255,.06),0 0 90px color-mix(in srgb,var(--c2) 75%,transparent),0 0 160px color-mix(in srgb,var(--c1) 45%,transparent)}}
.btn-main,.btn-ghost{display:inline-flex;align-items:center;min-height:48px;padding:.7rem 1.4rem;border-radius:9999px;font-weight:700;text-decoration:none;transition:transform .2s,box-shadow .2s}
.btn-main{color:#020617;background:linear-gradient(90deg,var(--c1),var(--c2));box-shadow:0 10px 30px color-mix(in srgb,var(--c2) 40%,transparent)}
.btn-ghost{color:#e2e8f0;border:1px solid rgba(148,163,184,.4);background:rgba(15,23,42,.6);backdrop-filter:blur(6px)}
.btn-main:hover,.btn-ghost:hover{transform:translateY(-3px)}
.section{padding:3.5rem 0;scroll-margin-top:3.6rem}
.ico{display:inline-flex;height:2.4rem;width:2.4rem;align-items:center;justify-content:center;border-radius:.8rem;color:#020617;background:linear-gradient(135deg,var(--c1),var(--c2));font-size:1rem}
.reveal{opacity:1;transform:none;transition:opacity .7s ease,transform .7s ease}
.js .reveal{opacity:0;transform:translateY(18px)}.js .reveal.in{opacity:1;transform:none}
.bar-track{height:.7rem;border-radius:9999px;background:rgba(148,163,184,.18);overflow:hidden}
.bar{height:100%;width:var(--w);border-radius:9999px;background:linear-gradient(90deg,var(--c1),var(--c2),var(--c3))}
.js .bar{width:0;transition:width 1.4s cubic-bezier(.2,.8,.2,1)}.js .in .bar{width:var(--w)}
.timeline{position:relative;margin:0;padding:0;list-style:none;border-inline-start:2px solid transparent;border-image:linear-gradient(180deg,var(--c1),var(--c2),transparent) 1;padding-inline-start:1.8rem}
.tl-item{position:relative;margin-bottom:2rem}
.tl-dot{position:absolute;inset-inline-start:calc(-1.8rem - 7px);top:.35rem;height:12px;width:12px;border-radius:9999px;background:var(--c1);box-shadow:0 0 0 4px #020617,0 0 18px var(--c1)}
.tl-list{margin:.6rem 0 0;padding-inline-start:1.1rem;color:#cbd5e1}.tl-list li{margin:.25rem 0}
.card{border-radius:1.25rem;padding:1.4rem;background:linear-gradient(160deg,rgba(30,41,59,.85),rgba(15,23,42,.85));border:1px solid rgba(148,163,184,.2);transition:transform .35s cubic-bezier(.2,.8,.2,1),box-shadow .35s,border-color .35s;outline:none}
.card:hover,.card:focus-visible,.card:active{transform:translateY(-8px) scale(1.015);border-color:var(--c1);box-shadow:0 24px 50px -12px color-mix(in srgb,var(--c2) 55%,transparent)}
.card-ico{display:inline-flex;height:2.8rem;width:2.8rem;align-items:center;justify-content:center;border-radius:.9rem;color:#020617;background:linear-gradient(135deg,var(--c1),var(--c3))}
.card-link{display:inline-block;margin-top:1rem;font-weight:700;color:var(--c1);text-decoration:none}
.chip{border-radius:9999px;padding:.35rem .9rem;border:1px solid rgba(148,163,184,.3);background:rgba(15,23,42,.7)}.chip b{color:var(--c1);margin-inline-start:.3rem}
.contact{display:flex;align-items:center;gap:.8rem;border-radius:1rem;padding:1rem 1.2rem;color:#e2e8f0;text-decoration:none;background:rgba(15,23,42,.7);border:1px solid rgba(148,163,184,.2);word-break:break-all;transition:transform .2s,border-color .2s}
a.contact:hover{transform:translateY(-3px);border-color:var(--c1)}.contact i{color:var(--c1);width:1.2rem;text-align:center}
mark.ph{background:#fef3c7;color:#111827;border-radius:4px;padding:0 .25em}
.dock{position:fixed;inset-inline:.9rem;bottom:.9rem;z-index:50;display:flex;gap:.5rem;padding:.5rem;border-radius:1.4rem;background:rgba(15,23,42,.82);backdrop-filter:blur(14px);border:1px solid rgba(148,163,184,.3);box-shadow:0 18px 40px rgba(0,0,0,.55)}
.dock-btn{flex:1;display:flex;flex-direction:column;align-items:center;gap:.15rem;padding:.55rem .3rem;border-radius:1rem;color:#fff;text-decoration:none;font-size:.72rem;font-weight:700;background:linear-gradient(135deg,var(--c1),var(--c2));min-height:48px;justify-content:center}
.dock-btn i{font-size:1.15rem}.dock-wa{background:linear-gradient(135deg,#25d366,#128c7e)}
@media (min-width:768px){.dock{display:none}}
.topnav{position:sticky;top:0;z-index:60;display:flex;align-items:center;gap:.6rem;padding:.5rem .8rem;background:rgba(2,6,23,.78);backdrop-filter:blur(14px);border-bottom:1px solid rgba(148,163,184,.2)}
.brand{display:inline-flex;height:2.4rem;width:2.4rem;flex:none;align-items:center;justify-content:center;border-radius:.8rem;font-weight:900;color:#020617;text-decoration:none;background:linear-gradient(135deg,var(--c1),var(--c2))}
.navlinks{display:flex;flex:1;gap:.3rem;overflow-x:auto;scrollbar-width:none}.navlinks::-webkit-scrollbar{display:none}
.navlinks a{white-space:nowrap;padding:.45rem .8rem;border-radius:9999px;color:#94a3b8;text-decoration:none;font-size:.85rem;font-weight:600;transition:color .2s,background .2s}
.navlinks a:hover{color:#e2e8f0}.navlinks a.on{color:#020617;background:linear-gradient(90deg,var(--c1),var(--c2))}
.tools{display:flex;gap:.3rem;flex:none}.tool{display:inline-flex;height:2.4rem;width:2.4rem;align-items:center;justify-content:center;border-radius:.8rem;border:1px solid rgba(148,163,184,.3);background:rgba(15,23,42,.6);color:inherit;cursor:pointer;text-decoration:none;font-size:1rem}
.tool:hover{border-color:var(--c1);color:var(--c1)}.tool[hidden]{display:none}
.progress{position:fixed;top:0;inset-inline-start:0;z-index:70;height:3px;width:0;background:linear-gradient(90deg,var(--c1),var(--c2),var(--c3))}
.totop{position:fixed;inset-inline-end:1rem;bottom:5.6rem;z-index:55;height:2.8rem;width:2.8rem;border-radius:9999px;border:0;cursor:pointer;color:#020617;background:linear-gradient(135deg,var(--c1),var(--c2));box-shadow:0 10px 30px rgba(0,0,0,.45);opacity:0;pointer-events:none;transition:opacity .25s}
.totop.show{opacity:1;pointer-events:auto}@media (min-width:768px){.totop{bottom:1.2rem}}
.card{position:relative;overflow:hidden}.card::before{content:"";position:absolute;inset:0;pointer-events:none;opacity:0;transition:opacity .3s;background:radial-gradient(260px circle at var(--mx,50%) var(--my,0%),color-mix(in srgb,var(--c1) 22%,transparent),transparent 70%)}.card:hover::before{opacity:1}
.qrdlg{max-width:min(92vw,22rem);border:1px solid rgba(148,163,184,.4);border-radius:1.4rem;padding:1.4rem;text-align:center;background:#0b1224;color:#e2e8f0}.qrdlg::backdrop{background:rgba(2,6,23,.75);backdrop-filter:blur(4px)}
#qrBox{display:flex;justify-content:center;margin:1rem 0}#qrBox svg{max-width:100%;height:auto;border-radius:.8rem}
html.light body{background:#f8fafc;color:#0f172a}
html.light .topnav{background:rgba(255,255,255,.82)}html.light .navlinks a{color:#475569}html.light .navlinks a:hover{color:#0f172a}
html.light .tool{background:#fff;border-color:#cbd5e1}
html.light .card,html.light .chip,html.light .contact,html.light .btn-ghost,html.light .dock,html.light .qrdlg{background:#fff;color:#0f172a;border-color:#cbd5e1}
html.light .text-slate-100,html.light .text-slate-200,html.light .text-slate-300{color:#1e293b}html.light .text-slate-400,html.light .text-slate-500{color:#475569}
html.light .bar-track{background:#e2e8f0}html.light .tl-dot{box-shadow:0 0 0 4px #f8fafc,0 0 14px var(--c1)}html.light .tl-list{color:#334155}
html.light .aurora{opacity:.45}html.light .avatar>*{background:#fff}html.light .btn-ghost{color:#0f172a}
html.light .card-link{color:color-mix(in srgb,var(--c2) 80%,#000)}
@media print{
  @page{margin:14mm}
  .topnav,.progress,.dock,.totop,.aurora,.btn-main,.btn-ghost,.qrdlg{display:none!important}
  html,body{background:#fff!important;color:#111!important}
  *{animation:none!important;transition:none!important;box-shadow:none!important;text-shadow:none!important}
  .js .reveal{opacity:1!important;transform:none!important}.js .bar{width:var(--w)!important}
  .bg-clip-text,.text-transparent{background:none!important;-webkit-text-fill-color:#111!important;color:#111!important}
  .text-slate-100,.text-slate-200,.text-slate-300,.text-slate-400,.text-slate-500,.tl-list{color:#222!important}
  .card,.chip,.contact{background:#fff!important;border:1px solid #bbb!important;color:#111!important}.card::before{display:none}
  .bar{background:#111!important}.bar-track{background:#ddd!important}
  .section{padding:1.2rem 0;break-inside:avoid-page}.tl-item,.card{break-inside:avoid}
  .avatar{box-shadow:none!important;background:#ccc!important}.ico,.card-ico{background:#ddd!important;color:#111!important}
}
a:focus-visible,button:focus-visible{outline:3px solid var(--c1);outline-offset:3px}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}.js .reveal{opacity:1;transform:none}.js .bar{width:var(--w)}}
</style>
</head>
<body class="min-h-screen bg-slate-950 text-slate-100 antialiased">
@@BODY@@
<script>@@QRJS@@</script>
<script>
(function(){
  var d=document,root=d.documentElement,$=function(i){return d.getElementById(i)};
  function theme(m){root.classList.toggle('light',m==='light');root.classList.toggle('dark',m!=='light');var m2=d.querySelector('meta[name=theme-color]');if(m2)m2.content=m==='light'?'#f8fafc':'#020617';try{localStorage.setItem('pf-theme',m)}catch(e){}}
  $('themeBtn').onclick=function(){theme(root.classList.contains('light')?'dark':'light')};
  $('printBtn').onclick=function(){window.print()};
  var secs=[].slice.call(d.querySelectorAll('[data-spy]')),prog=$('progress'),top=$('toTop');
  function onScroll(){
    var h=root.scrollHeight-innerHeight,y=pageYOffset;
    prog.style.width=(h>0?Math.min(100,y/h*100):0)+'%';top.classList.toggle('show',y>600);
    var cur='';secs.forEach(function(a){var s=$(a.getAttribute('data-spy'));if(s&&s.getBoundingClientRect().top<innerHeight*.35)cur=a.getAttribute('data-spy')});
    secs.forEach(function(a){a.classList.toggle('on',a.getAttribute('data-spy')===cur);if(a.classList.contains('on')&&a.scrollIntoView&&a.parentNode.scrollWidth>a.parentNode.clientWidth){a.parentNode.scrollLeft=a.offsetLeft-60}});
  }
  addEventListener('scroll',onScroll,{passive:true});onScroll();
  top.onclick=function(){scrollTo({top:0,behavior:'smooth'})};
  d.querySelectorAll('.card').forEach(function(c){c.addEventListener('pointermove',function(e){var r=c.getBoundingClientRect();c.style.setProperty('--mx',(e.clientX-r.left)+'px');c.style.setProperty('--my',(e.clientY-r.top)+'px')})});
  if(/^https?:$/.test(location.protocol)&&window.CARRIVA_QR){
    var qb=$('qrBtn'),dl=$('qrDlg');qb.hidden=false;
    qb.onclick=function(){$('qrBox').innerHTML=CARRIVA_QR.svg(location.href.split('#')[0],{size:240});dl.showModal?dl.showModal():dl.setAttribute('open','')};
    $('qrClose').onclick=function(){dl.close?dl.close():dl.removeAttribute('open')};
    dl.addEventListener('click',function(e){if(e.target===dl&&dl.close)dl.close()});
  }
  var els=d.querySelectorAll('.reveal');
  if(!('IntersectionObserver' in window)){els.forEach(function(e){e.classList.add('in')});return;}
  var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target);}})},{threshold:.15});
  els.forEach(function(e){io.observe(e)});
})();
</script>
</body>
</html>
"""
