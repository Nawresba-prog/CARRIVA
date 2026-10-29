"""Améliorer et gérer son profil LinkedIn : audit chiffré, mots-clés manquants, titres/« À propos » proposés, plan d'action sur 30 jours, boost IA optionnel.

LinkedIn ne permet ni de lire ni de modifier un profil par programme (API fermée, scraping interdit) : l'utilisateur colle les textes de son profil
(ou importe son PDF LinkedIn / son CV), l'audit est fait par règles déterministes (aucune IA, aucune donnée envoyée à un tiers) et les textes améliorés
sont à recopier à la main. Le boost IA (facultatif) n'est actif que si ANTHROPIC_API_KEY est défini et n'invente jamais de fait.
"""
from __future__ import annotations

import os
import re

from . import matching
from .cv_import import _pretty

LIMITS = {"headline": 220, "about": 2600}
GENERIC_HEADLINE = re.compile(r"(looking for|seeking|open to|en recherche|a la recherche|à la recherche|chercheur|demandeur|suche|cerco|busco|in cerca|opportunit|available for|etudiant|student at|ابحث عن|باحث عن)", re.I)
CTA = re.compile(r"(contact|reach out|write me|message me|get in touch|n'hesitez|n’hésitez|écrivez|ecrivez|kontakt|schreiben sie|scrivimi|contattami|escríbeme|escribeme|@|linkedin\.com|اتصل|راسل)", re.I)
METRIC = re.compile(r"(\d+[\d.,]*\s*(%|k\b|m\b|€|\$|£|x\b|ans\b|years|clients|users|utilisateurs|projets|projects|personnes|people|équipe|team|mois|months)|\b\d{2,}\b)", re.I)
CHECKS = {"photo": 5, "banner": 2, "custom_url": 3, "location": 2, "featured": 3}
MAX = {"headline": 20, "about": 25, "experience": 20, "skills": 15, "profile": 20}


def _txt(p: dict) -> str:
    ex = " ".join(f"{e.get('title', '')} {e.get('company', '')} {e.get('description', '')}" for e in p.get("experiences", []))
    return f"{p.get('headline', '')} {p.get('about', '')} {ex} {' '.join(p.get('skills', []))}"


def _ids(*texts: str) -> list[str]:
    return matching.extract_skills(*texts)


def audit(p: dict) -> dict:
    """p : headline, about, experiences[{title, company, description}], skills[], target_role, target_text, checks{photo,banner,custom_url,location,featured}, recommendations(int)."""
    headline, about = str(p.get("headline", "")).strip(), str(p.get("about", "")).strip()
    exps = [e for e in p.get("experiences", []) if str(e.get("title", "")).strip() or str(e.get("description", "")).strip()]
    skills = [s for s in p.get("skills", []) if str(s).strip()]
    role = str(p.get("target_role", "")).strip()
    target_ids = _ids(role, str(p.get("target_text", "")))
    have_ids = set(_ids(_txt(p)))
    missing = [i for i in target_ids if i not in have_ids]
    cov = (len(target_ids) - len(missing)) / len(target_ids) if target_ids else 1.0
    F, sec = [], {k: 0.0 for k in MAX}

    def add(id_, section, sev, gain, **params):
        F.append({"id": id_, "section": section, "sev": sev, "gain": round(gain), "params": params})

    # --- titre (20)
    if not headline:
        add("hl_missing", "headline", "high", 20)
    else:
        sec["headline"] += 6
        n = len(headline)
        if n >= 80: sec["headline"] += 6
        elif n >= 40: sec["headline"] += 3; add("hl_short", "headline", "med", 3, n=n)
        else: add("hl_short", "headline", "high", 6, n=n)
        rt = [w for w in re.findall(r"\w{3,}", matching.normalize(role))]
        kw_hit = bool(rt) and any(w in matching.normalize(headline) for w in rt) or len(set(_ids(headline))) >= 2
        if kw_hit or (not role and len(set(_ids(headline))) >= 1): sec["headline"] += 6
        else: add("hl_nokw", "headline", "high", 6)
        if GENERIC_HEADLINE.search(headline): add("hl_generic", "headline", "med", 2)
        else: sec["headline"] += 2
    # --- à propos (25)
    if not about:
        add("ab_missing", "about", "high", 25)
    else:
        sec["about"] += 5; n = len(about)
        if n >= 1000: sec["about"] += 6
        elif n >= 400: sec["about"] += 3; add("ab_short", "about", "med", 3, n=n)
        else: add("ab_short", "about", "high", 6, n=n)
        if n > LIMITS["about"]: add("ab_long", "about", "med", 0, n=n)
        hook = about[:210]
        if _ids(hook) or (role and any(w in matching.normalize(hook) for w in re.findall(r"\w{4,}", matching.normalize(role)))) or METRIC.search(hook): sec["about"] += 4
        else: add("ab_hook", "about", "med", 4)
        if len(METRIC.findall(about)) >= 2: sec["about"] += 5
        else: add("ab_nometrics", "about", "high", 5)
        if CTA.search(about): sec["about"] += 2
        else: add("ab_nocta", "about", "low", 2)
        if cov >= 0.5: sec["about"] += 3
        elif target_ids: add("ab_nokw", "about", "med", 3)
        else: sec["about"] += 3
    # --- expériences (20)
    if not exps:
        add("ex_missing", "experience", "high", 20)
    else:
        sec["experience"] += 4
        thin = [e for e in exps if len(str(e.get("description", "")).strip()) < 150]
        sec["experience"] += 6 * (1 - len(thin) / len(exps))
        if thin: add("ex_thin", "experience", "high" if len(thin) == len(exps) else "med", 6 * len(thin) / len(exps), n=len(thin), m=len(exps))
        with_m = [e for e in exps if METRIC.search(str(e.get("description", "")))]
        sec["experience"] += 6 * len(with_m) / len(exps)
        if len(with_m) < len(exps): add("ex_nometrics", "experience", "high", 6 * (1 - len(with_m) / len(exps)))
        exp_ids = set(_ids(" ".join(str(e.get("description", "")) + " " + str(e.get("title", "")) for e in exps)))
        ecov = (len([i for i in target_ids if i in exp_ids]) / len(target_ids)) if target_ids else 1.0
        sec["experience"] += 4 * ecov
        if target_ids and ecov < 0.5: add("ex_nokw", "experience", "med", 4 * (1 - ecov))
    # --- compétences (15)
    n = len(skills)
    sec["skills"] += min(5, n)
    if n < 5: add("sk_few", "skills", "high", 5 - n, n=n)
    if n >= 15: sec["skills"] += 3
    elif n >= 5: sec["skills"] += 3 * (n - 5) / 10; add("sk_more", "skills", "low", 3 * (15 - n) / 10, n=n)
    sk_ids = set(_ids(" , ".join(skills))) | have_ids
    scov = (len([i for i in target_ids if i in sk_ids]) / len(target_ids)) if target_ids else 1.0
    if n: sec["skills"] += 7 * scov            # rien à créditer sans aucune compétence
    if target_ids and scov < 1: add("sk_gap", "skills", "high" if scov < 0.5 else "med", 7 * (1 - scov), missing=[_pretty(matching.label(i)) for i in missing][:12])
    # --- complétude (20)
    ch = p.get("checks", {}) or {}
    for k, pts in CHECKS.items():
        if ch.get(k): sec["profile"] += pts
        else: add("pf_" + {"custom_url": "url"}.get(k, k), "profile", "high" if pts >= 5 else "med" if pts >= 3 else "low", pts)
    rec = int(p.get("recommendations") or 0)
    sec["profile"] += 5 if rec >= 2 else 2 if rec == 1 else 0
    if rec < 2: add("pf_reco", "profile", "med", 5 if rec == 0 else 3, n=rec)
    sections = {k: {"score": round(sec[k]), "max": MAX[k]} for k in MAX}
    score = max(0, min(100, sum(v["score"] for v in sections.values())))
    order = {"high": 0, "med": 1, "low": 2}
    F.sort(key=lambda f: (order[f["sev"]], -f["gain"]))
    kw = {"have": [_pretty(matching.label(i)) for i in target_ids if i in have_ids], "missing": [_pretty(matching.label(i)) for i in missing]}
    return {"score": score, "band": "green" if score >= 80 else "yellow" if score >= 55 else "red", "sections": sections, "findings": F, "keywords": kw, "plan": plan(F)}


def plan(findings: list[dict]) -> list[dict]:
    """Plan 30 jours : semaine 1 = corrections prioritaires, 2 = moyennes, 3 = le reste + contenu, 4 = suivi ; routines récurrentes."""
    hi = [f for f in findings if f["sev"] == "high"]; me = [f for f in findings if f["sev"] == "med"]; lo = [f for f in findings if f["sev"] == "low"]
    tasks = [{"id": f"fix_{f['id']}", "week": 1, "kind": "fix", "finding": f["id"]} for f in hi[:6]]
    tasks += [{"id": f"fix_{f['id']}", "week": 2, "kind": "fix", "finding": f["id"]} for f in (hi[6:] + me)[:6]]
    tasks += [{"id": f"fix_{f['id']}", "week": 3, "kind": "fix", "finding": f["id"]} for f in lo[:5]]
    tasks += [{"id": "ask_reco", "week": 3, "kind": "action"}, {"id": "feature_post", "week": 3, "kind": "action"}, {"id": "recheck", "week": 4, "kind": "action"}, {"id": "review_views", "week": 4, "kind": "action"}]
    tasks += [{"id": "routine_post", "week": 0, "kind": "routine"}, {"id": "routine_comment", "week": 0, "kind": "routine"}, {"id": "routine_connect", "week": 0, "kind": "routine"}]
    return tasks


# --------------------------------------------------------------------------- propositions de texte (à partir des seules données fournies)
def headline_options(p: dict) -> list[str]:
    role = (str(p.get("target_role", "")).strip() or (p.get("experiences") or [{}])[0].get("title", "") or "").strip()
    skills = [s for s in p.get("skills", []) if str(s).strip()]
    tgt = [_pretty(matching.label(i)) for i in _ids(role, str(p.get("target_text", "")))]
    top = []
    for s in tgt + skills:           # d'abord ce que le poste visé demande ET que la personne possède
        if s.lower() not in {x.lower() for x in top} and (s.lower() in {x.lower() for x in skills} or not skills):
            top.append(s)
    top = top[:3] or skills[:3]
    value = str(p.get("value", "")).strip()
    out = []
    if role and top: out.append(f"{role} | " + " · ".join(top))
    if role and top and value: out.append(f"{role} | {value} | " + " · ".join(top[:2]))
    if role and value: out.append(f"{role} - {value}")
    if role and top: out.append(f"{role} · " + " | ".join(top))
    seen, res = set(), []
    for h in out:
        h = h[:LIMITS["headline"]]
        if h not in seen: seen.add(h); res.append(h)
    return res[:3]


def about_template(p: dict) -> dict:
    """Squelette « Accroche / Preuves / Compétences / Contact » avec les faits fournis ; les trous à remplir sont marqués [...]."""
    role = (str(p.get("target_role", "")).strip() or (p.get("experiences") or [{}])[0].get("title", "")).strip()
    skills = [s for s in p.get("skills", []) if str(s).strip()][:8]
    facts = []
    for e in (p.get("experiences") or [])[:3]:
        t, c = str(e.get("title", "")).strip(), str(e.get("company", "")).strip()
        if t: facts.append(f"{t}" + (f" - {c}" if c else ""))
    return {"role": role, "skills": skills, "facts": facts}


PROMPT = {
    "fr": ("Agis comme un expert LinkedIn et recruteur. Réécris mon profil pour le poste visé : « {role} ».\n\nRÈGLES STRICTES : n'invente AUCUN fait, chiffre, employeur, diplôme ou compétence ; utilise uniquement ce que contiennent mes textes ; si un chiffre manque, laisse [à compléter : chiffre]. Garde mon ton, sans formules creuses.\n\n"
           "LIVRE : 1) 3 titres (≤ 220 caractères, mots-clés du poste en tête) ; 2) une section « À propos » (1 500-2 000 caractères : accroche dans les 200 premiers caractères, 2-3 réalisations chiffrées si je les ai fournies, compétences clés, appel à l'action) ; 3) pour chaque expérience, 3-4 puces orientées résultats (verbe d'action + contexte + résultat) ; 4) 10 compétences à épingler, classées ; 5) 5 idées de posts pour 30 jours.\n\n",
           "MOTS-CLÉS DU POSTE À INTÉGRER (seulement s'ils sont vrais pour moi) : {kw}\n\nMON PROFIL ACTUEL :\n"),
    "en": ("Act as a LinkedIn expert and recruiter. Rewrite my profile for the target role: “{role}”.\n\nSTRICT RULES: do NOT invent any fact, number, employer, degree or skill; use only what my texts contain; if a number is missing, write [to complete: number]. Keep my voice, no filler phrases.\n\n"
           "DELIVER: 1) 3 headlines (≤ 220 characters, role keywords first); 2) an “About” section (1,500-2,000 characters: hook within the first 200 characters, 2-3 quantified achievements if I provided them, key skills, call to action); 3) for each experience, 3-4 result-oriented bullets (action verb + context + result); 4) 10 skills to pin, ranked; 5) 5 post ideas for 30 days.\n\n",
           "ROLE KEYWORDS TO INCLUDE (only if true for me): {kw}\n\nMY CURRENT PROFILE:\n"),
    "de": ("Handle als LinkedIn-Experte und Recruiter. Schreibe mein Profil für die Zielstelle um: „{role}“.\n\nSTRENGE REGELN: Erfinde KEINE Fakten, Zahlen, Arbeitgeber, Abschlüsse oder Fähigkeiten; nutze nur meine Texte; fehlt eine Zahl, schreibe [zu ergänzen: Zahl]. Behalte meinen Ton.\n\n"
           "LIEFERE: 1) 3 Schlagzeilen (≤ 220 Zeichen, Stellen-Keywords zuerst); 2) „Info“-Abschnitt (1.500-2.000 Zeichen: Einstieg in den ersten 200 Zeichen, 2-3 messbare Erfolge falls angegeben, Kernkompetenzen, Handlungsaufforderung); 3) je Station 3-4 ergebnisorientierte Stichpunkte; 4) 10 Top-Kenntnisse, sortiert; 5) 5 Post-Ideen für 30 Tage.\n\n",
           "STELLEN-KEYWORDS (nur wenn zutreffend): {kw}\n\nMEIN AKTUELLES PROFIL:\n"),
    "es": ("Actúa como experto en LinkedIn y reclutador. Reescribe mi perfil para el puesto objetivo: «{role}».\n\nREGLAS ESTRICTAS: NO inventes hechos, cifras, empresas, títulos ni habilidades; usa solo lo que contienen mis textos; si falta una cifra, escribe [por completar: cifra]. Mantén mi tono.\n\n"
           "ENTREGA: 1) 3 titulares (≤ 220 caracteres, palabras clave primero); 2) sección «Acerca de» (1.500-2.000 caracteres: gancho en los primeros 200, 2-3 logros cuantificados si los di, competencias clave, llamada a la acción); 3) por experiencia, 3-4 viñetas orientadas a resultados; 4) 10 aptitudes destacadas, ordenadas; 5) 5 ideas de publicaciones para 30 días.\n\n",
           "PALABRAS CLAVE DEL PUESTO (solo si son ciertas): {kw}\n\nMI PERFIL ACTUAL:\n"),
    "it": ("Agisci come esperto LinkedIn e recruiter. Riscrivi il mio profilo per il ruolo target: «{role}».\n\nREGOLE RIGIDE: NON inventare fatti, numeri, aziende, titoli o competenze; usa solo i miei testi; se manca un numero scrivi [da completare: numero]. Mantieni il mio tono.\n\n"
           "CONSEGNA: 1) 3 titoli (≤ 220 caratteri, parole chiave in testa); 2) sezione «Informazioni» (1.500-2.000 caratteri: gancio nei primi 200, 2-3 risultati quantificati se forniti, competenze chiave, invito all'azione); 3) per ogni esperienza 3-4 punti orientati ai risultati; 4) 10 competenze in evidenza, ordinate; 5) 5 idee di post per 30 giorni.\n\n",
           "PAROLE CHIAVE DEL RUOLO (solo se vere per me): {kw}\n\nIL MIO PROFILO ATTUALE:\n"),
    "ar": ("تصرّف كخبير في لينكدإن ومسؤول توظيف. أعد كتابة ملفي للوظيفة المستهدفة: «{role}».\n\nقواعد صارمة: لا تخترع أي حقيقة أو رقم أو جهة عمل أو شهادة أو مهارة؛ استخدم فقط ما في نصوصي؛ إذا غاب رقم اكتب [يُستكمل: رقم]. حافظ على أسلوبي.\n\n"
           "المطلوب: 1) ثلاثة عناوين (≤ 220 حرفاً، الكلمات المفتاحية أولاً)؛ 2) قسم «نبذة» (1500-2000 حرف: جملة جذب في أول 200 حرف، 2-3 إنجازات رقمية إن وُجدت، المهارات الأساسية، دعوة للتواصل)؛ 3) لكل خبرة 3-4 نقاط موجهة بالنتائج؛ 4) 10 مهارات للتثبيت مرتبة؛ 5) 5 أفكار منشورات لمدة 30 يوماً.\n\n",
           "الكلمات المفتاحية للوظيفة (فقط إن كانت صحيحة بالنسبة لي): {kw}\n\nملفي الحالي:\n"),
}


def profile_text(p: dict) -> str:
    lines = [f"Headline: {p.get('headline', '')}", f"About: {p.get('about', '')}"]
    for e in p.get("experiences", []):
        lines.append(f"- {e.get('title', '')} @ {e.get('company', '')}: {e.get('description', '')}")
    lines.append("Skills: " + ", ".join(p.get("skills", [])))
    return "\n".join(lines)


def ai_prompt(p: dict, lang: str = "fr", missing: list[str] | None = None) -> str:
    a, b = PROMPT.get(lang, PROMPT["en"])
    return a.format(role=p.get("target_role") or "—") + b.format(kw=", ".join(missing or []) or "—") + profile_text(p)


def boost(p: dict, lang: str, missing: list[str], post=None) -> str:
    """Boost IA facultatif (ANTHROPIC_API_KEY). `post` injectable pour les tests. Lève RuntimeError('no_key') sans clé."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key and post is None:
        raise RuntimeError("no_key")
    names = {"fr": "français", "en": "English", "de": "Deutsch", "es": "español", "it": "italiano", "ar": "العربية"}
    prompt = ai_prompt(p, lang, missing) + f"\n\nRéponds en {names.get(lang, 'English')}, en Markdown (titres ##)."
    if post is None:
        import httpx
        r = httpx.post("https://api.anthropic.com/v1/messages", timeout=90, headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                       json={"model": os.getenv("GROWTH_MODEL", "claude-sonnet-5-5"), "max_tokens": 3500, "temperature": 0.4, "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json().get("content", []))
    return post(prompt)
