from backend import linkedin as L

WEAK = {"headline": "Chercheur d'emploi", "about": "Je cherche un poste.", "experiences": [{"title": "Développeur Python", "company": "Acme", "description": "Dev"}],
        "skills": ["Python"], "target_role": "Développeur Python FastAPI Docker", "target_text": "", "checks": {}, "recommendations": 0}
STRONG = {"headline": "Développeur Python | FastAPI · Docker · PostgreSQL - API performantes pour la fintech et le e-commerce",
          "about": ("Développeur Python spécialisé en API FastAPI et Docker : j'ai réduit de 40 % le temps de réponse d'une plateforme à 2 millions d'utilisateurs. "
                    + "Je conçois des services fiables avec PostgreSQL, CI/CD et tests automatisés, en équipe de 8 personnes. " * 6
                    + "J'ai livré 12 projets, économisé 15 % de coûts cloud et formé 5 juniors. Contactez-moi : jean@example.com pour échanger sur vos projets."),
          "experiences": [{"title": "Développeur Python", "company": "Acme", "description": "- Conçu 25 API REST avec FastAPI et PostgreSQL, 99,9 % de disponibilité\n" * 3 + "- Docker et CI/CD : déploiements 3x plus rapides, équipe de 6"}],
          "skills": ["Python", "FastAPI", "Docker", "PostgreSQL", "SQL", "Git", "CI/CD", "Linux", "AWS", "Redis", "Scrum", "Kubernetes", "REST", "Pytest", "Terraform", "Agile"],
          "target_role": "Développeur Python FastAPI Docker", "checks": {k: True for k in ("photo", "banner", "custom_url", "location", "featured")}, "recommendations": 3}


def test_score_bounds_and_order():
    w, s = L.audit(WEAK), L.audit(STRONG)
    assert 0 <= w["score"] < s["score"] <= 100, (w["score"], s["score"])
    assert w["band"] == "red" and s["band"] in ("green", "yellow")
    assert sum(v["score"] for v in s["sections"].values()) == s["score"]
    for k, v in s["sections"].items(): assert 0 <= v["score"] <= v["max"], k


def test_findings_sorted_and_actionable():
    f = L.audit(WEAK)["findings"]
    assert f and [x["sev"] for x in f] == sorted((x["sev"] for x in f), key={"high": 0, "med": 1, "low": 2}.get)
    ids = {x["id"] for x in f}
    assert {"hl_nokw", "pf_photo", "pf_reco"} <= ids, ids
    assert all(x["gain"] >= 0 and x["section"] in L.MAX for x in f)


def test_missing_keywords_only_those_absent():
    kw = L.audit(WEAK)["keywords"]
    assert "Python" in " ".join(kw["have"]) and kw["missing"], kw
    assert not any("Python" == m for m in kw["missing"])
    assert L.audit(STRONG)["keywords"]["missing"] == []


def test_empty_profile_does_not_crash():
    a = L.audit({})
    assert a["score"] <= 5 and any(x["id"] == "hl_missing" for x in a["findings"])


def test_plan_has_four_weeks_and_routines():
    pl = L.audit(WEAK)["plan"]
    assert {t["week"] for t in pl} >= {0, 1, 3, 4}
    assert sum(1 for t in pl if t["kind"] == "routine") == 3
    assert len({t["id"] for t in pl}) == len(pl)


def test_headline_options_use_only_given_facts():
    opts = L.headline_options({**WEAK, "value": "API fiables"})
    assert opts and all(len(o) <= L.LIMITS["headline"] for o in opts)
    assert all("Kubernetes" not in o for o in opts)


def test_prompt_forbids_invention_in_every_language():
    for lang in ("fr", "en", "de", "es", "it", "ar"):
        pr = L.ai_prompt(WEAK, lang, ["Docker"])
        assert "Docker" in pr and "Acme" in pr and len(pr) > 400


def test_boost_with_injected_post_and_without_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    import os; os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        L.boost(WEAK, "fr", []); assert False
    except RuntimeError as e:
        assert str(e) == "no_key"
    seen = []
    out = L.boost(WEAK, "en", ["Docker"], post=lambda p: seen.append(p) or "## ok")
    assert out == "## ok" and "Docker" in seen[0] and "English" in seen[0]
