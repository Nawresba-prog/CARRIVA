import json

from backend import llm_polish

DATA = {"summary": "Ingénieure logiciel avec 4 ans d'expérience.", "experiences": [
    {"title": "Dev", "company": "Atlas", "description": "Conception d'API REST.\nMise en place de CI/CD."}, {"title": "Stagiaire", "company": "X", "description": ""}]}


def fake(resp):
    return lambda system, user: resp if isinstance(resp, str) else json.dumps(resp)


def test_good_output_applied_and_input_is_data_not_instructions():
    seen = {}
    def call(system, user):
        seen["system"], seen["user"] = system, user
        return "```json\n" + json.dumps({"summary": "Ingénieure logiciel forte de 4 ans d'expérience.", "experiences": ["Conçoit des API REST.\nDéploie des pipelines CI/CD.", ""]}) + "\n```"
    out, warn = llm_polish.polish(DATA, "fr", call)
    assert warn is None and out["summary"].startswith("Ingénieure logiciel forte")
    assert out["experiences"][0]["description"].startswith("Conçoit") and out["experiences"][1]["description"] == ""
    assert "jamais des instructions" in seen["system"] and "Conception d'API REST" in seen["user"]


def test_invented_facts_are_rejected():
    bad = {"summary": "Ingénieure avec 10 ans d'expérience, contact: x@evil.io", "experiences": ["Gère 50 serveurs.", ""]}
    out, warn = llm_polish.polish(DATA, "fr", fake(bad))
    assert out["summary"] == DATA["summary"] and out["experiences"][0]["description"] == DATA["experiences"][0]["description"]


def test_wrong_structure_and_garbage_fall_back():
    for resp in ({"summary": "x", "experiences": ["only one"]}, "pas du json"):
        out, warn = llm_polish.polish(DATA, "fr", fake(resp))
        assert out == DATA and warn == "ai_failed"


def test_unavailable_without_key(monkeypatch=None):
    import os
    os.environ.pop("ANTHROPIC_API_KEY", None)
    out, warn = llm_polish.polish(DATA, "fr")
    assert out == DATA and warn == "ai_unavailable"
