"""Intégration LMS (Moodle) : transport simulé, aucun accès réseau."""
import hashlib
import hmac
import json

import pytest

from backend import catalog, lms


class Fake:
    """Simule le serveur Moodle : enregistre les appels et répond selon la fonction."""
    def __init__(self, users=None, completed=False, notenroled=False):
        self.calls, self.users, self.completed, self.notenroled, self.next_id = [], dict(users or {}), completed, notenroled, 100

    def __call__(self, url, data):
        self.calls.append((url, data)); fn = data["wsfunction"]
        if fn == "core_user_get_users_by_field":
            e = data["values[0]"]; return [{"id": self.users[e], "email": e}] if e in self.users else []
        if fn == "core_user_create_users":
            self.next_id += 1; self.users[data["users[0][email]"]] = self.next_id; return [{"id": self.next_id, "username": data["users[0][username]"]}]
        if fn == "enrol_manual_enrol_users":
            return None
        if fn == "core_completion_get_course_completion_status":
            if self.notenroled: return {"exception": "moodle_exception", "errorcode": "notenroled", "message": "Not enrolled"}
            return {"completionstatus": {"completed": self.completed, "completions": []}}
        raise AssertionError(fn)


def moodle(fake, **kw): return lms.Moodle("https://lms.example.org/", "TOKEN", fake, **kw)


def test_flatten_matches_moodle_syntax():
    assert lms._flatten({"values": ["a@b"], "field": "email", "e": [{"roleid": 5, "x": True}]}) == {"values[0]": "a@b", "field": "email", "e[0][roleid]": "5", "e[0][x]": "1"}


def test_enroll_existing_user():
    f = Fake({"sara@x.org": 7}); r = moodle(f).enroll("Sara@X.org", "Sara H", 12)
    assert r == {"user_id": 7, "launch_url": "https://lms.example.org/course/view.php?id=12"}
    url, data = f.calls[-1]
    assert url == "https://lms.example.org/webservice/rest/server.php" and data["wstoken"] == "TOKEN" and data["moodlewsrestformat"] == "json"
    assert (data["enrolments[0][userid]"], data["enrolments[0][courseid]"], data["enrolments[0][roleid]"]) == ("7", "12", "5")


def test_unknown_user_needs_explicit_permission_to_be_created():
    with pytest.raises(lms.LMSError) as e: moodle(Fake()).enroll("new@x.org", "New User", 3)
    assert e.value.code == "nouser"
    f = Fake(); r = moodle(f, auto_create=True).enroll("new@x.org", "New User", 3)
    create = next(d for _, d in f.calls if d["wsfunction"] == "core_user_create_users")
    assert r["user_id"] == 101 and create["users[0][createpassword]"] == "1" and create["users[0][firstname]"] == "New" and create["users[0][lastname]"] == "User"
    assert create["users[0][username]"] == "new" and create["users[0][auth]"] == "manual"


def test_completion_states():
    assert moodle(Fake({"a@x.org": 1}, completed=True)).completion("a@x.org", 5) == {"enrolled": True, "completed": True}
    assert moodle(Fake({"a@x.org": 1}, completed=False)).completion("a@x.org", 5) == {"enrolled": True, "completed": False}
    assert moodle(Fake({"a@x.org": 1}, notenroled=True)).completion("a@x.org", 5) == {"enrolled": False, "completed": False}
    assert moodle(Fake()).completion("ghost@x.org", 5) == {"enrolled": False, "completed": False}


def test_moodle_errors_become_lmserror_without_leaking_token():
    def boom(url, data): return {"exception": "webservice_access_exception", "errorcode": "accessexception", "message": "Access control exception"}
    with pytest.raises(lms.LMSError) as e: moodle(boom).find_user("a@x.org")
    assert "TOKEN" not in str(e.value) and e.value.code == "accessexception"


def test_https_required_except_localhost():
    with pytest.raises(lms.LMSError): lms.Moodle("http://lms.example.org", "t")
    assert lms.Moodle("http://localhost:8080", "t").launch_url(2) == "http://localhost:8080/course/view.php?id=2"


def test_from_env():
    assert lms.from_env({}) is None and lms.from_env({"MOODLE_URL": "https://m.org"}) is None
    m = lms.from_env({"MOODLE_URL": "https://m.org", "MOODLE_TOKEN": "t", "MOODLE_AUTO_CREATE_USERS": "TRUE"}); assert m.auto_create is True


def sign(secret, raw): return "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def test_signature():
    raw = b'{"a":1}'
    assert lms.verify_signature("s3", raw, sign("s3", raw)) and lms.verify_signature("s3", raw, sign("s3", raw)[7:].upper())
    assert not lms.verify_signature("s3", raw, sign("other", raw)) and not lms.verify_signature("s3", b"{}", sign("s3", raw))
    assert not lms.verify_signature("", raw, sign("", raw)) and not lms.verify_signature("s3", raw, "")


def test_parse_events():
    assert lms.parse_event({"event": "course_completed", "user_email": " Sara@X.org ", "course_id": 12}) == ("sara@x.org", "12")
    assert lms.parse_event({"event": "course_completed", "email": "a@b.c"}) is None
    x = {"actor": {"mbox": "mailto:Sara@X.org"}, "verb": {"id": "http://adlnet.gov/expapi/verbs/completed"}, "object": {"id": "https://lms.example.org/course/view.php?id=12"}}
    assert lms.parse_event(x) == ("sara@x.org", "12")
    assert lms.parse_event({**x, "verb": {"id": "http://adlnet.gov/expapi/verbs/passed"}, "object": {"id": "https://lms.example.org/courses/9/"}}) == ("sara@x.org", "9")
    assert lms.parse_event({**x, "verb": {"id": "http://adlnet.gov/expapi/verbs/attempted"}}) is None
    assert lms.parse_event({**x, "actor": {"account": {"name": "u1"}}}) is None and lms.parse_event([]) is None and lms.parse_event({}) is None


def test_load_courses_validates_and_defaults_url(tmp_path):
    f = tmp_path / "c.json"
    f.write_text(json.dumps([{"lms_course_id": 7, "title": "Python pour l'analyse", "skills": "python sql", "modules": ["A", "B"]},
                             {"lms_course_id": "x", "title": "Invalide"}, {"lms_course_id": 8, "title": ""}, {"lms_course_id": 9, "title": "Http", "url": "http://insecure/x"},
                             {"lms_course_id": 10, "title": "Autre URL", "url": "https://formation.example.org/c/10"}]))
    cs = lms.load_courses(f, "https://lms.example.org/")
    assert [c["lms_course_id"] for c in cs] == [7, 10] and cs[0]["url"] == "https://lms.example.org/course/view.php?id=7" and cs[1]["url"].endswith("/c/10")
    assert lms.load_courses(tmp_path / "absent.json", "https://x") == [] and lms.load_courses(f, "") == [c for c in cs if c["lms_course_id"] == 10]


def test_catalog_includes_lms_courses(tmp_path, monkeypatch):
    f = tmp_path / "c.json"; f.write_text(json.dumps([{"lms_course_id": 7, "title": "Cours maison", "skills": "python", "url": "https://lms.example.org/course/view.php?id=7"}]))
    monkeypatch.setenv("LMS_COURSES_FILE", str(f))
    urls = [c["url"] for c in catalog.all_courses()]
    assert "https://lms.example.org/course/view.php?id=7" in urls and len(urls) == len(set(urls)) >= 64
