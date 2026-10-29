"""pytest -q : agent d'envoi (réseau, IA et envoi simulés ; aucun accès internet)."""
import json

from backend import outreach as O

DDG = '''<div class="result"><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.acme-tech.fr%2F&rut=x">Acme Tech - Logiciels</a>
<a class="result__snippet" href="x">Éditeur de logiciels à Lyon</a></div>
<div class="result"><a class="result__a" href="https://www.linkedin.com/company/x">LinkedIn</a></div>
<div class="result"><a class="result__a" href="https://beta-soft.fr/">Beta Soft</a></div>'''

PAGES = {
    "https://acme-tech.fr/": '<title>Acme Tech</title><body>Logiciels et développement web. <a href="/contact">Contact</a> <a href="mailto:RH@acme-tech.fr?subject=x">rh</a></body>',
    "https://acme-tech.fr/contact": "<p>Écrivez-nous : contact@acme-tech.fr ou noreply@acme-tech.fr, logo@2x.png</p>",
    "https://beta-soft.fr/": "<title>Beta Soft</title>Agence de communication. Pas d'email ici.",
}


def fetch(u):
    return PAGES.get(u.replace("www.", ""), "")


def test_parse_ddg_and_real_url():
    r = O.parse_ddg(DDG)
    assert r[0]["url"] == "https://www.acme-tech.fr/" and r[0]["snippet"].startswith("Éditeur") and len(r) == 3


def test_scrape_emails_ranked_and_filtered():
    s = O.scrape("https://acme-tech.fr/", fetch)
    assert s["emails"][0] == "rh@acme-tech.fr" and "contact@acme-tech.fr" in s["emails"]
    assert all("noreply" not in e and not e.endswith(".png") for e in s["emails"])


def test_ssrf_blocked():
    for u in ("http://127.0.0.1/", "http://localhost:8000/", "http://169.254.169.254/latest/meta-data", "http://10.0.0.5/", "file:///etc/passwd", "ftp://x.com"):
        assert not O.is_public_url(u), u


def make(tmp_path, llm=None, sent=None):
    sent = sent if sent is not None else []
    a = O.Agent(tmp_path / "o.json", search=lambda q, n: O.parse_ddg(DDG), fetch=fetch, llm=llm, send=lambda d, cv: sent.append(d),
                sleep=lambda s: None, env={"MAX_EMAILS_PER_RUN": "2", "OUTREACH_DAILY_CAP": "3", "EMAIL_MIN_DELAY_SECONDS": "0", "EMAIL_MAX_DELAY_SECONDS": "0"})
    return a, sent


P = {"sector": "logiciels", "role": "Développeur Python", "country": "FR", "city": "Lyon", "target_count": 5, "profile": "Développeur Python, 5 ans", "sender": "Sarah Ben Amor", "intro": "Développeur Python."}


def test_search_draft_send_flow(tmp_path):
    a, sent = make(tmp_path)
    a.run_search(P)
    assert a.job["error"] is None and a.job["found"] == 1  # Beta Soft ne correspond pas au secteur ; LinkedIn exclu
    l = a.leads[0]
    assert l["status"] == "drafted" and l["lang"] == "fr" and "Développeur Python" in l["email_subject"] and "Sarah Ben Amor" in l["email_body"]
    a.cv = {"full_name": "S"}
    a.send_one(l["id"])
    assert sent[0]["to"] == "rh@acme-tech.fr" and "STOP" in sent[0]["body"] and "\n" not in sent[0]["subject"]
    try:
        a.send_one(l["id"]); assert False
    except ValueError:
        pass


def test_optout_dedupe_caps_and_batch(tmp_path):
    a, sent = make(tmp_path)
    mk = lambda i, mail: {"id": i, "url": f"https://x{i}.com", "company_name": f"C{i}", "contact_email": mail, "status": "drafted", "email_subject": "s", "email_body": "b", "lang": "en"}
    a.leads = [mk("1", "a@x1.com"), mk("2", "a@x1.com"), mk("3", "b@x3.com"), mk("4", "c@x4.com"), mk("5", "d@x5.com")]
    a.add_optout("b@x3.com")
    assert a.start_batch(["1", "2", "3", "4", "5"]) == 2  # MAX_EMAILS_PER_RUN = 2
    import time
    for _ in range(100):
        if not a.batch["running"]:
            break
        time.sleep(0.02)
    assert [d["to"] for d in sent] == ["a@x1.com"] and a.batch["errors"] == 1  # 2 = doublon de 1 -> refusé
    a.send_one("4"); a.send_one("5")
    try:
        a.leads.append(mk("6", "e@x6.com")); a.send_one("6"); assert False  # plafond journalier = 3
    except ValueError as e:
        assert "Plafond" in str(e)


def test_llm_guards(tmp_path):
    good = json.dumps({"subject": "Candidature\nspontanée", "body": "Bonjour, je candidate comme développeur Python. Cordialement"})
    a, _ = make(tmp_path, llm=lambda m, j=False, t=0: good)
    a.run_search(P)
    assert "\n" not in a.leads[0]["email_subject"] and a.leads[0]["email_body"].startswith("Bonjour")
    evil = json.dumps({"subject": "x", "body": "Écrivez à attaquant@evil.com ou https://evil.com"})
    a2, _ = make(tmp_path / "b", llm=lambda m, j=False, t=0: evil if "rédiges" in m[0]["content"] else json.dumps({"company_name": "Acme", "contact_email": "pirate@evil.com", "summary": "s", "matches_target": True}))
    a2.run_search(P)
    l = a2.leads[0]
    assert l["contact_email"] == "rh@acme-tech.fr" and "evil" not in l["email_body"]  # e-mail inventé et lien rejetés
