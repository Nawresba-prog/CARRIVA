"""Vérifie les liens du catalogue de formations : à lancer depuis la racine du projet, sur une machine avec accès Internet.

    python -m backend.check_links                 # tableau complet
    python -m backend.check_links --only-bad      # seulement ce qui demande une action
    python -m backend.check_links --json rapport.json --workers 6

Statuts : ok · redirige (le lien marche mais l'adresse a changé : mettre à jour le catalogue) · bloqué (le site refuse les robots :
à ouvrir à la main) · page_vide (200 mais la page dit « introuvable ») · mort (404/410) · erreur (autre code) · injoignable (réseau).
Code de sortie 1 s'il reste des liens « mort », « erreur », « page_vide » ou « injoignable ». Aucune dépendance (bibliothèque standard).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from urllib.parse import urlsplit

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 CARRIVA-linkcheck/1.0"
SOFT_404 = re.compile(r"\b(404|not found|page not found|introuvable|n'existe pas|nicht gefunden|no encontrad|non trovat|page unavailable)\b", re.I)
BAD = {"mort", "erreur", "page_vide", "injoignable"}


def _norm(u: str) -> str:
    p = urlsplit(u)
    host = p.netloc.lower().removeprefix("www.")
    return f"{host}{p.path.rstrip('/')}"


def _title(body: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
    return re.sub(r"\s+", " ", unescape(m.group(1))).strip()[:120] if m else ""


def fetch(url: str, timeout: float = 15.0) -> tuple[int, str, str]:
    """-> (code HTTP, URL finale après redirections, début du corps). Lève OSError si le réseau échoue."""
    req = urllib.request.Request(url.split("#")[0], headers={"User-Agent": UA, "Accept": "text/html,*/*;q=0.8", "Accept-Language": "fr,en;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.geturl(), r.read(60_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.geturl() or url, ""


def classify(url: str, code: int, final: str, body: str) -> dict:
    title = _title(body)
    out = {"url": url, "code": code, "final_url": final if _norm(final) != _norm(url) else None, "title": title}
    if code in (401, 403, 429, 451, 999):
        out["status"] = "bloqué"
    elif code in (404, 410):
        out["status"] = "mort"
    elif code >= 400:
        out["status"] = "erreur"
    elif title and SOFT_404.search(title):
        out["status"] = "page_vide"
    elif out["final_url"]:
        out["status"] = "redirige"
    else:
        out["status"] = "ok"
    return out


def check(url: str, fetcher=fetch, retries: int = 1, pause: float = 1.0) -> dict:
    last = ""
    for i in range(retries + 1):
        try:
            return classify(url, *fetcher(url))
        except (OSError, ValueError) as e:  # URLError, timeout, SSL, DNS
            last = str(e)[:100]
            if i < retries:
                time.sleep(pause)
    return {"url": url, "code": 0, "final_url": None, "title": "", "status": "injoignable", "error": last}


def catalog_urls() -> list[tuple[str, str]]:
    from . import catalog
    seen, out = set(), []
    for c in catalog.all_courses():
        if c["url"] not in seen:
            seen.add(c["url"])
            out.append((c["url"], c["title"]))
    return out


def run(items: list[tuple[str, str]], workers: int = 6, fetcher=fetch) -> list[dict]:
    titles = dict(items)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        res = list(ex.map(lambda it: check(it[0], fetcher), items))
    for r in res:
        r["course"] = titles[r["url"]]
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only-bad", action="store_true", help="n'afficher que les liens à traiter")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--json", metavar="FICHIER", help="écrire le rapport complet en JSON")
    a = ap.parse_args(argv)
    res = run(catalog_urls(), a.workers)
    counts: dict[str, int] = {}
    for r in res:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        if a.only_bad and r["status"] == "ok":
            continue
        extra = f"  →  {r['final_url']}" if r.get("final_url") else (f"  [{r.get('error', '')}]" if r.get("error") else "")
        print(f"{r['status']:<11} {r['code'] or '-':<4} {r['course'][:44]:<44} {r['url']}{extra}")
    print("\n" + " · ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
    return 1 if any(r["status"] in BAD for r in res) else 0


if __name__ == "__main__":
    sys.exit(main())
