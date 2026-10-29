"""Traitement des données saisies par l'utilisateur (CV Parser/Builder Agent — partie déterministe).

Rien n'est copié « tel quel » dans le CV : chaque champ est nettoyé, normalisé, validé et structuré.
- noms / intitulés / villes : casse corrigée (« sarah ben AMOR » -> « Sarah Ben Amor »), acronymes préservés ;
- e-mail, téléphone, site web : nettoyés et contrôlés ;
- dates : « mars 2021 », « 03/2021 », « 2021 » -> format ISO ; inversion si fin < début ; « en cours » reconnu ;
- compétences : séparées, dédoublonnées, orthographe canonique (python -> Python, ci/cd -> CI/CD) ;
- langues : noms reconnus (anglais/english/inglés -> code « en »), niveaux CECR normalisés, langue maternelle extraite ;
- activités : découpées en puces, majuscule + point final, doublons supprimés ;
- expériences et formations : triées de la plus récente à la plus ancienne (convention Europass) ;
- permis : catégories validées (« permis b » -> « B »).

La fonction est idempotente : traiter deux fois donne le même résultat. Elle travaille sur des dict (pas de dépendance
à pydantic) et renvoie (données, changements, avertissements) ; les avertissements sont des codes traduits par l'interface.
Aucune donnée personnelle n'est écrite dans les logs.
"""
from __future__ import annotations

import datetime as dt
import re
import unicodedata

# --------------------------------------------------------------------------- utilitaires texte
ACRONYMS = {"it", "ui", "ux", "qa", "hr", "rh", "ia", "ai", "sql", "php", "api", "erp", "crm", "seo", "sem", "cv", "bi", "ci", "cd", "b2b", "b2c",
            "pme", "sap", "iot", "ceo", "cto", "hse", "bts", "dut", "usa", "uk", "ue", "eu"}
PARTICLES = {"de", "du", "des", "del", "della", "di", "da", "van", "von", "der", "den", "la", "le", "et", "and", "of", "the", "for", "en", "au", "aux", "y", "e", "und"}
JUNK = {"", "-", "--", "n/a", "na", "none", "null", "aucun", "aucune", "rien", "x", "xx", "...", "?", "/"}


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm(s: str) -> str:
    """Clé de comparaison : minuscules, sans accents, espaces simples."""
    return re.sub(r"\s+", " ", strip_accents(str(s or "")).lower()).strip()


def clean_spaces(s: str) -> str:
    return re.sub(r"[ \t ​]+", " ", str(s or "").replace("\r", "")).strip()


def is_junk(s: str) -> bool:
    return norm(s) in JUNK


def smart_title(text: str) -> str:
    """Casse « titre » : Jean-Pierre, d'Alembert, Ingénieur IT, Chef de Projet (particules en minuscules sauf en tête)."""
    runs = list(re.finditer(r"[^\W_]+", text))
    out, last = [], 0
    for idx, m in enumerate(runs):
        w, lw = m.group(), m.group().lower()
        nxt = text[m.end():m.end() + 1]
        if lw in ACRONYMS:
            new = w.upper()
        elif idx > 0 and lw in PARTICLES:
            new = lw
        elif idx > 0 and lw in {"d", "l"} and nxt in ("'", "’"):
            new = lw
        else:
            new = lw[:1].upper() + lw[1:]
        out.append(text[last:m.start()])
        out.append(new)
        last = m.end()
    out.append(text[last:])
    return "".join(out)


def fix_case(s: str, strict: bool = False) -> str:
    """Corrige la casse mot par mot : « sarah ben AMOR » -> « Sarah Ben Amor ».
    Les mots en casse mixte (DataPro, iPhone, McDonald) sont conservés ; les mots tout en majuscules de <= 4 lettres
    (ENIT, IBM, SAP) aussi, sauf en mode strict (noms de personnes, villes, pays)."""
    words = clean_spaces(s).split(" ")
    out = []
    for idx, w in enumerate(words):
        letters = [c for c in w if c.isalpha()]
        if not letters:
            out.append(w)
        elif w != w.lower() and w != w.upper():
            out.append(w)  # casse mixte volontaire
        elif w == w.upper() and not strict and len(letters) <= 4 and w.lower() not in PARTICLES:
            out.append(w)  # acronyme court
        else:
            t = smart_title(w)
            if idx > 0 and w.lower() in PARTICLES:
                t = w.lower()
            elif idx > 0 and re.match(r"^[dDlL]['’]", w):
                t = w[0].lower() + t[1:]
            out.append(t)
    return " ".join(out)


def cap_first(s: str) -> str:
    for i, c in enumerate(s):
        if c.isalpha():
            return s[:i] + c.upper() + s[i + 1:]
    return s


def fix_punct(s: str) -> str:
    s = re.sub(r"\s+([,.;!?%)\]])", r"\1", s)
    s = re.sub(r"([,;])(?=[^\s\d])", r"\1 ", s)
    s = re.sub(r"\(\s+", "(", s)
    return clean_spaces(s)


def ensure_period(s: str) -> str:
    return s if not s or s[-1] in ".!?…" else s + "."


def split_lines(text: str, max_lines: int = 10) -> list[str]:
    """Découpe un texte libre en puces propres (sans doublons)."""
    lines: list[str] = []
    for raw in re.split(r"[\n\r;•·▪►]+", str(text or "")):
        raw = re.sub(r"^[\s\-–—•·*▪►>✓✔→]+", "", raw)
        raw = re.sub(r"^\d+[.)]\s+", "", raw)
        raw = clean_spaces(raw)
        if is_junk(raw):
            continue
        parts: list[str] = []
        for piece in re.split(r"(?<=[.!?])\s+", raw):
            if parts and re.search(r"(?:\b(?:etc|ex|vs|env|approx|cf|dr|mme|mr|st)|\b[A-Za-z]|n°)\.$", parts[-1], flags=re.I):
                parts[-1] += " " + piece  # abréviation : pas une fin de phrase
            else:
                parts.append(piece)
        lines.extend(p for p in (clean_spaces(x) for x in parts) if p and not is_junk(p))
    seen, out = set(), []
    for ln in lines:
        ln = ensure_period(cap_first(fix_punct(ln)))
        k = norm(ln)
        if k not in seen:
            seen.add(k)
            out.append(ln)
    return out[:max_lines]


# --------------------------------------------------------------------------- dates
_MONTHS = {"jan": 1, "ene": 1, "gen": 1, "feb": 2, "fev": 2, "mar": 3, "mrz": 3, "apr": 4, "avr": 4, "abr": 4, "mai": 5, "may": 5, "mag": 5,
           "jun": 6, "giu": 6, "jui": 6, "jul": 7, "lug": 7, "aug": 8, "aou": 8, "ago": 8, "sep": 9, "set": 9, "oct": 10, "okt": 10, "ott": 10,
           "nov": 11, "dec": 12, "dez": 12, "dic": 12}
_PRESENT = {"present", "presente", "current", "now", "en cours", "actuel", "actuellement", "aujourd'hui", "aujourdhui", "heute", "oggi", "hoy",
            "ongoing", "a ce jour", "jusqu'a present", "jusqu'a maintenant", "to date", "حتى الآن", "حاليا", "الان"}


def _month_from_word(w: str) -> int | None:
    w = norm(w).rstrip(".")
    if w in ("juin",):
        return 6
    if w in ("juil", "juillet"):
        return 7
    return _MONTHS.get(w[:3]) if w.isalpha() else None


def parse_month(v: str) -> tuple[str | None, bool]:
    """-> (valeur normalisée « YYYY-MM » | « YYYY » | « » si en cours | None si illisible, est_en_cours)."""
    raw = clean_spaces(v)
    n = norm(raw)
    if not n:
        return "", False
    if n in _PRESENT:
        return "", True
    m = re.fullmatch(r"(\d{4})-(\d{1,2})(?:-\d{1,2})?", n)
    if m and 1 <= int(m.group(2)) <= 12:
        return f"{m.group(1)}-{int(m.group(2)):02d}", False
    m = re.fullmatch(r"(\d{1,2})[/.\-](\d{4})", n)
    if m and 1 <= int(m.group(1)) <= 12:
        return f"{m.group(2)}-{int(m.group(1)):02d}", False
    m = re.fullmatch(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})", n)
    if m and 1 <= int(m.group(2)) <= 12:
        return f"{m.group(3)}-{int(m.group(2)):02d}", False
    if re.fullmatch(r"\d{4}", n):
        return n, False
    m = re.fullmatch(r"([a-z.]+)\s+(\d{4})", n) or None
    if m and (mo := _month_from_word(m.group(1))):
        return f"{m.group(2)}-{mo:02d}", False
    m = re.fullmatch(r"(\d{4})\s+([a-z.]+)", n)
    if m and (mo := _month_from_word(m.group(2))):
        return f"{m.group(1)}-{mo:02d}", False
    return None, False


def parse_full_date(v: str) -> str | None:
    n = norm(v)
    if not n:
        return ""
    for pat, order in ((r"(\d{4})-(\d{1,2})-(\d{1,2})", "ymd"), (r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})", "dmy")):
        m = re.fullmatch(pat, n)
        if m:
            g = m.groups()
            y, mo, d = (g[0], g[1], g[2]) if order == "ymd" else (g[2], g[1], g[0])
            try:
                return dt.date(int(y), int(mo), int(d)).isoformat()
            except ValueError:
                return None
    return None


def _key(v: str) -> tuple[int, int]:
    m = re.fullmatch(r"(\d{4})(?:-(\d{2}))?", v or "")
    return (int(m.group(1)), int(m.group(2) or 1)) if m else (0, 0)


# --------------------------------------------------------------------------- compétences
SKILL_DISPLAY = {
    "python": "Python", "sql": "SQL", "mysql": "MySQL", "postgresql": "PostgreSQL", "postgres": "PostgreSQL", "mongodb": "MongoDB", "redis": "Redis",
    "javascript": "JavaScript", "js": "JavaScript", "typescript": "TypeScript", "java": "Java", "php": "PHP", "c#": "C#", "c++": "C++", ".net": ".NET",
    "node": "Node.js", "nodejs": "Node.js", "node.js": "Node.js", "react": "React", "reactjs": "React", "react.js": "React", "vue": "Vue.js", "vuejs": "Vue.js",
    "angular": "Angular", "html": "HTML", "html5": "HTML5", "css": "CSS", "css3": "CSS3", "docker": "Docker", "kubernetes": "Kubernetes", "k8s": "Kubernetes",
    "git": "Git", "github": "GitHub", "gitlab": "GitLab", "aws": "AWS", "azure": "Azure", "gcp": "GCP", "linux": "Linux", "fastapi": "FastAPI",
    "django": "Django", "flask": "Flask", "excel": "Excel", "power bi": "Power BI", "powerbi": "Power BI", "tableau": "Tableau", "terraform": "Terraform",
    "ci/cd": "CI/CD", "cicd": "CI/CD", "ci cd": "CI/CD", "rest api": "REST API", "api rest": "API REST", "api": "API", "apis": "API", "graphql": "GraphQL",
    "machine learning": "Machine Learning", "ml": "Machine Learning", "deep learning": "Deep Learning", "nlp": "NLP", "llm": "LLM", "seo": "SEO",
    "sem": "SEM", "ux": "UX", "ui": "UI", "ux/ui": "UX/UI", "ui/ux": "UI/UX", "figma": "Figma", "photoshop": "Photoshop", "scrum": "Scrum", "agile": "Agile",
    "jira": "Jira", "sap": "SAP", "erp": "ERP", "crm": "CRM", "wordpress": "WordPress", "pandas": "Pandas", "tensorflow": "TensorFlow", "pytorch": "PyTorch",
    "spark": "Spark", "kafka": "Kafka", "airflow": "Airflow", "ansible": "Ansible", "jenkins": "Jenkins", "selenium": "Selenium", "pytest": "Pytest",
}


def skill_display(s: str) -> str:
    s = clean_spaces(s).strip(".,;:")
    k = s.lower()
    if k in SKILL_DISPLAY:
        return SKILL_DISPLAY[k]
    return cap_first(s) if s == s.lower() else s


# --------------------------------------------------------------------------- langues
LANGS = {  # code: (fr, en, de, it, es, ar)
    "fr": ("Français", "French", "Französisch", "Francese", "Francés", "الفرنسية"),
    "en": ("Anglais", "English", "Englisch", "Inglese", "Inglés", "الإنجليزية"),
    "ar": ("Arabe", "Arabic", "Arabisch", "Arabo", "Árabe", "العربية"),
    "de": ("Allemand", "German", "Deutsch", "Tedesco", "Alemán", "الألمانية"),
    "it": ("Italien", "Italian", "Italienisch", "Italiano", "Italiano", "الإيطالية"),
    "es": ("Espagnol", "Spanish", "Spanisch", "Spagnolo", "Español", "الإسبانية"),
    "pt": ("Portugais", "Portuguese", "Portugiesisch", "Portoghese", "Portugués", "البرتغالية"),
    "tr": ("Turc", "Turkish", "Türkisch", "Turco", "Turco", "التركية"),
    "zh": ("Chinois", "Chinese", "Chinesisch", "Cinese", "Chino", "الصينية"),
    "ru": ("Russe", "Russian", "Russisch", "Russo", "Ruso", "الروسية"),
    "nl": ("Néerlandais", "Dutch", "Niederländisch", "Olandese", "Neerlandés", "الهولندية"),
}
_UI = {"fr": 0, "en": 1, "de": 2, "it": 3, "es": 4, "ar": 5}
_EXTRA = {"fr": ["francais", "french", "fr"], "en": ["anglais", "english", "en", "angl"], "ar": ["arabe", "arabic", "ar", "darija", "arabe dialectal"],
          "de": ["allemand", "german", "deutsch", "de"], "it": ["italien", "italian", "italiano", "it"], "es": ["espagnol", "spanish", "espanol", "es"],
          "pt": ["portugais", "portuguese", "portugues", "pt"], "tr": ["turc", "turkish", "turkce", "tr"], "zh": ["chinois", "chinese", "mandarin", "zh"],
          "ru": ["russe", "russian", "ru"], "nl": ["neerlandais", "hollandais", "dutch", "nl"]}
LANG_ALIAS: dict[str, str] = {}
for _c, _names in LANGS.items():
    for _n in list(_names) + _EXTRA[_c]:
        LANG_ALIAS[norm(_n)] = _c


def lang_name(code: str, ui: str) -> str:
    return LANGS[code][_UI.get(ui, 1)]


_CEFR = ["A1", "A2", "B1", "B2", "C1", "C2"]
_LEVEL_WORDS = [  # (mot, niveau) — « MOTHER » = langue maternelle
    ("langue maternelle", "MOTHER"), ("mother tongue", "MOTHER"), ("native", "MOTHER"), ("natif", "MOTHER"), ("maternelle", "MOTHER"), ("bilingue", "MOTHER"),
    ("muttersprache", "MOTHER"), ("madrelingua", "MOTHER"), ("materna", "MOTHER"), ("اللغة الأم", "MOTHER"),
    ("debutant", "A1"), ("beginner", "A1"), ("notions", "A1"), ("basic", "A2"), ("basique", "A2"), ("elementaire", "A2"), ("scolaire", "A2"),
    ("intermediaire", "B1"), ("intermediate", "B1"), ("moyen", "B1"), ("bon", "B2"), ("good", "B2"), ("independant", "B2"), ("upper", "B2"),
    ("courant", "C1"), ("fluent", "C1"), ("avance", "C1"), ("advanced", "C1"), ("tres bon", "C1"),
    ("maitrise", "C2"), ("excellent", "C2"), ("proficient", "C2"), ("expert", "C2"), ("parfait", "C2"),
]


def parse_level(v: str) -> str | None:
    n = norm(v)
    m = re.search(r"\b([abc][12])\b", n)
    if m:
        return m.group(1).upper()
    for word, lvl in _LEVEL_WORDS:
        if word in n:
            return lvl
    return None


def _split_list(v: str) -> list[str]:
    return [x.strip() for x in re.split(r"[,;/&|\n]+|\s+(?:et|and|und|e|y|و)\s+", str(v or "")) if x.strip()]


# --------------------------------------------------------------------------- permis
_LICENCE = {"AM", "A1", "A2", "A", "B1", "B", "BE", "C1", "C1E", "C", "CE", "D1", "D1E", "D", "DE"}
_LICENCE_NOISE = {"permis", "licence", "license", "driving", "category", "categorie", "cat", "de", "conduire", "conduite", "رخصة", "القيادة"}


def clean_licence(v: str) -> tuple[str, bool]:
    n = norm(v)
    if not n or n in JUNK or n in {"non", "no", "nein", "nessuna", "ninguna", "لا"}:
        return "", True
    toks = [t for t in re.split(r"[\s,;/+&]+", n) if t and t not in _LICENCE_NOISE]
    cats = [t.upper() for t in toks if t.upper() in _LICENCE]
    ok = bool(cats) and len(cats) == len(toks)
    return (", ".join(dict.fromkeys(cats)) if cats else clean_spaces(v)), ok


# --------------------------------------------------------------------------- pipeline
class _Rec:
    def __init__(self) -> None:
        self.changes: list[dict] = []
        self.warnings: list[dict] = []

    def fix(self, field: str, before: str, after: str) -> str:
        if str(before).strip() != after and len(str(before)) <= 120 and len(after) <= 120:
            self.changes.append({"field": field, "kind": "fix", "before": str(before).strip(), "after": after})
        return after

    def reformatted(self, field: str, before: str, after: str) -> str:
        if clean_spaces(before) != after and after:
            self.changes.append({"field": field, "kind": "reformatted"})
        return after

    def warn(self, code: str, field: str = "", detail: str = "") -> None:
        self.warnings.append({"code": code, "field": field, "detail": detail})


def _dates(rec: _Rec, f: str, start: str, end: str) -> tuple[str, str]:
    s, s_present = parse_month(start)
    e, e_present = parse_month(end)
    for name, raw, val in (("start", start, s), ("end", end, e)):
        if val is None:
            rec.warn("date_invalid", f"{f}.{name}", clean_spaces(raw))
    s = clean_spaces(start) if s is None else s
    e = clean_spaces(end) if e is None else e
    rec.fix(f"{f}.start", start, s)
    rec.fix(f"{f}.end", end, e)
    if s and e and _key(s) > _key(e) != (0, 0):
        rec.changes.append({"field": f, "kind": "swapped_dates", "before": f"{s} → {e}", "after": f"{e} → {s}"})
        s, e = e, s
    today = dt.date.today()
    if s and _key(s) > (today.year, today.month):
        rec.warn("future_start", f"{f}.start", s)
    return s, e


def process_cv(data: dict, ui_lang: str = "fr") -> tuple[dict, list[dict], list[dict]]:
    rec = _Rec()
    out: dict = dict(data)

    # --- identité & contact
    name = fix_case(data.get("full_name", ""), strict=True)
    if re.search(r"\d", name):
        rec.warn("name_digits", "full_name", name)
    out["full_name"] = rec.fix("full_name", data.get("full_name", ""), name)
    out["email"] = rec.fix("email", data.get("email", ""), clean_spaces(data.get("email", "")).lower())

    phone = re.sub(r"^(?:tel|tél|phone|mob|mobile)\s*[:.]?\s*", "", clean_spaces(data.get("phone", "")), flags=re.I)
    phone = re.sub(r"[^\d+()\s.\-]", "", phone)
    phone = re.sub(r"^00", "+", phone)
    phone = clean_spaces(re.sub(r"[.\-]+", " ", phone))
    digits = re.sub(r"\D", "", phone)
    if phone and not 7 <= len(digits) <= 15:
        rec.warn("phone_invalid", "phone", phone)
    out["phone"] = rec.fix("phone", data.get("phone", ""), phone)

    web = clean_spaces(data.get("website", ""))
    web = re.sub(r"^(?:https?://)?(?:www\.)?", "", web, flags=re.I).rstrip("/")
    if web and not re.search(r"\.[a-z]{2,}", web, flags=re.I):
        rec.warn("website_invalid", "website", web)
    out["website"] = rec.fix("website", data.get("website", ""), web)

    for key in ("city", "country", "nationality"):
        out[key] = rec.fix(key, data.get(key, ""), "" if is_junk(data.get(key, "")) else fix_case(data.get(key, ""), strict=True))

    dob_raw = data.get("date_of_birth", "")
    dob = parse_full_date(dob_raw)
    if dob is None:
        rec.warn("date_invalid", "date_of_birth", clean_spaces(dob_raw))
        dob = clean_spaces(dob_raw)
    elif dob:
        age = (dt.date.today() - dt.date.fromisoformat(dob)).days // 365
        if not 14 <= age <= 90:
            rec.warn("dob_implausible", "date_of_birth", dob)
    out["date_of_birth"] = rec.fix("date_of_birth", dob_raw, dob)

    lic, ok = clean_licence(data.get("driving_licence", ""))
    if lic and not ok:
        rec.warn("licence_unknown", "driving_licence", lic)
    out["driving_licence"] = rec.fix("driving_licence", data.get("driving_licence", ""), lic)

    # --- textes libres
    for key in ("summary", "additional_info"):
        raw = data.get(key, "")
        text = " ".join(split_lines(raw, 8)) if key == "summary" else "\n".join(split_lines(raw, 6))
        if key == "summary" and len(text) > 700:
            cut = text[:700].rsplit(". ", 1)[0]
            text = ensure_period(cut if len(cut) > 200 else text[:700].rsplit(" ", 1)[0])
            rec.warn("summary_truncated", "summary")
        out[key] = rec.reformatted(key, raw, text)

    # --- expériences
    exps, seen = [], set()
    for i, e in enumerate(data.get("experiences", [])):
        f = f"experiences.{i}"
        title, company = fix_case(e.get("title", "")), fix_case(e.get("company", ""))
        if is_junk(title) and is_junk(company):
            continue
        s, en = _dates(rec, f, e.get("start", ""), e.get("end", ""))
        if not s:
            rec.warn("missing_start", f)
        desc = "\n".join(split_lines(e.get("description", "")))
        item = {
            "title": rec.fix(f"{f}.title", e.get("title", ""), "" if is_junk(title) else title),
            "company": rec.fix(f"{f}.company", e.get("company", ""), "" if is_junk(company) else company),
            "city": rec.fix(f"{f}.city", e.get("city", ""), fix_case(e.get("city", ""), strict=True)),
            "country": rec.fix(f"{f}.country", e.get("country", ""), fix_case(e.get("country", ""), strict=True)),
            "start": s, "end": en,
            "description": rec.reformatted(f"{f}.description", e.get("description", ""), desc),
        }
        k = (norm(item["title"]), norm(item["company"]), s)
        if k in seen:
            rec.changes.append({"field": f, "kind": "duplicate_removed"})
            continue
        seen.add(k)
        exps.append(item)
    ordered = sorted(exps, key=lambda x: (0 if x["end"] else 1, _key(x["start"]), _key(x["end"])), reverse=True)
    if [id(x) for x in ordered] != [id(x) for x in exps]:
        rec.changes.append({"field": "experiences", "kind": "sorted"})
    out["experiences"] = ordered

    # --- formations
    edus, seen = [], set()
    for i, e in enumerate(data.get("education", [])):
        f = f"education.{i}"
        degree, school = fix_case(e.get("degree", "")), fix_case(e.get("school", ""))
        if is_junk(degree) and is_junk(school):
            continue
        s, en = _dates(rec, f, e.get("start", ""), e.get("end", ""))
        year = clean_spaces(e.get("year", ""))
        level = re.sub(r"\D", "", str(e.get("level", "")))[:1]
        if level and not "1" <= level <= "8":
            level = ""
        item = {
            "degree": rec.fix(f"{f}.degree", e.get("degree", ""), "" if is_junk(degree) else degree),
            "school": rec.fix(f"{f}.school", e.get("school", ""), "" if is_junk(school) else school),
            "city": rec.fix(f"{f}.city", e.get("city", ""), fix_case(e.get("city", ""), strict=True)),
            "country": rec.fix(f"{f}.country", e.get("country", ""), fix_case(e.get("country", ""), strict=True)),
            "start": s, "end": en, "year": year, "level": level,
        }
        k = (norm(item["degree"]), norm(item["school"]), s, en)
        if k in seen:
            rec.changes.append({"field": f, "kind": "duplicate_removed"})
            continue
        seen.add(k)
        edus.append(item)
    ordered = sorted(edus, key=lambda x: (_key(x["end"] or x["year"] or x["start"]), _key(x["start"])), reverse=True)
    if [id(x) for x in ordered] != [id(x) for x in edus]:
        rec.changes.append({"field": "education", "kind": "sorted"})
    out["education"] = ordered

    # --- compétences
    raw_skills = data.get("skills", [])
    if isinstance(raw_skills, str):
        raw_skills = [raw_skills]
    pieces = [p for s in raw_skills for p in re.split(r"[,;\n•·|]+", str(s))]
    skills, seen = [], set()
    for p in pieces:
        p = clean_spaces(p)
        if is_junk(p) or len(p) > 60:
            continue
        d = skill_display(p)
        if norm(d) not in seen:
            seen.add(norm(d))
            skills.append(d)
    if len(skills) > 40:
        skills = skills[:40]
        rec.warn("skills_truncated", "skills")
    if skills != [clean_spaces(str(s)) for s in raw_skills]:
        rec.changes.append({"field": "skills", "kind": "fix", "before": ", ".join(map(str, raw_skills))[:120], "after": ", ".join(skills)[:120]})
    out["skills"] = skills
    if not skills and not out["experiences"]:
        rec.warn("no_skills", "skills")

    # --- langues
    mother_codes: list[str] = []
    mother_names: list[str] = []
    for part in _split_list(data.get("mother_tongue", "")):
        code = LANG_ALIAS.get(norm(part))
        if code and code not in mother_codes:
            mother_codes.append(code)
        elif not code and norm(part) not in {norm(x) for x in mother_names}:
            mother_names.append(fix_case(part))
    langs: dict[str, dict] = {}
    for i, l in enumerate(data.get("languages", [])):
        raw_name = clean_spaces(l.get("name", ""))
        if is_junk(raw_name):
            continue
        code = LANG_ALIAS.get(norm(raw_name), "")
        lvl = parse_level(l.get("level", "") or "")
        if lvl == "MOTHER":
            if code and code not in mother_codes:
                mother_codes.append(code)
            elif not code:
                mother_names.append(fix_case(raw_name))
            rec.changes.append({"field": f"languages.{i}", "kind": "moved_to_mother"})
            continue
        if lvl is None:
            rec.warn("level_unknown", f"languages.{i}", clean_spaces(l.get("level", "")))
            lvl = "B2"
        item = {"name": lang_name(code, ui_lang) if code else fix_case(raw_name), "code": code, "level": lvl}
        for k in ("listening", "reading", "interaction", "production", "writing"):
            v = parse_level(l.get(k, "") or "")
            item[k] = v if v in _CEFR else ""
        key = code or norm(raw_name)
        if key in langs:  # doublon : on garde le meilleur niveau
            if _CEFR.index(item["level"]) <= _CEFR.index(langs[key]["level"]):
                continue
        langs[key] = item
        rec.fix(f"languages.{i}.name", raw_name, item["name"])
    for c in mother_codes:
        langs.pop(c, None)  # une langue maternelle n'est pas « autre langue »
    out["languages"] = list(langs.values())
    out["mother_tongue_codes"] = mother_codes
    out["mother_tongue"] = ", ".join([lang_name(c, ui_lang) for c in mother_codes] + mother_names)
    if out["mother_tongue"] != clean_spaces(data.get("mother_tongue", "")):
        rec.changes.append({"field": "mother_tongue", "kind": "fix", "before": clean_spaces(data.get("mother_tongue", "")), "after": out["mother_tongue"]})
    return out, rec.changes, rec.warnings
