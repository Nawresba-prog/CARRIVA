"""Service 6 — Conseil en stratégie, RSE (développement durable) et conformité.

Diagnostic déterministe (sans IA, sans tiers) : l'entreprise répond à ~16 questions (0 = non, 1 = partiellement, 2 = oui) ; on calcule un score par pilier,
les forces/faiblesses, une feuille de route 30 jours / 90 jours / 12 mois et un « radar » des cadres réglementaires susceptibles de s'appliquer selon le pays,
l'effectif et le chiffre d'affaires. Les textes affichés (questions, actions, libellés) vivent dans l'interface, indexés par identifiant : ici, uniquement la logique.
Le radar est INDICATIF : seuils et calendriers évoluent (ex. omnibus CSRD/CSDDD de 2026) ; à valider avec un juriste ou un expert-comptable.
"""
from __future__ import annotations

PILLARS = {
    "strategy": ["st_vision", "st_position", "st_kpi", "st_diversify", "st_innov"],
    "csr": ["cs_measure", "cs_reduce", "cs_social", "cs_suppliers", "cs_gov"],
    "compliance": ["cp_data", "cp_labour", "cp_fiscal", "cp_ethics", "cp_sector", "cp_cyber"],
}
# (impact 1-3, effort 1-3) : sert à classer les actions ; effort faible + impact fort = gain rapide
QUESTIONS = {
    "st_vision": (3, 2), "st_position": (3, 2), "st_kpi": (3, 1), "st_diversify": (2, 3), "st_innov": (2, 2),
    "cs_measure": (3, 2), "cs_reduce": (2, 2), "cs_social": (3, 2), "cs_suppliers": (2, 2), "cs_gov": (2, 2),
    "cp_data": (3, 2), "cp_labour": (3, 2), "cp_fiscal": (3, 1), "cp_ethics": (2, 1), "cp_sector": (3, 2), "cp_cyber": (3, 1),
}
PILLAR_OF = {q: p for p, qs in PILLARS.items() for q in qs}
GOALS = ("growth", "profit", "export", "transition")
EU = set("AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE EU".split())


def _num(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def band(score: int) -> str:
    return "green" if score >= 75 else "yellow" if score >= 45 else "red"


def regulations(country: str, employees: int, turnover_m: float | None) -> list[dict]:
    """[{id, status}] — status : applies (seuil atteint), check (à vérifier), voluntary (volontaire / demandé par les clients), info."""
    c, n, ca = (country or "").upper(), max(0, int(employees or 0)), turnover_m
    eu = c in EU
    out = []

    def add(i, s):
        out.append({"id": i, "status": s})

    if eu: add("gdpr", "applies")
    elif c in ("MA", "TN", "DZ"): add("data_" + c.lower(), "applies")
    else: add("gdpr", "check")                     # hors UE : s'applique si des clients/résidents UE sont visés
    if eu and n >= 50: add("whistle", "applies")
    if eu: add("pay_transp", "check")
    if eu and n >= 50: add("nis2", "check")
    if eu or c not in ("MA", "TN", "DZ"): add("aiact", "info")
    if eu and n > 1000 and ca is not None and ca > 450: add("csrd", "applies")
    elif eu and n > 1000 and ca is None: add("csrd", "check")
    else: add("vsme", "voluntary")
    if eu and n > 5000 and ca is not None and ca > 1500: add("csddd", "applies")
    if c == "FR":
        if n >= 1: add("fr_duerp", "applies")
        if n >= 11: add("fr_cse", "applies")
        if n >= 50: add("fr_egapro", "applies")
        if n >= 500: add("fr_beges", "applies")
        if n >= 500 and ca is not None and ca > 100: add("fr_sapin2", "applies")
        elif n >= 500 and ca is None: add("fr_sapin2", "check")
        add("fr_einvoice", "check")
    if c == "DE" and n >= 1000: add("de_lksg", "applies")
    if c == "MA": add("ma_label", "voluntary")
    add("iso", "voluntary")
    add("ecovadis", "voluntary")
    return out


def diagnostic(p: dict) -> dict:
    """p : country, employees, turnover_m, sector, goal, answers{id: 0|1|2}, done[ids]. Les questions sans réponse sont comptées à part (non évaluées)."""
    ans = {k: int(v) for k, v in (p.get("answers") or {}).items() if k in QUESTIONS and v in (0, 1, 2)}
    done = {d for d in (p.get("done") or []) if d in QUESTIONS}
    pillars, tot, mx = {}, 0, 0
    for name, qs in PILLARS.items():
        got = [ans[q] for q in qs if q in ans]
        pillars[name] = {"score": round(100 * sum(got) / (2 * len(got))) if got else 0, "answered": len(got), "total": len(qs)}
        tot += sum(got); mx += 2 * len(got)
    score = round(100 * tot / mx) if mx else 0
    answered = [q for q in QUESTIONS if q in ans]
    strengths = [q for q in answered if ans[q] == 2]
    # écarts : conformité sans réponse « oui » d'abord (risque juridique), puis impact décroissant, effort croissant, réponse la plus faible
    gaps = [q for q in answered if ans[q] < 2]
    gaps.sort(key=lambda q: (not (PILLAR_OF[q] == "compliance" and ans[q] == 0), -QUESTIONS[q][0], QUESTIONS[q][1], ans[q]))
    weak = [{"id": q, "level": ans[q], "impact": QUESTIONS[q][0], "effort": QUESTIONS[q][1], "pillar": PILLAR_OF[q], "done": q in done} for q in gaps]
    pending = [w for w in weak if not w["done"]]
    quick = [w["id"] for w in pending if w["effort"] <= 2 and w["impact"] >= 2]
    d30 = quick[:4]
    rest = [w["id"] for w in pending if w["id"] not in d30]
    d90 = [q for q in rest if QUESTIONS[q][1] <= 2][:5]
    m12 = [q for q in rest if q not in d90]
    n_gaps = len(weak)
    progress = round(100 * len([w for w in weak if w["done"]]) / n_gaps) if n_gaps else 0
    regs = regulations(p.get("country", ""), p.get("employees", 0), _num(p.get("turnover_m")))
    return {"score": score, "band": band(score), "pillars": {k: {**v, "band": band(v["score"]) if v["answered"] else "none"} for k, v in pillars.items()},
            "answered": len(answered), "total": len(QUESTIONS), "strengths": strengths, "weaknesses": weak,
            "roadmap": {"d30": d30, "d90": d90, "m12": m12}, "progress": progress, "regulations": regs}
