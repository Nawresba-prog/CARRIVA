"""Import d'un CV déjà prêt (PDF, Word .docx, texte) : extraction du texte puis pré-remplissage du formulaire CV.

Analyse par règles (aucune IA, aucune donnée envoyée à un tiers, fichier non conservé) : coordonnées, compétences (dictionnaire canonique + rubrique
« Compétences »), expériences, formations, langues. C'est un POINT DE DÉPART à relire : les mises en page très graphiques (colonnes, tableaux, images) donnent un
résultat partiel, et un PDF scanné (image) n'a pas de texte à extraire. Le PDF d'origine, lui, peut être joint tel quel aux candidatures.
"""
from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from xml.etree import ElementTree

from . import matching

MAX_BYTES = 6_000_000
MAX_PAGES = 30


class ImportError_(ValueError):
    """Fichier inexploitable (message affichable à l'utilisateur)."""


def extract_text(data: bytes, filename: str = "") -> tuple[str, str]:
    """(texte, format) ; le format est détecté sur les octets, pas sur l'extension."""
    if len(data) > MAX_BYTES:
        raise ImportError_("Fichier trop volumineux (6 Mo maximum).")
    if data[:5] == b"%PDF-":
        try:
            from pypdf import PdfReader
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise ModuleNotFoundError("pypdf") from exc
        try:
            rd = PdfReader(io.BytesIO(data))
            if rd.is_encrypted:
                raise ImportError_("PDF protégé par mot de passe : retirez la protection puis réessayez.")
            pages = list(rd.pages)[:MAX_PAGES]
            text = "\n".join((p.extract_text() or "") for p in pages)
        except ImportError_:
            raise
        except Exception as exc:  # noqa: BLE001 — PDF corrompu
            raise ImportError_(f"PDF illisible ({type(exc).__name__}).")
        if len(text.strip()) < 40:
            raise ImportError_("Ce PDF ne contient pas de texte (scan ou image) : exportez-le depuis Word/Docs, ou saisissez votre CV dans l'onglet 1.")
        return text, "pdf"
    if data[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                xml = z.read("word/document.xml")
        except (KeyError, zipfile.BadZipFile):
            raise ImportError_("Format non reconnu : utilisez un PDF, un .docx ou un fichier texte.")
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        root = ElementTree.fromstring(xml)
        paras = []
        for p in root.iter(ns + "p"):
            line = "".join((t.text or "") if t.tag == ns + "t" else ("\t" if t.tag == ns + "tab" else ("\n" if t.tag == ns + "br" else "")) for t in p.iter() if t.tag in (ns + "t", ns + "tab", ns + "br"))
            paras.append(line)
        return "\n".join(paras), "docx"
    if data[:4] == b"\xd0\xcf\x11\xe0":
        raise ImportError_("Ancien format Word (.doc) non pris en charge : enregistrez-le en .docx ou PDF.")
    for enc in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            text = data.decode(enc)
            if text.count("\x00") == 0 and sum(1 for ch in text if ch < " " and ch not in "\n\r\t") <= max(2, len(text) // 50) and sum(ch.isalpha() for ch in text) > len(text) // 4:
                return text, "txt"
        except UnicodeError:
            continue
    raise ImportError_("Format non reconnu : utilisez un PDF, un .docx ou un fichier texte.")


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


SECTIONS = {
    "summary": ["profil", "profil professionnel", "resume", "summary", "profile", "about me", "about", "objectif", "objective", "zusammenfassung", "profilo", "perfil", "a propos", "ملخص", "نبذة"],
    "experience": ["experience", "experiences", "experience professionnelle", "experiences professionnelles", "parcours professionnel", "work experience", "professional experience", "employment", "employment history", "berufserfahrung",
                   "esperienza", "esperienza lavorativa", "experiencia", "experiencia laboral", "الخبرة", "الخبرات", "الخبرة المهنية"],
    "education": ["formation", "formations", "education", "etudes", "parcours academique", "diplomes", "training", "ausbildung", "bildung", "istruzione", "formazione", "formacion", "educacion", "التعليم", "المؤهلات", "التكوين"],
    "skills": ["competences", "competences cles", "skills", "key skills", "technical skills", "kenntnisse", "faehigkeiten", "competenze", "habilidades", "competencias", "المهارات", "الكفاءات"],
    "languages": ["langues", "languages", "sprachen", "lingue", "idiomas", "اللغات"],
    "other": ["centres d'interet", "interets", "hobbies", "loisirs", "interests", "references", "certifications", "projets", "projects", "publications", "benevolat", "volunteering", "interessen", "interessi", "intereses"],
}
_HEAD = {k: {_fold(x) for x in v} for k, v in SECTIONS.items()}
MONTHS = {"jan": "01", "fev": "02", "feb": "02", "mar": "03", "apr": "04", "avr": "04", "mai": "05", "may": "05", "mag": "05", "jun": "06", "giu": "06", "jui": "06", "jul": "07", "lug": "07",
          "aou": "08", "aug": "08", "ago": "08", "sep": "09", "set": "09", "oct": "10", "okt": "10", "ott": "10", "nov": "11", "dec": "12", "dez": "12", "dic": "12"}
PRESENT = r"(?:pr[eé]sente?|actuel(?:lement)?|aujourd.?hui|today|current|now|ongoing|en cours|heute|oggi|actualidad|actual|attuale|bis jetzt|الان|الآن|الحاضر|حتى الان)"
_D = r"(?:(?:\d{1,2}[/.\-])?\d{4}|[a-z]{3,9}\.?\s+\d{4})"
RANGE = re.compile(rf"(?P<a>{_D})\s*(?:-|–|—|a|à|to|bis|al|au|until|jusqu.?a)\s*(?P<b>{_D}|{PRESENT})", re.I)
SINCE = re.compile(rf"(?:depuis|since|seit|dal|desde)\s+(?P<a>{_D})", re.I)
CEFR = {"a1": "A1", "a2": "A2", "b1": "B1", "b2": "B2", "c1": "C1", "c2": "C2"}
LEVEL_WORDS = [("maternelle", "C2"), ("native", "C2"), ("muttersprache", "C2"), ("madrelingua", "C2"), ("materna", "C2"), ("natif", "C2"), ("bilingue", "C2"), ("bilingual", "C2"), ("courant", "C1"), ("fluent", "C1"),
               ("flie", "C1"), ("fluido", "C1"), ("avance", "C1"), ("advanced", "C1"), ("intermediaire", "B1"), ("intermediate", "B1"), ("intermedio", "B1"), ("scolaire", "A2"), ("basic", "A2"), ("debutant", "A1"), ("beginner", "A1"), ("notions", "A1")]
LANG_NAMES = {"francais": "Français", "french": "Français", "franzosisch": "Français", "frances": "Français", "francese": "Français", "الفرنسية": "Français",
              "anglais": "Anglais", "english": "Anglais", "englisch": "Anglais", "ingles": "Anglais", "inglese": "Anglais", "الانجليزية": "Anglais", "الإنجليزية": "Anglais",
              "arabe": "Arabe", "arabic": "Arabe", "arabisch": "Arabe", "arabo": "Arabe", "العربية": "Arabe",
              "allemand": "Allemand", "german": "Allemand", "deutsch": "Allemand", "aleman": "Allemand", "tedesco": "Allemand", "الالمانية": "Allemand", "الألمانية": "Allemand",
              "espagnol": "Espagnol", "spanish": "Espagnol", "spanisch": "Espagnol", "espanol": "Espagnol", "spagnolo": "Espagnol", "الاسبانية": "Espagnol", "الإسبانية": "Espagnol",
              "italien": "Italien", "italian": "Italien", "italienisch": "Italien", "italiano": "Italien", "الايطالية": "Italien", "الإيطالية": "Italien",
              "portugais": "Portugais", "portuguese": "Portugais", "portugiesisch": "Portugais", "portugues": "Portugais", "portoghese": "Portugais",
              "russe": "Russe", "russian": "Russe", "chinois": "Chinois", "chinese": "Chinois", "turc": "Turc", "turkish": "Turc", "neerlandais": "Néerlandais", "dutch": "Néerlandais"}
DEGREE = re.compile(r"\b(master|licence|bachelor|doctorat|phd|mba|bts|dut|but|bac\b|baccalaur|ingenieur|ingenieure|diplome|diploma|degree|laurea|licenciatura|grado|abitur|magister|diplom|uni(?:versite|versity|versitat|versita|versidad)|ecole|school|institut|college|faculte|ensi|isg|fst|الجامعة|ماجستير|بكالوريوس|اجازة|إجازة|دكتوراه)", re.I)
EMAIL = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
PHONE = re.compile(r"(?<![\w/])(\+?\d[\d ().\-]{7,17}\d)(?![\w/])")
URL = re.compile(r"(?:https?://)?(?:www\.)?(?:linkedin\.com/in/|github\.com/)[\w\-./%]+", re.I)
BULLET = re.compile(r"^\s*(?:[-•*▪●◦►➢✓·–—]|\d+[.)])\s+")
SEP = re.compile(r"(?:\s+(?:[-–—|@·]|chez|at|bei|presso)\s+|\s*,\s+)", re.I)


def _heading(line: str) -> str | None:
    t = _fold(re.sub(r"[:#*_•\-–—|•]+", " ", line)).strip()
    t = re.sub(r"\s+", " ", t)
    if not t or len(t) > 40:
        return None
    for k, words in _HEAD.items():
        if t in words:
            return k
    return None


def _ym(tok: str, end: bool = False) -> str:
    """'03/2021' / 'mars 2021' / '2021' -> '2021-03' ; année seule -> '2021-01'. Vide pour « présent »."""
    tok = _fold(tok.strip(" ."))
    if not tok or re.fullmatch(PRESENT, tok, re.I):
        return ""
    m = re.fullmatch(r"(?:(\d{1,2})[/.\-])?(\d{4})", tok)
    if m:
        return f"{m.group(2)}-{int(m.group(1)):02d}" if m.group(1) and 1 <= int(m.group(1)) <= 12 else f"{m.group(2)}-{'12' if end else '01'}"
    m = re.fullmatch(r"([a-z]{3,9})\.?\s+(\d{4})", tok)
    if m:
        pre = m.group(1)[:3]
        mm = "07" if m.group(1).startswith("juil") else MONTHS.get(pre, "01")
        return f"{m.group(2)}-{mm}"
    return ""


def _split_sections(lines: list[str]) -> tuple[list[str], dict[str, list[str]]]:
    head, secs, cur = [], {}, None
    for ln in lines:
        h = _heading(ln)
        if h:
            cur = h; secs.setdefault(cur, []); continue
        (head if cur is None else secs[cur]).append(ln)
    return head, secs


def _name(head: list[str], email: str) -> str:
    for ln in head[:8]:
        t = ln.strip()
        if not t or len(t) > 50 or re.search(r"[@\d/:]|http|www", t):
            continue
        words = t.replace("-", " ").split()
        particles = {"de", "du", "la", "le", "van", "von", "der", "den", "ben", "bin", "el", "al", "di", "da", "dos", "des", "ibn", "abu", "bint"}
        if 2 <= len(words) <= 4 and not t.endswith((".", ",")) and all(w[0].isalpha() and (w[0].isupper() or w[0].lower() == w[0].upper() or w.lower() in particles) for w in words) and not _heading(t) and not re.search(r"\b(cv|curriculum|resume|vitae|lebenslauf)\b", _fold(t)):
            return " ".join(w.capitalize() if w.isupper() else w for w in t.split())
    if email:  # repli : prenom.nom@…
        local = re.split(r"[._\-]", email.split("@")[0])
        if len(local) >= 2 and all(p.isalpha() for p in local[:2]):
            return " ".join(p.capitalize() for p in local[:2])
    return ""


def _title_company(text: str) -> tuple[str, str]:
    parts = SEP.split(text.strip(" -–—|,;:()"), maxsplit=1)
    return (parts[0].strip(" -–—|,;:()"), parts[1].strip(" -–—|,;:()")) if len(parts) == 2 else (parts[0].strip(), "")


def _experiences(lines: list[str]) -> list[dict]:
    idx = []
    for i, ln in enumerate(lines):
        m = RANGE.search(ln)
        if m:
            idx.append((i, m.group("a"), m.group("b"), ln[:m.start()] + " " + ln[m.end():]))
        elif SINCE.search(ln) and len(ln) < 80:
            m2 = SINCE.search(ln); idx.append((i, m2.group("a"), "", ln[:m2.start()] + " " + ln[m2.end():]))
    out, used = [], set()
    for n, (i, a, b, rest) in enumerate(idx):
        rest = re.sub(r"[()\[\]|]", " ", rest); rest = re.sub(r"\s+", " ", rest).strip(" -–—,;:")
        head: list[str] = [rest] if re.search(r"[^\W\d_]{2}", rest) else []
        nxt = idx[n + 1][0] if n + 1 < len(idx) else len(lines)
        j = i + 1
        if len(head) < 2:  # titre sur la ligne précédente (mise en page « Titre / Entreprise | dates »)
            k = i - 1
            if k >= 0 and k not in used and lines[k].strip() and not BULLET.match(lines[k]) and len(lines[k]) < 90 and not RANGE.search(lines[k]):
                head.insert(0, lines[k].strip()); used.add(k)
        while len(head) < 2 and j < nxt and lines[j].strip() and not BULLET.match(lines[j]) and len(lines[j]) < 90 and not (j + 1 == nxt and nxt < len(lines) and not BULLET.match(lines[j])):
            head.append(lines[j].strip()); j += 1
        title, company = (head[0], head[1]) if len(head) >= 2 else (_title_company(head[0]) if head else ("", ""))
        if len(head) >= 2 and not company:
            title, company = head[0], head[1]
        desc = []
        end_at = nxt - 1 if (nxt < len(lines) and (nxt - 1) not in used and lines[nxt - 1].strip() and not BULLET.match(lines[nxt - 1]) and len(lines[nxt - 1]) < 90 and nxt - 1 >= j) else nxt
        for ln in lines[j:end_at]:
            t = BULLET.sub("", ln).strip()
            if t:
                desc.append(t)
        if title:
            out.append({"title": title[:120], "company": company[:120], "start": _ym(a), "end": _ym(b, True), "description": "\n".join(desc)[:1500]})
    return out[:15]


def _education(lines: list[str]) -> list[dict]:
    out, skip = [], set()
    dates_only = lambda t: bool(RANGE.search(t)) and not re.search(r"[^\W\d_]{3}", RANGE.sub(" ", t))
    for i, raw in enumerate(lines):
        ln = raw.strip()
        if i in skip or not ln or BULLET.match(ln):
            continue
        if dates_only(ln):  # dates puis diplôme sur la ligne suivante
            m = RANGE.search(ln)
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if nxt and not dates_only(nxt) and (DEGREE.search(nxt) or True):
                skip.add(i + 1); deg, sch = _title_company(nxt)
                out.append({"degree": deg[:120], "school": sch[:120], "start": _ym(m.group("a")), "end": _ym(m.group("b"), True)})
            continue
        if not DEGREE.search(ln):
            continue
        m = RANGE.search(ln); txt = (ln[:m.start()] + " " + ln[m.end():]) if m else ln
        txt = re.sub(r"\s+", " ", re.sub(r"[()\[\]]", " ", txt)).strip(" -–—,;:|")
        deg, sch = _title_company(txt)
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        nxt, nidx = (lines[j].strip() if j < len(lines) else ""), j
        if not m and nxt and dates_only(nxt):
            m = RANGE.search(nxt); skip.add(j)
            k = j + 1
            while k < len(lines) and not lines[k].strip():
                k += 1
            nxt, nidx = (lines[k].strip() if k < len(lines) else ""), k
        if not sch and nxt and not DEGREE.search(nxt) and not RANGE.search(nxt) and len(nxt) < 80 and not BULLET.match(nxt):
            sch = nxt; skip.add(nidx)
        out.append({"degree": deg[:120], "school": sch[:120], "start": _ym(m.group("a")) if m else "", "end": _ym(m.group("b"), True) if m else ""})
    seen, uniq = set(), []
    for e in out:
        k = (e["degree"].lower(), e["school"].lower())
        if k not in seen and e["degree"]:
            seen.add(k); uniq.append(e)
    return uniq[:10]


def _languages(lines: list[str]) -> tuple[list[dict], str]:
    out, native, seen = [], [], set()
    items = [x for ln in lines for x in re.split(r"[,;|•·\n]|\s{3,}", ln)]
    for it in items:
        t = it.strip(" -–—:*()")
        if not t:
            continue
        f = _fold(t)
        name = next((v for k, v in LANG_NAMES.items() if re.search(rf"(?<![^\W\d_]){re.escape(k)}(?![^\W\d_])", f)), None)
        if not name or name in seen:
            continue
        lvl = next((CEFR[w] for w in re.findall(r"\b([abc][12])\b", f) if w in CEFR), None) or next((v for k, v in LEVEL_WORDS if k in f), "B2")
        seen.add(name); out.append({"name": name, "level": lvl})
        if lvl == "C2" and re.search(r"maternel|native|muttersprache|madrelingua|materna|natif", f):
            native.append(name)
    return out[:10], ", ".join(native)


ACRO = {"sql", "seo", "api", "rest", "ci", "cd", "aws", "gcp", "hr", "ux", "nlp", "etl", "php", "html", "css", "ai", "nosql", "bi", "rh"}


SPECIAL = {"fastapi": "FastAPI", "nodejs": "Node.js", "html css": "HTML/CSS", "ci cd": "CI/CD", "rest api": "REST API", "powerbi": "Power BI", "power bi": "Power BI", "devops": "DevOps", "javascript": "JavaScript",
           "typescript": "TypeScript", "machine learning": "Machine Learning", "github": "GitHub"}


def _pretty(label: str) -> str:
    if label.lower() in SPECIAL:
        return SPECIAL[label.lower()]
    return " ".join(w.upper() if w in ACRO else w.capitalize() for w in label.split())


def parse_cv(text: str) -> dict:
    """Texte brut -> {cv: champs du formulaire, found: compteurs, warnings: [...]}."""
    text = text.replace("\r", "\n").replace(" ", " ").replace("\t", "   ")
    lines = [re.sub(r"[  -​]+", " ", ln).rstrip() for ln in text.split("\n")]
    head, secs = _split_sections(lines)
    email = (EMAIL.search(text) or [""])[0] if EMAIL.search(text) else ""
    ph = next((m.group(1) for m in PHONE.finditer("\n".join(lines[:25])) if len(re.sub(r"\D", "", m.group(1))) >= 8 and not RANGE.search(m.group(1))), "")
    site = (URL.search(text) or [""])[0] if URL.search(text) else ""
    name = _name([l for l in head if l.strip()], email)
    skills_txt = "\n".join(secs.get("skills", []))
    listed = []
    for it in re.split(r"[,;•·|\n]|\s{3,}", skills_txt):
        t = BULLET.sub("", it).strip(" -–—:*")
        t = re.sub(r"^[^:]{2,30}:\s*", "", t) if ":" in t and len(t) > 40 else t
        if 1 < len(t) <= 40 and not _heading(t) and len(t.split()) <= 4:
            listed.append(t)
    listed_ids = {sid for it in listed for sid in matching.extract_skills(it)}
    canonical = [_pretty(matching.label(sid)) for sid in matching.extract_skills(text) if sid not in listed_ids]
    skills, seen = [], set()
    for s in listed + canonical:
        k = _fold(s)
        if k not in seen:
            seen.add(k); skills.append(s)
    exp = _experiences(secs.get("experience", []))
    edu = _education(secs.get("education", []))
    langs, mother = _languages(secs.get("languages", []) or [l for l in lines if _heading(l) is None and any(re.search(rf"\b{re.escape(k)}\b", _fold(l)) for k in LANG_NAMES)][:0])
    summary = " ".join(x.strip() for x in secs.get("summary", []) if x.strip())[:900]
    cv = {"full_name": name, "email": email, "phone": ph.strip(), "website": site, "summary": summary, "mother_tongue": mother, "skills": skills[:40], "experiences": exp, "education": edu, "languages": langs}
    warn = []
    if not name:
        warn.append("name")
    if not email:
        warn.append("email")
    if not exp:
        warn.append("experience")
    if not skills:
        warn.append("skills")
    return {"cv": cv, "found": {"skills": len(skills), "experiences": len(exp), "education": len(edu), "languages": len(langs)}, "warnings": warn}


def import_cv(data: bytes, filename: str = "") -> dict:
    text, fmt = extract_text(data, filename)
    res = parse_cv(text)
    cv = res["cv"]
    if not (cv["email"] or cv["full_name"] or cv["skills"] or cv["experiences"]):
        raise ImportError_("Aucune information de CV reconnue dans ce fichier : vérifiez le fichier ou saisissez votre CV dans l'onglet 1.")
    res["format"] = fmt; res["chars"] = len(text); res["text"] = text[:6000]
    return res
