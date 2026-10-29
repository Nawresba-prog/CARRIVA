"""Robustesse : tous les générateurs déterministes sur de larges grilles d'entrées (aucune exception, scores bornés, JSON valide,
aucun marqueur de gabarit « {x} » ou « undefined » dans les textes produits)."""
import itertools, json, math, random
from backend import linkedin, retouch, spot, strategy

BAD = ("{", "}", "undefined", "NaN", "None")


def _walk(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _walk(v)
    else:
        yield o


def _finite(o):
    for v in _walk(o):
        if isinstance(v, float):
            assert math.isfinite(v), v


def test_spot_grid():
    n = 0
    for tone, dur, plat, angle in itertools.product(spot.TONES, spot.DURATIONS, spot.PLATFORMS, ("auto",) + spot.ANGLES):
        r = spot.campaign({"product": "Crème bio", "audience": "femmes 30-45", "tone": tone, "duration": dur, "platform": plat, "angle": angle, "offer": "-20 %"})
        assert sum(b["dur"] for b in r["beats"]) == dur and r["beats"][0]["dur"] == 3
        assert r["beats"][0]["start"] == 0 and all(b["end"] == b["start"] + b["dur"] for b in r["beats"])
        assert all(b["start"] == a["end"] for a, b in zip(r["beats"], r["beats"][1:]))
        _finite(r); json.dumps(r)
        for v in _walk([b["prompt"] for b in r["beats"]] + [r["voice"]["prompt"], r["music"]["prompt"]]):
            assert not any(x in str(v) for x in BAD[:4]), v
        n += 1
    assert n == 5 * 3 * 4 * 4


def test_spot_hostile_inputs():
    for prod in ("<script>alert(1)</script>", "x" * 5000, "ça‮ va", "{product} {0}", "\n\n  \t"):
        try:
            r = spot.campaign({"product": prod, "audience": prod, "pain": prod, "offer": prod})
        except ValueError:
            continue
        assert len(r["product"]) <= 120
        json.dumps(r)


def test_retouch_grid():
    for sc, li, bg, us, ra in itertools.product(retouch.SCENES, retouch.LIGHTS, retouch.BACKGROUNDS, retouch.USAGES, retouch.RATIOS):
        for src in ((None, None), (300, 200), (6000, 4000)):
            p = retouch.plan({"scene": sc, "light": li, "background": bg, "usage": us, "ratio": ra, "src_w": src[0], "src_h": src[1]})
            assert p["steps"][-1]["id"] == "export" and p["output"]["w"] > 0
            assert p["upscale"] in (1, 2, 4)
            _finite(p); json.dumps(p)


def test_strategy_random_answers():
    rnd = random.Random(7)
    ids = list(strategy.QUESTIONS)
    for _ in range(300):
        ans = {i: rnd.choice([0, 1, 2]) for i in rnd.sample(ids, rnd.randint(0, len(ids)))}
        done = rnd.sample(ids, rnd.randint(0, 5))
        r = strategy.diagnostic({"country": rnd.choice(["FR", "DE", "ES", "IT", "MA", "TN", "DZ", "XX"]), "employees": rnd.choice([0, 3, 60, 300, 1200, 6000]),
                                 "turnover_m": rnd.choice([None, 0, 2, 120, 500, 2000]), "goal": rnd.choice(["growth", "profit", "export", "transition"]), "answers": ans, "done": done})
        assert 0 <= r["score"] <= 100 and 0 <= r["progress"] <= 100
        for pl in r["pillars"].values():
            assert 0 <= (pl["score"] if isinstance(pl, dict) else pl) <= 100
        _finite(r); json.dumps(r)


def test_linkedin_random_profiles():
    rnd = random.Random(11)
    words = ["python", "gestion", "équipe", "projet", "vente", "SQL", "design", "anglais", "leadership", "analyse"]
    for _ in range(200):
        p = {"role": " ".join(rnd.sample(words, rnd.randint(0, 3))), "headline": " ".join(rnd.sample(words, rnd.randint(0, 8))),
             "about": " ".join(rnd.choices(words, k=rnd.randint(0, 120))), "skills": rnd.sample(words, rnd.randint(0, 10)),
             "experiences": [{"title": rnd.choice(words), "description": " ".join(rnd.choices(words, k=rnd.randint(0, 40)))} for _ in range(rnd.randint(0, 4))]}
        r = linkedin.audit(p)
        assert 0 <= r["score"] <= 100, r["score"]
        for sec in r["sections"].values():
            assert 0 <= (sec["score"] if isinstance(sec, dict) else sec) <= 100
        _finite(r); json.dumps(r)
