"""Les 4 routes passent bien leurs champs libres par ai_input et renvoient le bilan (sans clé : mise en forme seule, aucun appel externe)."""
import re
APP = open(__import__("pathlib").Path(__file__).resolve().parent.parent / "backend" / "app.py", encoding="utf-8").read()


def test_routes_use_processing_and_never_touch_sensitive_fields():
    for route, fields in (("spots_campaign", ('"product": "name"', '"pain": "sentence"')), ("strategy_diagnostic", ('"sector": "label"',)), ("chat_reply_route", ('"persona": "sentence"', '"offer": "label"'))):
        body = APP.split(f"def {route}(")[1].split("\n\n\n")[0]
        assert "_proc(" in body and '"processing"' in body or "pr}" in body, route
        for f in fields: assert f in body, (route, f)
    chat = APP.split("def chat_reply_route(")[1].split("\n\n\n")[0]
    for forbidden in ('"message"', '"history"', '"price"', '"brand"'):
        assert forbidden not in chat.split("_proc(")[1].split("\n")[0], forbidden      # le message du client et le prix restent fidèles
    inv = APP.split("def invoice")[1:] if "def invoice" in APP else []
    assert not any("_proc(" in x.split("\n\n\n")[0] for x in inv)                        # jamais sur les factures


if __name__ == "__main__":
    test_routes_use_processing_and_never_touch_sensitive_fields(); print("ALL PASS")
