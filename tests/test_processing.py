"""pytest -q depuis la racine du projet (modules purs, sans dépendance externe)."""
from datetime import date

from backend import processing as P

TODAY = date(2026, 10, 18)
RAW = {
    "full_name": "  sarah   ben amor ", "email": " Sarah@Example.COM ", "phone": "20 123 456", "website": "https://LinkedIn.com/in/sarah/", "city": "TUNIS",
    "country": "tunisia", "date_of_birth": "12/04/1996", "driving_licence": "permis B", "mother_tongue": "arabe",
    "skills": ["python , django; SQL", "PYTHON", "<b>fastapi</b>"],
    "experiences": [
        {"title": "développeuse python", "company": "ATLAS TECH", "start": "mars 2021", "end": "en cours", "description": "conception d'API REST; tests automatisés"},
        {"title": "stagiaire", "company": "datapro", "start": "08/2020", "end": "février 2020", "description": "<script>x()</script>scripts pandas"}],
    "education": [{"degree": "master informatique", "school": "enit", "start": "2019-06", "end": "2017-09", "level": "7"}],
    "languages": [{"name": "francais (courant)", "level": "B2"}, {"name": "arabe (langue maternelle)", "level": "B2"}, {"name": "Deutsch A2", "level": "B2"}],
}


def test_core_normalization():
    d, _ = P.process_cv(RAW, TODAY)
    assert d["full_name"] == "Sarah Ben Amor" and d["email"] == "sarah@example.com"
    assert d["phone"] == "+216 20 12 34 56" and d["website"] == "linkedin.com/in/sarah"
    assert d["city"] == "Tunis" and d["country"] == "Tunisia" and d["date_of_birth"] == "1996-04-12" and d["driving_licence"] == "B"
    assert d["skills"] == ["Python", "Django", "SQL", "FastAPI"]


def test_dates_sorting_and_swap():
    d, ch = P.process_cv(RAW, TODAY)
    assert [e["title"] for e in d["experiences"]] == ["Développeuse Python", "Stagiaire"]  # plus récent d'abord
    assert (d["experiences"][1]["start"], d["experiences"][1]["end"]) == ("2020-02", "2020-08")  # dates inversées corrigées
    assert d["experiences"][0]["end"] == "" and (d["education"][0]["start"], d["education"][0]["end"]) == ("2017-09", "2019-06")
    assert any(c["field"] == "dates" for c in ch)


def test_html_removed_and_bullets():
    d, _ = P.process_cv(RAW, TODAY)
    assert d["experiences"][1]["description"] == "Scripts pandas"  # <script> supprimé avec son contenu
    assert d["experiences"][0]["description"] == "• Conception d'API REST\n• Tests automatisés"


def test_languages_and_mother_tongue():
    d, _ = P.process_cv(RAW, TODAY)
    assert d["mother_tongue"] == "Arabic" and [(l["name"], l["level"]) for l in d["languages"]] == [("French", "C1"), ("German", "A2")]
    eu = P.to_europass(d, "de", TODAY)
    assert eu["mother_tongue"] == ["Arabisch"] and eu["language_skills"][0]["name"] == "Französisch" and eu["personal"]["address"] == "Tunis, Tunesien"


def test_idempotent():
    d, _ = P.process_cv(RAW, TODAY)
    d2, ch2 = P.process_cv(d, TODAY)
    assert d2 == d and ch2 == []


def test_no_invention():
    d, _ = P.process_cv({"full_name": "A B", "email": "a@b.co"}, TODAY)
    eu = P.to_europass(d, "fr", TODAY)
    assert eu["summary"] == "" and eu["work_experience"] == [] and eu["digital_skills"] == []  # rien n'est inventé
    d, _ = P.process_cv({"full_name": "A B", "email": "a@b.co", "skills": ["python"], "experiences": [{"title": "dev", "start": "2020-01"}]}, TODAY)
    s = P.auto_summary(d, "fr", TODAY)
    assert "6 ans" in s and "Python" in s  # uniquement des faits fournis (années calculées depuis les dates)


def test_phone_and_dates():
    assert P.phone_clean("06 12 34 56 78", "FR") == "+33 6 12 34 56 78" and P.phone_clean("+33 (0)6 12 34 56 78") == "+33 6 12 34 56 78"
    assert P.phone_clean("123") == "123"  # douteux : conservé, non « inventé »
    assert P.parse_date("Sept. 2019") == ("2019-09", "ok") and P.parse_date("Heute") == ("", "present") and P.parse_date("xyz")[1] == "invalid"


def test_llm_refine_is_off_by_default():
    eu = {"summary": "x", "work_experience": []}
    assert P.maybe_refine(eu, "fr")["summary"] == eu["summary"]


def test_multiple_positions_same_employer():
    raw = {"full_name": "A B", "email": "a@b.co", "experiences": [
        {"title": "développeur junior", "company": "Atlas Tech", "start": "2018-01", "end": "2020-12"},
        {"title": "développeur senior", "company": "atlas tech", "start": "2021-01", "end": "2023-06"},
        {"title": "chef d'équipe", "company": "Atlas Tech", "start": "2023-07", "end": ""},
        {"title": "Chef d'équipe", "company": "Atlas Tech", "start": "2023-07", "end": ""}]}  # doublon exact
    d, _ = P.process_cv(raw, TODAY)
    assert [e["title"] for e in d["experiences"]] == ["Chef d'équipe", "Développeur senior", "Développeur junior"]  # 3 postes, récent d'abord
    assert {e["company"] for e in d["experiences"]} == {"Atlas Tech"}
    assert P.years_of_experience(d["experiences"], TODAY) == 8  # 2018-01 -> 2026-10, périodes contiguës non comptées deux fois


def test_school_uppercase():
    d, _ = P.process_cv({"education": [{"degree": "licence info", "school": "école nationale d'ingénieurs de tunis", "end": "2020"}]})
    assert d["education"][0]["school"] == "ÉCOLE NATIONALE D'INGÉNIEURS DE TUNIS"


def _eu():
    return {"summary": "Dev python.", "work_experience": [{"title": "Développeur", "company": "Acme", "description": "• fait des api 2020"}]}


def test_ai_refine_ok_and_guards(monkeypatch=None):
    import json as _j
    good = _j.dumps({"summary": "Développeur Python orienté API.", "experiences": ["Concevoir des API\nAssurer la maintenance"]})
    r = P.maybe_refine(_eu(), "fr", llm_call=lambda s, h: good)
    assert r["_ai"] == "ok" and r["work_experience"][0]["description"] == "• Concevoir des API\n• Assurer la maintenance"
    bad = _j.dumps({"summary": "Dev avec 12 ans d'expérience", "experiences": ["x"]})  # chiffre inventé -> rejet
    r = P.maybe_refine(_eu(), "fr", llm_call=lambda s, h: bad)
    assert r["_ai"] == "failed" and r["summary"] == "Dev python."
    r = P.maybe_refine(_eu(), "fr", llm_call=lambda s, h: "pas du json")
    assert r["_ai"] == "failed"


def test_ai_off_without_key():
    import os
    os.environ.pop("ANTHROPIC_API_KEY", None)
    assert P.maybe_refine(_eu(), "fr")["_ai"] == "off"


def test_job_links():
    from backend import joblinks, seed_data
    urls = [j["url"] for j in seed_data.SEED_JOBS]
    assert len(urls) == len(set(urls)) >= 60
    links = joblinks.for_job({**seed_data.SEED_JOBS[0], "source": "seed"})
    assert [l["name"] for l in links][:2] == ["LinkedIn", "Indeed"] and all(l["url"].startswith("https://") for l in links)
    real = joblinks.for_job({"title": "Dev", "city": "Lyon", "country": "FR", "url": "https://emp.example/1", "source": "n8n"})
    assert real[0] == {"name": "Offre d'origine", "url": "https://emp.example/1"}
    evil = joblinks.for_job({"title": "Dev", "city": "Lyon", "country": "FR", "url": "javascript:alert(1)", "source": "n8n"})
    assert all(l["url"].startswith("https://") for l in evil)


def test_jobs_with_and_without_email():
    from backend import seed_data
    jobs = seed_data.SEED_JOBS
    assert len(jobs) >= 150 and len({j["url"] for j in jobs}) == len(jobs)
    assert any(j["email"] for j in jobs) and sum(1 for j in jobs if not j["email"]) > len(jobs) // 2
