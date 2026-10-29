from backend import strategy as S


def _all(v):
    return {q: v for q in S.QUESTIONS}


def test_scores_bounds_and_extremes():
    zero, full = S.diagnostic({"answers": _all(0)}), S.diagnostic({"answers": _all(2)})
    assert zero["score"] == 0 and zero["band"] == "red" and full["score"] == 100 and full["band"] == "green"
    assert all(v["score"] == 100 and v["answered"] == v["total"] for v in full["pillars"].values())
    assert full["weaknesses"] == [] and full["roadmap"] == {"d30": [], "d90": [], "m12": []} and full["progress"] == 0


def test_no_answers_does_not_crash_and_unanswered_not_penalised():
    r = S.diagnostic({})
    assert r["score"] == 0 and r["answered"] == 0 and r["weaknesses"] == []
    r = S.diagnostic({"answers": {"st_kpi": 2}})
    assert r["score"] == 100 and r["pillars"]["csr"]["answered"] == 0 and r["pillars"]["csr"]["band"] == "none"


def test_invalid_answers_ignored():
    r = S.diagnostic({"answers": {"nope": 2, "st_kpi": 5, "st_vision": "x", "cp_data": 1}})
    assert r["answered"] == 1 and r["pillars"]["compliance"]["score"] == 50


def test_roadmap_priorities_and_uniqueness():
    r = S.diagnostic({"answers": _all(0)})
    rm = r["roadmap"]; ids = rm["d30"] + rm["d90"] + rm["m12"]
    assert len(ids) == len(set(ids)) == len(S.QUESTIONS)
    assert len(rm["d30"]) == 4 and all(S.QUESTIONS[q][1] <= 2 and S.QUESTIONS[q][0] >= 2 for q in rm["d30"])
    assert S.PILLAR_OF[rm["d30"][0]] == "compliance"          # risque juridique d'abord
    assert "st_diversify" in rm["m12"]                          # effort 3 : chantier de fond


def test_done_actions_leave_the_roadmap_and_count_as_progress():
    a = {"cp_data": 0, "cp_fiscal": 0, "st_vision": 1, "cs_measure": 0}
    r = S.diagnostic({"answers": a, "done": ["cp_data", "bogus"]})
    assert "cp_data" not in sum(r["roadmap"].values(), []) and r["progress"] == 25
    assert next(w for w in r["weaknesses"] if w["id"] == "cp_data")["done"] is True


def _ids(rs):
    return {x["id"]: x["status"] for x in rs}


def test_regulations_by_country_and_size():
    fr = _ids(S.regulations("fr", 60, 8))
    assert fr["gdpr"] == "applies" and fr["fr_duerp"] == "applies" and fr["fr_cse"] == "applies" and fr["fr_egapro"] == "applies"
    assert "fr_beges" not in fr and "fr_sapin2" not in fr and fr["vsme"] == "voluntary" and "csrd" not in fr
    big = _ids(S.regulations("FR", 1200, 600))
    assert big["csrd"] == "applies" and big["fr_beges"] == "applies" and big["fr_sapin2"] == "applies" and "csddd" not in big
    assert _ids(S.regulations("DE", 6000, 2000))["csddd"] == "applies" and _ids(S.regulations("DE", 1000, 10))["de_lksg"] == "applies"
    small = _ids(S.regulations("FR", 8, None))
    assert "fr_cse" not in small and "whistle" not in small and "fr_egapro" not in small
    assert _ids(S.regulations("FR", 1500, None))["csrd"] == "check"       # CA inconnu : à vérifier, pas affirmé


def test_regulations_non_eu():
    ma = _ids(S.regulations("MA", 40, 3))
    assert ma["data_ma"] == "applies" and ma["ma_label"] == "voluntary" and "gdpr" not in ma and "csrd" not in ma and "fr_duerp" not in ma
    assert _ids(S.regulations("XX", 500, 100))["gdpr"] == "check" and "whistle" not in _ids(S.regulations("XX", 500, 100))


def test_i18n_covers_every_id_in_all_languages():
    import json, re, pathlib
    html = (pathlib.Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")
    m = re.search(r"const I18N_ST = (\{.*?\});\n", html, re.S); T = json.loads(m.group(1))
    need = {"q_" + q for q in S.QUESTIONS} | {"a_" + q for q in S.QUESTIONS} | {"gs6"}
    probe = [S.regulations(c, n, ca) for c in ("FR", "DE", "MA", "TN", "DZ", "XX", "ES") for n, ca in ((5, None), (60, 8), (1200, 600), (6000, 2000))]
    need |= {"r_" + g["id"] for rs in probe for g in rs} | {"stS_" + s for s in ("applies", "check", "voluntary", "info")}
    for l in ("fr", "en", "de", "es", "it", "ar"):
        assert not need - set(T[l]), (l, sorted(need - set(T[l])))
