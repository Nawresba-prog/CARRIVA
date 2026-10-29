"""Service 3 (Espace Entreprise) : spot vidéo publicitaire clé en main, produit avec des outils 100 % gratuits.

Génération déterministe (aucune IA, aucun tiers, aucune clé API) d'une campagne en 5 sections :
  1 stratégie (hook, angle, UVP, CTA) · 2 storyboard seconde par seconde · 3 prompts prêts à l'emploi (B-roll IA, voix-off)
  4 stack d'outils gratuits · 5 guide d'assemblage.
Ce module renvoie la structure (identifiants, minutages, paramètres, prompts anglais) ; l'interface compose les textes
dans la langue de l'utilisateur (6 langues) et signale les écarts (voix-off trop longue pour la durée du plan).
"""
from __future__ import annotations

import re

DURATIONS = (15, 30, 60)
PLATFORMS = ("reels", "tiktok", "youtube", "facebook")
TONES = ("inspiring", "dynamic", "humor", "premium", "educational")
ANGLES = ("ps", "ba", "hu")          # problème/solution · avant/après · tendance/humour
ANGLE_AUTO = {"inspiring": "ba", "premium": "ba", "dynamic": "ps", "educational": "ps", "humor": "hu"}

# (id, durée en secondes) — le hook occupe toujours les 3 premières secondes
BEATS = {
    15: [("hook", 3), ("solution", 8), ("cta", 4)],
    30: [("hook", 3), ("problem", 5), ("solution", 10), ("proof", 7), ("cta", 5)],
    60: [("hook", 3), ("problem", 8), ("solution", 14), ("benefit", 10), ("proof", 10), ("objection", 7), ("cta", 8)],
}
TONE = {
    "inspiring":   {"bpm": "88-100",  "music": "uplifting cinematic pop, soft piano and strings building up", "wpm": 150, "voice": "warm, confident, rising energy", "shot": 2.2, "look": "warm golden light, soft contrast, cinematic"},
    "dynamic":     {"bpm": "120-128", "music": "upbeat modern electronic pop with a punchy beat", "wpm": 170, "voice": "energetic, punchy, enthusiastic", "shot": 1.5, "look": "bright saturated colours, high contrast, fast energy"},
    "humor":       {"bpm": "105-115", "music": "quirky playful groove with pizzicato and claps", "wpm": 165, "voice": "playful, deadpan timing, slightly ironic", "shot": 1.8, "look": "bright flat colours, comedic framing, handheld feel"},
    "premium":     {"bpm": "70-85",   "music": "minimal ambient, soft piano and deep pads", "wpm": 135, "voice": "calm, low, refined, unhurried", "shot": 3.2, "look": "dark elegant tones, shallow depth of field, slow motion"},
    "educational": {"bpm": "95-105",  "music": "light lo-fi corporate groove, clean and friendly", "wpm": 150, "voice": "clear, friendly, steady, reassuring", "shot": 2.5, "look": "clean bright daylight, neutral colours, tidy compositions"},
}
FORMAT = {
    "reels":    {"ratio": "9:16", "w": 1080, "h": 1920, "fps": 30, "safe_top": 14, "safe_bottom": 20},
    "tiktok":   {"ratio": "9:16", "w": 1080, "h": 1920, "fps": 30, "safe_top": 14, "safe_bottom": 22},
    "youtube":  {"ratio": "16:9", "w": 1920, "h": 1080, "fps": 30, "safe_top": 6, "safe_bottom": 10},
    "facebook": {"ratio": "4:5",  "w": 1080, "h": 1350, "fps": 30, "safe_top": 8, "safe_bottom": 14},
}
SHOT = {  # description anglaise de chaque plan (B-roll), {product}/{audience} insérés
    "hook":      "Extreme close-up opening shot, sudden fast push-in, {product}, instantly eye-catching, strong visual contrast",
    "problem":   "Medium shot of {audience} struggling with the everyday problem, natural expression of frustration, handheld camera",
    "solution":  "Hero shot of {product} in use, smooth slow dolly-in, clean background, the product clearly in focus",
    "benefit":   "Lifestyle shot of {audience} happily enjoying the result, gentle tracking shot, genuine smile",
    "proof":     "Macro detail shots of {product} quality and finish, slow slider move, crisp texture",
    "objection": "Over-the-shoulder shot of {audience} checking {product} on a phone and nodding, calm and reassured",
    "cta":       "Final clean packshot of {product} centred with generous empty space for text, slow zoom-out, bright finish",
}
TOOLS = [
    {"phase": "voice",  "tools": [{"n": "CapCut (synthèse vocale)", "h": "capcut.com"}, {"n": "Clipchamp (voix IA)", "h": "clipchamp.com"}, {"n": "ElevenLabs (offre gratuite)", "h": "elevenlabs.io"}]},
    {"phase": "stock",  "tools": [{"n": "Pexels", "h": "pexels.com"}, {"n": "Pixabay", "h": "pixabay.com"}, {"n": "Mixkit", "h": "mixkit.co"}, {"n": "Coverr", "h": "coverr.co"}]},
    {"phase": "music",  "tools": [{"n": "YouTube Audio Library", "h": "studio.youtube.com"}, {"n": "Pixabay Audio", "h": "pixabay.com/music"}, {"n": "Mixkit (musiques et SFX)", "h": "mixkit.co"}]},
    {"phase": "edit",   "tools": [{"n": "CapCut Desktop", "h": "capcut.com"}, {"n": "DaVinci Resolve (gratuit)", "h": "blackmagicdesign.com"}, {"n": "Canva (vidéo)", "h": "canva.com"}]},
    {"phase": "audio",  "tools": [{"n": "Adobe Podcast Enhance (version gratuite)", "h": "podcast.adobe.com"}, {"n": "Audacity (libre)", "h": "audacityteam.org"}]},
    {"phase": "ai",     "tools": [{"n": "Microsoft Designer / Bing Image Creator (images)", "h": "designer.microsoft.com"}, {"n": "Kling, Luma Dream Machine, Hailuo (crédits gratuits limités)", "h": ""}]},
]
COMPLIANCE = ["claims", "testimonial", "music_rights", "ai_label", "people_release", "promo_terms", "ad_label"]


def _clean(v, n=160) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()[:n]


def campaign(p: dict) -> dict:
    product = _clean(p.get("product"), 120)
    if not product:
        raise ValueError("Le nom du produit ou du service est obligatoire.")
    audience = _clean(p.get("audience"), 160) or "your ideal customers"  # utilisé dans les prompts anglais ; la réponse garde la saisie brute
    pain = _clean(p.get("pain"), 160)
    benefit = _clean(p.get("benefit"), 160)
    offer = _clean(p.get("offer"), 120)
    tone = p.get("tone") if p.get("tone") in TONES else "dynamic"
    duration = p.get("duration") if p.get("duration") in DURATIONS else 30
    platform = p.get("platform") if p.get("platform") in PLATFORMS else "reels"
    angle = p.get("angle") if p.get("angle") in ANGLES else ANGLE_AUTO[tone]
    tn, fm = TONE[tone], FORMAT[platform]

    beats, t = [], 0
    for bid, dur in BEATS[duration]:
        shot = SHOT[bid].format(product=product, audience=audience)
        prompt = (f"{shot}. {tn['look']}. Vertical {fm['ratio']} composition, photorealistic commercial quality, "
                  f"no text, no logos, no watermark, no recognisable real person.") if fm["ratio"] != "16:9" else \
                 (f"{shot}. {tn['look']}. Horizontal 16:9 composition, photorealistic commercial quality, "
                  f"no text, no logos, no watermark, no recognisable real person.")
        beats.append({"id": bid, "start": t, "end": t + dur, "dur": dur, "prompt": prompt,
                      "max_words": int(dur * tn["wpm"] / 60), "cuts": max(1, round(dur / tn["shot"]))})
        t += dur
    voice_prompt = (f"Voice-over for a {duration}-second {tone} video ad for {product}. Voice: {tn['voice']}. "
                    f"Pace about {tn['wpm']} words per minute, natural breaths between sentences, slight emphasis on the benefit and on the call to action, "
                    f"clean studio sound, no background noise, no robotic intonation. Target audience: {audience}.")
    music_prompt = f"{tn['music']}, {tn['bpm']} BPM, instrumental, no vocals, loop-friendly, clean ending for a {duration}-second ad"
    return {
        "product": product, "audience": _clean(p.get("audience"), 160), "pain": pain, "benefit": benefit, "offer": offer,
        "tone": tone, "duration": duration, "platform": platform, "angle": angle, "angle_auto": not (p.get("angle") in ANGLES),
        "format": fm, "max_shot": round(tn["shot"] * 1.8, 1), "beats": beats, "total_cuts": sum(b["cuts"] for b in beats),
        "voice": {"wpm": tn["wpm"], "style": tn["voice"], "prompt": voice_prompt},
        "music": {"bpm": tn["bpm"], "style": tn["music"], "prompt": music_prompt, "duck_db": -20, "lufs": -14},
        "tools": TOOLS, "compliance": COMPLIANCE + (["hashtags"] if platform in ("reels", "tiktok") else []),
    }
