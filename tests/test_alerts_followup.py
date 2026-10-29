"""Logique des routes n8n /internal/matching/run et /internal/followup/propose (modules purs, sans FastAPI ni Qdrant)."""
from datetime import datetime, timedelta, timezone

from backend import alerts, followup, matching
from backend.seed_data import SEED_JOBS

NOW = datetime(2026, 10, 23, 9, 0, tzinfo=timezone.utc)


def search(q, country, city):
    return [j for j in SEED_JOBS if (not country or j["country"] == country) and (not city or j["city"] == city)]


def mk(**kw):
    skills, titles = matching.extract_skills("python, sql, docker, fastapi, git, rest api", "Développeur Python"), "Développeur Python"
    d = dict(user="u1", cv_skills=skills, titles=titles, country="FR", city=None, min_score=0.6, lang="fr", email="a@b.fr")
    d.update(kw)
    return alerts.make_alert(**d)


def test_matching_returns_only_jobs_above_threshold_and_sorted():
    a = mk(); res = alerts.run_matching({"u1": a}, search)
    assert res and all(r["score"] >= 0.6 and r["country"] == "FR" and r["user"] == "u1" and r["email"] == "a@b.fr" for r in res)
    assert [r["score"] for r in res] == sorted((r["score"] for r in res), reverse=True)
    assert "Développeur Python" in res[0]["title"] and "%" in res[0]["message"]
    assert len(res) <= 5 and all(isinstance(r["missing"], list) for r in res)


def test_never_notifies_the_same_offer_twice():
    a = mk(); first = alerts.run_matching({"u1": a}, search); second = alerts.run_matching({"u1": a}, search, max_per_user=20)
    assert first and not ({r["url"] for r in first} & {r["url"] for r in second})
    assert a["last_run"] and len(a["notified"]) >= len(first)


def test_dry_run_changes_nothing():
    a = mk(); r1 = alerts.run_matching({"u1": a}, search, dry_run=True); r2 = alerts.run_matching({"u1": a}, search, dry_run=True)
    assert r1 == r2 and a["notified"] == [] and a["last_run"] is None


def test_threshold_and_country_are_respected():
    strict = alerts.run_matching({"u": mk(min_score=0.99)}, search)
    assert all(r["score"] >= 0.99 for r in strict) and len(strict) <= len(alerts.run_matching({"u": mk()}, search, max_per_user=20))
    assert alerts.run_matching({"u": mk(country="JP")}, search) == []


def test_each_user_gets_own_lines_and_empty_profile_is_safe():
    res = alerts.run_matching({"u1": mk(), "u2": mk(user="u2", email="c@d.fr", cv_skills=["excel"], titles="Comptable")}, search)
    assert {r["user"] for r in res} <= {"u1", "u2"} and "u1" in {r["user"] for r in res}
    assert alerts.run_matching({}, search) == []


def test_public_view_hides_email_and_notified_urls():
    v = alerts.public_view(mk()); assert "email" not in v and "notified" not in v and v["notified_count"] == 0


def sent(**kw):
    a = {"status": "sent", "draft": {"to": "rh@acme.fr", "subject": "Candidature : Développeur Python", "lang": "fr", "channel": "email"},
         "sent_at": NOW - timedelta(days=7)}
    a.update(kw); return a


def test_eligibility_rules():
    assert followup.eligibility(sent(), None, NOW)[:2] == (True, "ok")
    assert followup.eligibility(sent(status="pending"), None, NOW)[1] == "not_sent"
    assert followup.eligibility(sent(status="ready"), None, NOW)[1] == "not_sent"
    assert followup.eligibility(sent(kind="followup"), None, NOW)[1] == "not_sent"
    for st in ("reply", "rejected", "withdrawn"):
        assert followup.eligibility(sent(tracking=st), None, NOW)[1] == "reply_received"
    assert followup.eligibility(sent(tracking="opened"), None, NOW)[0] is True
    assert followup.eligibility(sent(), {"status": "pending"}, NOW)[1] == "already_proposed"
    assert followup.eligibility(sent(), {"status": "rejected"}, NOW)[1] == "already_proposed"
    assert followup.eligibility(sent(), {"status": "expired"}, NOW)[0] is True
    ok, why, due = followup.eligibility(sent(sent_at=NOW - timedelta(days=1)), None, NOW)
    assert (ok, why) == (False, "too_early") and due > NOW
    d = sent(); d["draft"]["channel"] = "link"; assert followup.eligibility(d, None, NOW)[1] == "no_email"


def test_draft_is_faithful_localized_and_has_no_attachment_flag():
    job = {"title": "Développeur Python", "company": "Acme"}
    for lang in followup.TEMPLATES:
        d = followup.build_draft("p1", {"to": "rh@acme.fr", "subject": "S", "lang": lang}, job, "Sara Haddad", NOW)
        assert d["kind"] == "followup" and d["parent"] == "p1" and d["to"] == "rh@acme.fr" and d["channel"] == "email" and d["lang"] == lang
        assert "Acme" in d["body"] and "Développeur Python" in d["body"] and "Sara Haddad" in d["body"] and "{" not in d["body"]
    fr = followup.build_draft("p", {"to": "x@y.fr", "subject": "Candidature : X", "lang": "fr"}, job, "S", NOW)
    en = followup.build_draft("p", {"to": "x@y.fr", "subject": "Re: Application", "lang": "en"}, job, "S", NOW)
    assert fr["subject"] == "Re: Candidature : X" and "23/10/2026" in fr["body"]
    assert en["subject"] == "Re: Application" and "2026-10-23" in en["body"]
    assert followup.build_draft("p", {"to": "x@y.fr", "subject": "S", "lang": "zz"}, job, "S", NOW)["lang"] == "en"
