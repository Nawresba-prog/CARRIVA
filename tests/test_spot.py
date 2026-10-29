import json, pathlib, re
from backend import spot


def test_requires_product():
    try:
        spot.campaign({"product": "  "}); assert False
    except ValueError:
        pass


def test_timings_cover_whole_duration_for_all_durations():
    for d in spot.DURATIONS:
        c = spot.campaign({"product": "X", "duration": d})
        assert c["beats"][0]["id"] == "hook" and c["beats"][0]["end"] == 3
        assert c["beats"][-1]["id"] == "cta" and c["beats"][-1]["end"] == d
        assert all(a["end"] == b["start"] for a, b in zip(c["beats"], c["beats"][1:]))
        assert all(b["max_words"] >= 5 and b["cuts"] >= 1 for b in c["beats"])


def test_defaults_and_auto_angle():
    c = spot.campaign({"product": "X", "tone": "???", "duration": 99, "platform": "myspace", "angle": "auto"})
    assert (c["tone"], c["duration"], c["platform"]) == ("dynamic", 30, "reels") and c["angle"] == "ps" and c["angle_auto"]
    assert spot.campaign({"product": "X", "tone": "humor"})["angle"] == "hu"
    assert spot.campaign({"product": "X", "tone": "humor", "angle": "ba"})["angle"] == "ba"


def test_format_per_platform_and_prompts_are_clean():
    assert spot.campaign({"product": "X", "platform": "youtube"})["format"]["ratio"] == "16:9"
    c = spot.campaign({"product": "Crème bio", "platform": "tiktok", "audience": "women 30-45"})
    for b in c["beats"]:
        assert "no text, no logos, no watermark" in b["prompt"] and "9:16" in b["prompt"]
    assert "Crème bio" in c["beats"][0]["prompt"] and "women 30-45" in c["beats"][1]["prompt"] if len(c["beats"]) > 1 else True
    assert "BPM" in c["music"]["prompt"] and "words per minute" in c["voice"]["prompt"]


def test_input_is_sanitised():
    c = spot.campaign({"product": "A\n\n  B" + "z" * 500})
    assert "\n" not in c["product"] and len(c["product"]) <= 120


def test_compliance_and_tools():
    assert "hashtags" in spot.campaign({"product": "X", "platform": "reels"})["compliance"]
    assert "hashtags" not in spot.campaign({"product": "X", "platform": "youtube"})["compliance"]
    assert {p["phase"] for p in spot.TOOLS} == {"voice", "stock", "music", "edit", "audio", "ai"}


def test_i18n_covers_every_key_the_ui_can_request():
    html = (pathlib.Path(__file__).resolve().parent.parent / "frontend" / "index.html").read_text(encoding="utf-8")
    d = json.loads(re.search(r"const I18N_R = (\{.*?\});\n", html, re.S).group(1))
    need = set(["gs3", "sp_go", "sp_music_tpl", "sp_cuts_tpl", "sp_words_warn", "sp_lic", "sp_chk", "sp_p_en", "sp_uvp_tpl", "sp_cta_tpl", "sp_cta_none"])
    need |= {f"sp_h{i}" for i in range(1, 6)} | {f"sp_as_{i}" for i in range(1, 13)}
    need |= {f"sp_tone_{t}" for t in spot.TONES} | {f"sp_vi_{t}" for t in spot.TONES} | {f"sp_plat_{p}" for p in spot.PLATFORMS} | {f"sp_angle_{a}" for a in spot.ANGLES}
    need |= {f"sp_{k}_{a}" for a in spot.ANGLES for k in ("hookd", "angled")}
    for dur in spot.DURATIONS:
        for b, _ in spot.BEATS[dur]:
            need |= {f"sp_v_{b}", f"sp_x_{b}"}
    for a in spot.ANGLES:
        for b in ("hook", "problem", "solution"):
            need |= {f"sp_vo_{a}_{b}", f"sp_ov_{a}_{b}"}
    for b in ("benefit", "proof", "objection", "cta", "cta0"):
        need |= {f"sp_vo_{b}", f"sp_ov_{b}"}
    need |= {f"sp_ph_{p['phase']}" for p in spot.TOOLS} | {f"sp_pi_{p['phase']}" for p in spot.TOOLS}
    need |= {f"sp_k_{k}" for k in spot.COMPLIANCE + ["hashtags"]}
    for lang in ("fr", "en", "de", "es", "it", "ar"):
        miss = [k for k in need if not d[lang].get(k, "").strip()]
        assert not miss, (lang, miss)
    # placeholders cohérents entre langues
    for k in need:
        base = set(re.findall(r"\{(\w+)\}", d["fr"][k]))
        for lang in ("en", "de", "es", "it", "ar"):
            assert set(re.findall(r"\{(\w+)\}", d[lang][k])) == base, (lang, k)
