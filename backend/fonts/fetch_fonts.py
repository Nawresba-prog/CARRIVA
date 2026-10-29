"""Télécharge Noto Sans Arabic (licence SIL OFL 1.1, redistribution autorisée) dans backend/fonts/.

Usage : python backend/fonts/fetch_fonts.py
Les polices ne sont pas versionnées dans le dépôt ; lancez ce script au build (Dockerfile / CI) ou copiez
vous-même les fichiers NotoSansArabic-Regular.ttf et NotoSansArabic-Bold.ttf dans ce dossier.
"""
import sys
import urllib.request
from pathlib import Path

DEST = Path(__file__).resolve().parent
FILES = ["NotoSansArabic-Regular.ttf", "NotoSansArabic-Bold.ttf"]
MIRRORS = [
    "https://github.com/notofonts/notofonts.github.io/raw/main/fonts/NotoSansArabic/hinted/ttf/{f}",
    "https://cdn.jsdelivr.net/gh/notofonts/notofonts.github.io/fonts/NotoSansArabic/hinted/ttf/{f}",
]


def fetch(name: str, family: str = "NotoSansArabic") -> bool:
    target = DEST / name
    if target.exists() and target.stat().st_size > 10_000:
        print(f"= {name} déjà présent")
        return True
    for tpl in MIRRORS:
        url = tpl.format(f=name).replace("NotoSansArabic/", family + "/")
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                data = r.read()
            if data[:4] not in (b"\x00\x01\x00\x00", b"true", b"OTTO"):
                raise ValueError("pas une police TrueType")
            target.write_bytes(data)
            print(f"+ {name} <- {url}")
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"! {url}: {exc}", file=sys.stderr)
    return False


if __name__ == "__main__":
    ok = all([fetch(f) for f in FILES])
    for f in ("NotoSans-Regular.ttf", "NotoSans-Bold.ttf"):  # police latine incorporée dans les Factur-X (PDF/A) ; à défaut DejaVu Sans est cherché sur le système
        fetch(f, "NotoSans")
    sys.exit(0 if ok else 1)
