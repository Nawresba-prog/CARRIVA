import base64, io, random
from backend import retouch as r


def _img(w=400, h=300, noisy=True, mode="RGB", fmt="JPEG"):
    from PIL import Image
    rnd = random.Random(1)
    im = Image.new(mode, (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            v = 90 + (x * 60) // w + (rnd.randint(-18, 18) if noisy else 0)
            px[x, y] = (v, v + 6, v - 8) if mode == "RGB" else (v, v + 6, v - 8, 255)
    buf = io.BytesIO(); im.save(buf, fmt)
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(buf.getvalue()).decode()


def test_plan_defaults_and_invalid_values_fall_back():
    p = r.plan({"scene": "???", "usage": None})
    assert p["scene"] == "product" and p["usage"] == "web" and p["steps"][0]["id"] == "audit"
    assert [s["n"] for s in p["steps"]] == list(range(1, len(p["steps"]) + 1))


def test_plan_upscale_factor_rules():
    assert r.upscale_factor(2000, 1500, 1600) == 1
    assert r.upscale_factor(1000, 800, 1600) == 2
    assert r.upscale_factor(400, 300, 1600) == 4
    assert r.upscale_factor(None, None, 1600) == 1
    ids = [s["id"] for s in r.plan({"src_w": 400, "src_h": 300, "usage": "web"})["steps"]]
    assert "upscale" in ids
    assert "upscale" not in [s["id"] for s in r.plan({"src_w": 3000, "src_h": 2000})["steps"]]


def test_plan_background_and_ratio_steps():
    ids = lambda **k: [s["id"] for s in r.plan(k)["steps"]]
    assert "cutout" in ids(background="white") and "cutout" not in ids(background="keep")
    assert "crop" in ids(ratio="1:1") and "crop" not in ids(ratio="orig")
    last = r.plan({"background": "transparent"})["steps"][-1]["params"]
    assert last["fmt"] == "png"


def test_output_sizes():
    assert (r.output("social", "4:5")["w"], r.output("social", "4:5")["h"]) == (1080, 1350)
    o = r.output("web", "orig", 4000, 3000); assert o["w"] == 1600 and o["h"] == 1200
    assert r.output("print", "1:1")["dpi"] == 300


def test_adjustments_in_range():
    for sc in r.SCENES:
        for li in r.LIGHTS:
            for bg in r.BACKGROUNDS:
                a = r.adjustments(sc, li, bg)
                for k, v in a.items():
                    if k not in ("temperature",):
                        assert -100 <= v <= 100, (sc, li, bg, k, v)
    assert r.adjustments("portrait", "natural", "keep")["clarity"] < r.adjustments("product", "natural", "keep")["clarity"]


def test_checklist_conditions():
    assert "white_255" in r.plan({"background": "white"})["checklist"]
    assert "marketplace_rules" in r.plan({"usage": "marketplace"})["checklist"]
    assert "skin_texture" in r.plan({"scene": "portrait"})["checklist"]


def test_enhance_keeps_proportions_and_upscales_at_most_2x():
    out = r.enhance(_img(400, 300), target_long=1600)
    assert out["scale"] == 2.0 and (out["width"], out["height"]) == (800, 600)
    assert abs(out["width"] / out["height"] - 400 / 300) < 0.01
    assert out["image"].startswith("data:image/jpeg;base64,") and "upscale" in out["applied"]


def test_enhance_never_shrinks_and_denoise_reduces_noise():
    from PIL import Image, ImageStat
    src = _img(500, 400)
    out = r.enhance(src, target_long=300, denoise=100, strength=0)
    assert out["scale"] == 1.0 and out["width"] == 500
    def lap(uri):
        im = Image.open(io.BytesIO(base64.b64decode(uri.split(",")[1]))).convert("L")
        from PIL import ImageFilter
        return ImageStat.Stat(im.filter(ImageFilter.FIND_EDGES)).stddev[0]
    assert lap(out["image"]) < lap(src)


def test_enhance_png_alpha_preserved():
    out = r.enhance(_img(200, 200, mode="RGBA", fmt="PNG"), target_long=400)
    assert out["image"].startswith("data:image/png;")
    from PIL import Image
    im = Image.open(io.BytesIO(base64.b64decode(out["image"].split(",")[1])))
    assert im.mode == "RGBA" and im.size == (400, 400)


def test_enhance_rejects_bad_input():
    for bad in ("", "hello", "data:text/plain;base64,aGk=", "data:image/png;base64,!!!", "data:image/png;base64," + base64.b64encode(b"notanimage").decode()):
        try:
            r.enhance(bad); assert False, bad
        except r.ImageError:
            pass


def test_enhance_rejects_huge_payload():
    try:
        r.enhance("data:image/jpeg;base64," + "A" * (r.MAX_BYTES * 2)); assert False
    except r.ImageError as e:
        assert "lourde" in str(e)


def test_i18n_all_languages_and_keys_used_by_plan():
    import json, pathlib, re
    html = (pathlib.Path(__file__).resolve().parent.parent / "frontend" / "index.html").read_text(encoding="utf-8")
    d = json.loads(re.search(r"const I18N_R = (\{.*?\});\n", html, re.S).group(1))
    need = ["gs4", "ph_plan", "ph_enh", "ph_note", "ph_done", "ph_src"]
    need += [f"s_{i}" for i in ("audit", "upscale", "denoise", "crop", "cutout", "background", "light", "spots", "export")]
    need += [f"ph_a_{k}" for k in r.adjustments("product", "studio", "white")] 
    need += [f"ph_bg_{b}" for b in r.BACKGROUNDS] + [f"ph_bgd_{b}" for b in ("white", "grey", "lifestyle", "brand", "transparent")]
    need += [f"ph_scene_{x}" for x in r.SCENES] + [f"ph_use_{x}" for x in r.USAGES] + [f"ph_ls_{x}" for x in r.LIGHTS]
    every = {"checklist": set()}
    for sc in r.SCENES:
        for us in r.USAGES:
            for bg in r.BACKGROUNDS:
                every["checklist"].update(r.plan({"scene": sc, "usage": us, "background": bg})["checklist"])
    need += [f"k_{c}" for c in every["checklist"]]
    for lang in ("fr", "en", "de", "es", "it", "ar"):
        for k in need:
            assert d[lang].get(k, "").strip(), (lang, k)
    assert "Retouche" in d["fr"]["gs4"]
