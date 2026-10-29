import os

from backend import jobsources as js


def fake(url, headers=None, data=None, timeout=0):
    if "adzuna" in url:
        assert "/jobs/fr/" in url and "where=Lyon" in url
        return {"results": [{"title": "Dév <b>Python</b>", "company": {"display_name": "Acme"}, "location": {"display_name": "Lyon"},
                             "description": "API &amp; SQL", "redirect_url": "https://www.adzuna.fr/land/ad/1", "created": "2026-10-01T00:00:00Z"},
                            {"title": "", "redirect_url": "https://x"}, {"title": "Sans lien", "redirect_url": "javascript:x"}]}
    if "arbeitnow" in url:
        return {"data": [{"title": "Python Developer", "company_name": "Foo", "location": "Berlin", "description": "python", "url": "https://arbeitnow.com/j/1", "created_at": 1760000000},
                         {"title": "Cuisinier", "company_name": "Bar", "location": "Berlin", "description": "cuisine", "url": "https://arbeitnow.com/j/2"}]}
    if "remotive" in url:
        return {"jobs": [{"title": "Python dev", "company_name": "R", "candidate_required_location": "Worldwide", "description": "x", "url": "https://remotive.com/j/9"}]}
    raise AssertionError(url)


def test_clean_and_filtering(monkeypatch=None):
    os.environ["ADZUNA_APP_ID"] = "i"; os.environ["ADZUNA_APP_KEY"] = "k"
    jobs, st = js.fetch("python", "FR", "Lyon", get=fake, providers=js.PROVIDERS)
    assert st["adzuna"]["ok"] and st["adzuna"]["count"] == 1          # annonces sans titre / sans http(s) écartées
    assert not st["arbeitnow"]["ok"] and not st["francetravail"]["ok"]  # hors pays / clé manquante : signalé, pas d'exception
    j = jobs[0]
    assert j["title"] == "Dév Python" and j["description"] == "API & SQL" and j["url"].startswith("https://") and j["country"] == "FR"


def test_arbeitnow_local_filter_and_dedupe():
    os.environ.pop("ADZUNA_APP_ID", None)
    jobs, st = js.fetch("python", "DE", "", get=fake, providers={"arbeitnow": js.arbeitnow, "remotive": js.remotive})
    titles = [j["title"] for j in jobs]
    assert "Cuisinier" not in titles and titles.count("Python Developer") == 1 and "Python dev" in titles
    assert st["arbeitnow"]["ok"] and st["remotive"]["ok"]


def test_failing_provider_does_not_break_others():
    def boom(url, **k):
        if "remotive" in url:
            raise OSError("réseau coupé")
        return fake(url)
    jobs, st = js.fetch("python", "DE", "", get=boom, providers={"arbeitnow": js.arbeitnow, "remotive": js.remotive})
    assert st["remotive"]["ok"] is False and "réseau" in st["remotive"]["reason"] and jobs
