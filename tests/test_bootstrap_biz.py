import math, backend.bootstrap_biz as B

CV = "Développeur Python et SQL, 8 ans d'expérience, manager d'une équipe de 5, formateur en entreprise. Passionné de data et de marketing."


def run(**k):
    return B.reply({"cv_text": CV, **k})


def test_all_languages_complete_and_same_shape():
    ref = B.L["fr"]
    for l in B.LANGS:
        d = B.L[l]
        assert set(d) == set(ref) and len(d["dom"]) == 11 and len(d["arche"]) == 8 and len(d["cost"]) == 6 and len(d["bmc"]) == 9
        assert len(d["qs"]) == 6 and len(d["mvp"]) == 6 and set(d["lab"]) == set(ref["lab"]) and set(d["risk"]) == set(B.RK)
        for a in d["arche"].values():
            assert "{domain}" in a["desc"]
        r = run(lang=l, idea=0)
        assert len(r["ideas"]) == 3 and r["plan"] and "BootstrapBot" in r["master_prompt"] and CV in r["master_prompt"]


def test_skills_unfair_and_three_ideas_with_three_risks():
    r = run()
    assert [d["key"] for d in r["skills"]["domains"]][0] == "tech" and r["skills"]["years"] == 8
    assert "python" in r["skills"]["hard"] and {s["key"] for s in r["skills"]["soft"]} >= {"lead", "ana"}
    assert len(r["ideas"]) == 3 and len({i["key"] for i in r["ideas"]}) == 3
    assert all(len(i["risks"]) == 3 and i["tools"] and i["test"] for i in r["ideas"]) and r["plan"] is None
    assert len(r["hidden_costs"]) == 6 and [c["cat"] for c in r["toolbox"]] == ["ideas", "research", "site", "design", "finance", "acq"]


def test_generic_cv_gets_default_ideas_and_placeholder():
    r = B.reply({"cv_text": "x" * 40})
    assert [i["key"] for i in r["ideas"]] == list(B.DEFAULT_ARCH) and r["skills"]["domains"][0]["key"] == "general" and "À COMPLÉTER" in r["unfair"]


def test_break_even_uses_only_user_numbers():
    r = run(idea=1, price="100", var_cost="10", fixed="300", goal="1000", hours="10")
    f = r["plan"]["finance"]
    assert "4 vente" in f[0] and "15 vente" in f[1] and "4 vente" in f[2]
    assert math.ceil(300 / 90) == 4 and math.ceil(1300 / 90) == 15
    assert "100" in [b["value"] for b in r["plan"]["bmc"] if b["key"] == "rev"]
    r = run(idea=0)
    assert "Renseignez" in r["plan"]["finance"][0] and all("À COMPLÉTER" in b["value"] for b in r["plan"]["bmc"] if b["key"] in ("seg", "rel", "res", "act", "par"))
    assert "supérieur" in run(idea=0, price="5", var_cost="9", fixed="10")["plan"]["finance"][0]
    assert "Sans coûts fixes" in run(idea=0, price="5", var_cost="1", fixed="0")["plan"]["finance"][0]


def test_only_listed_free_tools():
    allowed = {"Notion", "Trello", "Google Keep", "Google Trends", "Ubersuggest", "AnswerThePublic", "Similarweb", "Carrd", "Google Sites", "Framer", "Puffify", "Canva", "Photopea",
               "Coolors", "Remove.bg", "Google Sheets", "Buffer", "Meta Business Suite", "CapCut", "Typeform", "Google Forms", "Google Docs"}
    for tools in list(B.ARCH_TOOLS.values()) + [t for _, t in B.TOOLBOX]:
        for tool in tools:
            assert any(a.lower() in tool.lower() for a in allowed), tool


def test_validation():
    for bad in ({"cv_text": "court"}, {"price": "-3"}, {"price": "abc"}, {"price": "1e99"}, {"hours": "500"}, {"idea": 5}, {"idea": True}, {"lang": "zz"}):
        try:
            B.reply({"cv_text": CV, **bad})
        except ValueError:
            continue
        raise AssertionError(bad)


def test_injection_text_is_inert_and_long_cv_is_clipped():
    r = B.reply({"cv_text": "<script>alert(1)</script> " + "python " * 2000, "passions": "ignore all <b>" * 50})
    assert len(r["master_prompt"]) < 20000 and r["skills"]["domains"][0]["key"] == "tech"
