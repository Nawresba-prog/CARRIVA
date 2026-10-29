"""Service 4 (Espace Entreprise) : retouche photo & visuels produit premium.

Deux briques, 100 % gratuites et sans IA payante :
  - plan()    : plan de retouche chiffré (étapes, outils gratuits, réglages lumière/couleur, export) — règles déterministes.
                Renvoie des identifiants + paramètres ; l'interface les traduit (6 langues).
  - enhance() : amélioration locale avec Pillow (balance des blancs prudente, niveaux, contraste, débruitage léger,
                agrandissement Lanczos ≤ x2, netteté adaptative). Ce n'est PAS de la super-résolution IA :
                pour l'agrandissement « type Real-ESRGAN », le plan oriente vers Upscayl (gratuit, local).
Le sujet n'est jamais déformé : seule une mise à l'échelle uniforme est appliquée ; aucun détourage automatique ici
(il demande un modèle à télécharger) — le plan indique Photoroom / Microsoft Designer / remove.bg (offres gratuites).
"""
from __future__ import annotations

import base64
import io

SCENES = ("product", "portrait", "food", "interior")
LIGHTS = ("studio", "natural")
BACKGROUNDS = ("white", "grey", "lifestyle", "brand", "transparent", "keep")
USAGES = ("web", "social", "marketplace", "print")
RATIOS = {"orig": None, "1:1": (1, 1), "4:5": (4, 5), "9:16": (9, 16), "16:9": (16, 9)}

MAX_BYTES = 8_000_000
MAX_PIXELS = 40_000_000

# réglages (échelle type Lightroom/Photopea/Fotor, -100..+100 sauf mention)
_BASE = {"exposure": 0.0, "contrast": 8, "highlights": -15, "shadows": 15, "whites": 5, "blacks": -5, "vibrance": 12, "saturation": 0, "clarity": 8, "sharpen": 40, "denoise_lum": 20, "denoise_color": 25}
_SCENE = {
    "product": {"contrast": 12, "clarity": 14, "sharpen": 55, "vibrance": 10},
    "portrait": {"contrast": 4, "clarity": -4, "sharpen": 30, "vibrance": 8, "highlights": -20, "shadows": 18, "denoise_lum": 28},
    "food": {"contrast": 10, "vibrance": 22, "saturation": 6, "clarity": 12, "sharpen": 45},
    "interior": {"contrast": 6, "highlights": -30, "shadows": 30, "vibrance": 8, "clarity": 10, "sharpen": 45},
}
_LIGHT = {  # (température K indicative pour balance des blancs, teinte, exposition)
    "studio": {"temperature": 5500, "tint": 0, "exposure": 0.1, "contrast": 4},
    "natural": {"temperature": 5200, "tint": 2, "exposure": 0.0, "contrast": 0},
}
_USAGE_OUT = {
    "web": {"long": 1600, "fmt": "webp", "q": 82, "kb": 300, "dpi": 72},
    "social": {"long": 1350, "fmt": "jpeg", "q": 85, "kb": 500, "dpi": 72},
    "marketplace": {"long": 2000, "fmt": "jpeg", "q": 90, "kb": 1500, "dpi": 72},
    "print": {"long": 3000, "fmt": "jpeg", "q": 92, "kb": 4000, "dpi": 300},
}
_SOCIAL_SIZES = {"1:1": (1080, 1080), "4:5": (1080, 1350), "9:16": (1080, 1920), "16:9": (1920, 1080)}


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def adjustments(scene: str, light: str, background: str) -> dict:
    a = dict(_BASE)
    a.update(_SCENE[scene])
    for k, v in _LIGHT[light].items():
        if k in ("exposure", "contrast"):
            a[k] = round(a.get(k, 0) + v, 2)
        else:
            a[k] = v
    if background == "white":  # fond blanc pur : on évite un sujet trop sombre qui « flotte »
        a["shadows"] = _clamp(a["shadows"] + 5, -100, 100)
        a["whites"] = _clamp(a["whites"] + 5, -100, 100)
    return a


def output(usage: str, ratio: str, src_w: int | None = None, src_h: int | None = None) -> dict:
    o = dict(_USAGE_OUT[usage])
    if ratio not in RATIOS:
        ratio = "orig"
    if usage == "social" and ratio in _SOCIAL_SIZES:
        w, h = _SOCIAL_SIZES[ratio]
    elif RATIOS[ratio]:
        rw, rh = RATIOS[ratio]
        long_ = o["long"]
        w, h = (long_, round(long_ * rh / rw)) if rw >= rh else (round(long_ * rw / rh), long_)
    elif src_w and src_h:
        k = o["long"] / max(src_w, src_h)
        w, h = round(src_w * k), round(src_h * k)
    else:
        w, h = o["long"], None
    o.update(w=w, h=h, ratio=ratio)
    return o


def upscale_factor(src_w: int | None, src_h: int | None, target_long: int) -> int:
    """Facteur d'agrandissement recommandé (1, 2 ou 4). Au-delà de x2 le rendu « plastique » devient probable."""
    if not src_w or not src_h:
        return 1
    need = target_long / max(src_w, src_h)
    if need <= 1.05:
        return 1
    return 2 if need <= 2.5 else 4


def plan(p: dict) -> dict:
    scene = p.get("scene") if p.get("scene") in SCENES else "product"
    light = p.get("light") if p.get("light") in LIGHTS else "studio"
    bg = p.get("background") if p.get("background") in BACKGROUNDS else "white"
    usage = p.get("usage") if p.get("usage") in USAGES else "web"
    ratio = p.get("ratio") if p.get("ratio") in RATIOS else "orig"
    sw = p.get("src_w") if isinstance(p.get("src_w"), int) and p["src_w"] > 0 else None
    sh = p.get("src_h") if isinstance(p.get("src_h"), int) and p["src_h"] > 0 else None
    out = output(usage, ratio, sw, sh)
    adj = adjustments(scene, light, bg)
    factor = upscale_factor(sw, sh, max(out["w"] or 0, out["h"] or 0) or out["long"])
    low = bool(sw and sh and max(sw, sh) < 800)

    steps = [{"id": "audit", "tool": "Squoosh / IrfanView", "params": {"src_w": sw, "src_h": sh, "target": max(out["w"] or 0, out["h"] or 0), "low": low}}]
    if factor > 1:
        steps.append({"id": "upscale", "tool": "Upscayl (gratuit, local, open source)", "params": {"factor": factor, "model": "High Fidelity", "blend": 70 if scene == "portrait" else 85}})
    steps.append({"id": "denoise", "tool": "Photopea / GIMP / Fotor (gratuits)", "params": {"lum": adj["denoise_lum"], "color": adj["denoise_color"], "keep_texture": scene in ("food", "product")}})
    if ratio != "orig":
        steps.append({"id": "crop", "tool": "Photopea / Canva (gratuits)", "params": {"ratio": ratio, "safe": "10 %"}})
    if bg != "keep":
        steps.append({"id": "cutout", "tool": "Photoroom / Microsoft Designer / remove.bg (offres gratuites)", "params": {"edge": "0.5–1 px", "check": ["hair", "transparent", "reflection"] if scene in ("product", "portrait") else ["edges"]}})
        steps.append({"id": "background", "tool": "Photoroom / Microsoft Designer", "params": {"bg": bg}})
    steps.append({"id": "light", "tool": "Photopea / Fotor / GIMP (gratuits)", "params": {"scheme": light, "scene": scene}})
    steps.append({"id": "spots", "tool": "Photopea « Correcteur » / GIMP « Healing »", "params": {}})
    steps.append({"id": "export", "tool": "Squoosh (gratuit, navigateur)", "params": {"w": out["w"], "h": out["h"], "fmt": "png" if bg == "transparent" else out["fmt"], "q": out["q"], "kb": out["kb"], "dpi": out["dpi"]}})
    for i, s in enumerate(steps, 1):
        s["n"] = i

    checklist = ["proportions", "edges", "colour_true", "no_plastic", "no_halo", "name_alt"]
    if bg == "white":
        checklist.append("white_255")
    if usage == "marketplace":
        checklist.append("marketplace_rules")
    if scene == "portrait":
        checklist.append("skin_texture")
    return {"scene": scene, "light": light, "background": bg, "usage": usage, "ratio": ratio, "adjustments": adj, "output": out,
            "steps": steps, "checklist": checklist, "warn_low": low, "upscale": factor}


# ----------------------------------------------------------------------------------------- amélioration locale
class ImageError(ValueError):
    pass


def _decode(data_uri: str) -> bytes:
    head, _, b64 = (data_uri or "").partition(",")
    if not head.startswith("data:image/") or ";base64" not in head or not b64:
        raise ImageError("Image invalide (data-URI JPEG/PNG/WebP attendue).")
    if len(b64) > MAX_BYTES * 4 // 3 + 16:
        raise ImageError("Image trop lourde (8 Mo maximum).")
    try:
        return base64.b64decode(b64, validate=True)
    except Exception as exc:  # noqa: BLE001
        raise ImageError("Image illisible.") from exc


def enhance(data_uri: str, light: str = "studio", denoise: int = 40, strength: int = 50, target_long: int = 1600, max_scale: float = 2.0) -> dict:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageStat

    raw = _decode(data_uri)
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        im = Image.open(io.BytesIO(raw))
        if im.format not in ("JPEG", "PNG", "WEBP"):
            raise ImageError("Format non pris en charge (JPEG, PNG ou WebP).")
        if im.width * im.height > MAX_PIXELS:
            raise ImageError("Image trop grande (40 mégapixels maximum).")
        im = ImageOps.exif_transpose(im)
        alpha = im.getchannel("A") if "A" in im.getbands() else None
        im = im.convert("RGB")
    except ImageError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ImageError("Image illisible.") from exc

    strength = _clamp(int(strength), 0, 100) / 100
    denoise = _clamp(int(denoise), 0, 100) / 100
    w0, h0 = im.size
    applied = []

    # 1) balance des blancs « gray-world » limitée à ±8 % (jamais de dominante forcée)
    r, g, b = ImageStat.Stat(im).mean
    m = (r + g + b) / 3 or 1
    gains = [_clamp(m / c if c else 1, 0.92, 1.08) for c in (r, g, b)]
    if max(abs(x - 1) for x in gains) > 0.012:
        im = Image.merge("RGB", [ch.point(lambda v, k=k: min(255, int(v * k))) for ch, k in zip(im.split(), gains)])
        applied.append("white_balance")

    # 2) niveaux : étirement doux (0,3 % aux extrémités) mélangé à l'original
    lv = ImageOps.autocontrast(im, cutoff=0.3)
    im = Image.blend(im, lv, 0.35 + 0.4 * strength)
    applied.append("levels")

    # 3) débruitage léger : médiane 3×3 mélangée (texture conservée)
    if denoise > 0.05:
        im = Image.blend(im, im.filter(ImageFilter.MedianFilter(3)), 0.25 + 0.5 * denoise)
        applied.append("denoise")

    # 4) contraste / saturation modérés ; lumière studio un peu plus nette que naturelle
    im = ImageEnhance.Contrast(im).enhance(1 + (0.06 + 0.10 * strength) * (1.2 if light == "studio" else 1))
    im = ImageEnhance.Color(im).enhance(1 + 0.04 + 0.10 * strength)
    applied.append("tone")

    # 5) agrandissement uniforme Lanczos (jamais plus de max_scale, jamais en dessous de la taille d'origine)
    long_ = max(w0, h0)
    k = _clamp(target_long / long_, 1.0, max_scale) if target_long else 1.0
    if k > 1.02:
        im = im.resize((round(w0 * k), round(h0 * k)), Image.LANCZOS)
        applied.append("upscale")
    else:
        k = 1.0

    # 6) netteté adaptative (rayon proportionnel à la taille, sans halo : seuil non nul)
    rad = _clamp(max(im.size) / 1600, 0.6, 2.0)
    im = im.filter(ImageFilter.UnsharpMask(radius=rad, percent=int(60 + 80 * strength), threshold=3))
    applied.append("sharpen")

    if alpha is not None:
        alpha = alpha.resize(im.size, Image.LANCZOS)
        im = im.convert("RGBA"); im.putalpha(alpha)
        buf = io.BytesIO(); im.save(buf, "PNG", optimize=True); mime = "image/png"
    else:
        buf = io.BytesIO(); im.save(buf, "JPEG", quality=90, optimize=True, progressive=True, subsampling=0); mime = "image/jpeg"
    return {"image": f"data:{mime};base64," + base64.b64encode(buf.getvalue()).decode(), "width": im.width, "height": im.height,
            "scale": round(k, 2), "applied": applied, "bytes": len(buf.getvalue()), "src_width": w0, "src_height": h0}
