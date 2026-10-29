import io
import zipfile

from backend import cv_import as C

FR = """SARA HADDAD
Développeuse Full Stack
sara.haddad@example.com | +33 6 12 34 56 78 | Lyon
linkedin.com/in/sara-haddad

PROFIL
Développeuse passionnée par les API et le cloud.

EXPÉRIENCE PROFESSIONNELLE
Développeuse Python - Acme SAS
03/2021 - Présent
- Conception d'API REST avec FastAPI et PostgreSQL
- Mise en place de CI/CD avec Docker et GitLab
Stagiaire développeur, Nova Labs
juin 2019 - sept. 2019
• Tests unitaires et revue de code

FORMATION
Master Informatique - Université Claude Bernard Lyon 1
2017 - 2019
Licence Informatique, Université de Tunis
2014 - 2017

COMPÉTENCES
Python, SQL, Docker, Git, Gestion de projet, Scrum

LANGUES
Français : C2 (langue maternelle), Anglais : B2, Allemand (notions)
"""
EN = """John Smith
john.smith@mail.com  +44 7700 900123
WORK EXPERIENCE
2020 - 2023
Marketing Manager
Globex Ltd
- Led SEO and digital marketing campaigns
EDUCATION
BSc Business, University of Leeds, 2016 - 2019
SKILLS
SEO, Excel, Communication
LANGUAGES
English (native), French (B1)
"""


def test_french_cv():
    r = C.parse_cv(FR); cv = r["cv"]
    assert (cv["full_name"], cv["email"], cv["phone"]) == ("Sara Haddad", "sara.haddad@example.com", "+33 6 12 34 56 78")
    assert [(e["title"], e["company"], e["start"], e["end"]) for e in cv["experiences"]] == [("Développeuse Python", "Acme SAS", "2021-03", ""), ("Stagiaire développeur", "Nova Labs", "2019-06", "2019-09")]
    assert "FastAPI" in cv["experiences"][0]["description"] and "Tests unitaires" in cv["experiences"][1]["description"]
    assert [(e["degree"], e["school"], e["start"][:4], e["end"][:4]) for e in cv["education"]] == [("Master Informatique", "Université Claude Bernard Lyon 1", "2017", "2019"), ("Licence Informatique", "Université de Tunis", "2014", "2017")]
    assert {"Python", "SQL", "Docker", "Git", "Scrum", "FastAPI"} <= set(cv["skills"]) and len([s for s in cv["skills"] if "projet" in s.lower() or "project" in s.lower()]) == 1
    assert [(l["name"], l["level"]) for l in cv["languages"]] == [("Français", "C2"), ("Anglais", "B2"), ("Allemand", "A1")] and cv["mother_tongue"] == "Français"
    assert r["warnings"] == [] and r["found"]["experiences"] == 2


def test_english_cv_dates_above_title():
    cv = C.parse_cv(EN)["cv"]
    assert cv["experiences"][0]["title"] == "Marketing Manager" and cv["experiences"][0]["company"] == "Globex Ltd" and cv["experiences"][0]["start"] == "2020-01"
    assert cv["education"][0]["degree"] == "BSc Business" and cv["education"][0]["school"] == "University of Leeds"
    assert cv["mother_tongue"] == "Anglais" and {"SEO", "Excel"} <= set(cv["skills"])


def test_warnings_on_poor_input():
    r = C.parse_cv("Texte sans structure particulière.\nRien d'utile ici.")
    assert set(r["warnings"]) >= {"name", "email", "experience"}


def test_formats():
    r = C.import_cv(FR.encode("utf-8"), "cv.txt"); assert r["format"] == "txt" and r["cv"]["email"]
    r = C.import_cv(FR.encode("utf-16"), "cv.txt"); assert r["format"] == "txt" and r["cv"]["full_name"] == "Sara Haddad"
    body = "".join(f"<w:p><w:r><w:t xml:space=\"preserve\">{l.replace('&', '&amp;')}</w:t></w:r></w:p>" for l in FR.split("\n"))
    doc = f'<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", doc)
    r = C.import_cv(buf.getvalue(), "cv.docx"); assert r["format"] == "docx" and r["found"]["experiences"] == 2 and r["cv"]["full_name"] == "Sara Haddad"
    from reportlab.pdfgen import canvas
    pb = io.BytesIO(); c = canvas.Canvas(pb); y = 800
    for l in FR.split("\n"):
        c.drawString(40, y, l.encode("latin-1", "replace").decode("latin-1")); y -= 13
    c.save()
    r = C.import_cv(pb.getvalue(), "cv.pdf"); assert r["format"] == "pdf" and r["cv"]["email"] == "sara.haddad@example.com" and r["found"]["experiences"] == 2, r["found"]


def test_errors():
    from reportlab.pdfgen import canvas
    pb = io.BytesIO(); c = canvas.Canvas(pb); c.rect(10, 10, 50, 50); c.save()           # PDF sans texte (scan)
    for data, key in ((pb.getvalue(), "scan"), (b"\xd0\xcf\x11\xe0" + b"0" * 50, ".doc"), (b"PK\x03\x04junk", "Format"), (b"\x00\x01\x02" * 40, "Format"), (b"x" * (C.MAX_BYTES + 1), "volumineux")):
        try:
            C.import_cv(data, "x"); assert False, key
        except C.ImportError_ as e:
            assert key.lower() in str(e).lower(), (key, str(e))


def test_unrecognised_content_is_an_error():
    try:
        C.import_cv(b"\x00\x01" * 100, "x.bin"); assert False
    except C.ImportError_ as e:
        assert "reconnue" in str(e) or "Format" in str(e)
