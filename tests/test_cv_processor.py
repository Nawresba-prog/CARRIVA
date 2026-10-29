"""Tests du traitement des données (sans dépendances externes) : pytest -q"""
import datetime as dt

from backend.cv_processor import fix_case, parse_full_date, parse_month, process_cv, skill_display, split_lines

RAW = {
    "full_name": "  sarah   ben AMOR ", "email": " Sarah.BenAmor@Example.COM ", "phone": "Tél: 00216.20-123-456", "website": "https://www.linkedin.com/in/sarah/",
    "city": "tunis", "country": "TUNISIE", "nationality": "tunisienne", "date_of_birth": "12/04/1996", "driving_licence": "Permis B",
    "summary": "ingénieure logiciel avec 4 ans d'expérience , spécialisée en API python.  passionnée par l'automatisation",
    "mother_tongue": "arabe", "additional_info": "- bénévole dans une association\n- bénévole dans une association",
    "experiences": [
        {"title": "stagiaire développement", "company": "DATAPRO", "city": "sfax", "country": "", "start": "février 2020", "end": "août 2020",
         "description": "- scripts d'analyse de données avec pandas ; rapports hebdomadaires"},
        {"title": "DÉVELOPPEUSE PYTHON", "company": "Atlas Tech", "city": "", "country": "", "start": "03/2021", "end": "en cours",
         "description": "Conception d'API REST avec FastAPI. mise en place de CI/CD ; Conception d'API REST avec FastAPI."},
        {"title": "n/a", "company": "-", "start": "", "end": "", "description": ""},
    ],
    "education": [{"degree": "diplôme d'ingénieur", "school": "enit", "start": "2019", "end": "2016", "level": "niveau 7", "year": ""}],
    "skills": ["python, SQL; docker", "PYTHON", "ci/cd", "k8s", "n/a"],
    "languages": [{"name": "anglais", "level": "courant"}, {"name": "Français", "level": "c1"}, {"name": "francais", "level": "B1"},
                  {"name": "arabe", "level": "langue maternelle"}, {"name": "Klingon", "level": "???"}],
}


def test_identity_and_contact_are_cleaned():
    out, changes, _ = process_cv(RAW)
    assert out["full_name"] == "Sarah Ben Amor"
    assert out["email"] == "sarah.benamor@example.com"
    assert out["phone"] == "+216 20 123 456"
    assert out["website"] == "linkedin.com/in/sarah"
    assert (out["city"], out["country"], out["nationality"]) == ("Tunis", "Tunisie", "Tunisienne")
    assert out["date_of_birth"] == "1996-04-12" and out["driving_licence"] == "B"
    assert any(c["field"] == "full_name" for c in changes)


def test_dates_are_normalised_and_experiences_sorted():
    out, _, _ = process_cv(RAW)
    assert [e["title"] for e in out["experiences"]] == ["Développeuse Python", "Stagiaire Développement"]  # en cours d'abord, déchets supprimés
    assert out["experiences"][0]["start"] == "2021-03" and out["experiences"][0]["end"] == ""
    assert out["experiences"][1]["start"] == "2020-02" and out["experiences"][1]["end"] == "2020-08"
    assert out["experiences"][1]["company"] == "Datapro"


def test_swapped_dates_education_and_level():
    out, changes, _ = process_cv(RAW)
    e = out["education"][0]
    assert (e["start"], e["end"], e["level"], e["school"]) == ("2016", "2019", "7", "Enit")
    assert any(c["kind"] == "swapped_dates" for c in changes)


def test_descriptions_become_clean_bullets():
    out, _, _ = process_cv(RAW)
    assert out["experiences"][0]["description"].split("\n") == ["Conception d'API REST avec FastAPI.", "Mise en place de CI/CD."]
    assert out["experiences"][1]["description"].split("\n") == ["Scripts d'analyse de données avec pandas.", "Rapports hebdomadaires."]
    assert out["summary"].startswith("Ingénieure logiciel avec 4 ans d'expérience, spécialisée")
    assert out["additional_info"] == "Bénévole dans une association."


def test_skills_split_dedup_canonical():
    out, _, _ = process_cv(RAW)
    assert out["skills"] == ["Python", "SQL", "Docker", "CI/CD", "Kubernetes"]


def test_languages_codes_levels_mother_tongue():
    out, _, warnings = process_cv(RAW, ui_lang="fr")
    by = {l["name"]: l for l in out["languages"]}
    assert by["Anglais"]["level"] == "C1" and by["Français"]["level"] == "C1"  # doublon : meilleur niveau
    assert out["mother_tongue_codes"] == ["ar"] and out["mother_tongue"] == "Arabe"
    assert "Arabe" not in by and by["Klingon"]["level"] == "B2"
    assert any(w["code"] == "level_unknown" for w in warnings)
    en, _, _ = process_cv(RAW, ui_lang="en")
    assert en["mother_tongue"] == "Arabic" and {l["name"] for l in en["languages"]} >= {"English", "French"}


def test_idempotent():
    once, _, _ = process_cv(RAW)
    twice, changes2, _ = process_cv(once)
    assert once == twice
    assert not [c for c in changes2 if c["kind"] in ("fix", "swapped_dates", "sorted")]


def test_helpers():
    assert fix_case("DataPro") == "DataPro" and fix_case("ENIT") == "ENIT" and fix_case("sarah ben AMOR", strict=True) == "Sarah Ben Amor" and fix_case("jean-pierre d'alembert") == "Jean-Pierre d'Alembert"
    assert fix_case("ingénieur it") == "Ingénieur IT"
    assert parse_month("mars 2021") == ("2021-03", False) and parse_month("Present") == ("", True) and parse_month("blabla") == (None, False)
    assert parse_full_date("31/02/2000") is None
    assert skill_display("power bi") == "Power BI" and skill_display("gestion de projet") == "Gestion de projet"
    assert split_lines("a b c") == ["A b c."]
    assert split_lines("Gestion des stocks, factures, etc. et reporting. suivi des KPI") == ["Gestion des stocks, factures, etc. et reporting.", "Suivi des KPI."]


def test_warnings():
    bad = {"full_name": "Bob2", "email": "b@x.io", "phone": "12", "website": "nodomain", "date_of_birth": "01/01/2020", "driving_licence": "xyz",
           "experiences": [{"title": "Dev", "company": "X", "start": "dans longtemps", "end": ""}], "skills": [], "languages": []}
    _, _, w = process_cv(bad)
    codes = {x["code"] for x in w}
    assert {"name_digits", "phone_invalid", "website_invalid", "dob_implausible", "licence_unknown", "date_invalid"} <= codes
    _, _, w3 = process_cv({"full_name": "A B", "email": "a@b.co", "experiences": [{"title": "Dev", "company": "X", "start": ""}]})
    assert any(x["code"] == "missing_start" for x in w3)
    future = dt.date.today().year + 2
    _, _, w2 = process_cv({"full_name": "A B", "email": "a@b.co", "experiences": [{"title": "Dev", "start": f"{future}-01"}]})
    assert any(x["code"] == "future_start" for x in w2)
