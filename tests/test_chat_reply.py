import re, backend.chat_reply as C


def run(msg, **k):
    return C.reply({"message": msg, **k})


def test_intents_all_languages():
    cases = {"complaint": ["Je n'ai pas reçu ma commande, c'est un problème", "I never received my order, refund please", "Ich habe die Ware nicht erhalten, Erstattung bitte",
                           "No recibí mi pedido, quiero reembolso", "Non ricevuto, voglio il rimborso", "لم يصل الطلب وأريد استرجاع"],
             "objection": ["c'est trop cher", "too expensive, any discount?", "zu teuer, Rabatt?", "muy caro, descuento", "troppo caro, sconto", "غالي، هل من تخفيض"],
             "buy": ["Je veux commander", "I want to order", "ich möchte bestellen", "quiero comprar", "voglio ordinare", "أريد الطلب"],
             "comparison": ["Quelle différence avec X ?", "What's the difference with X?", "Was ist der Unterschied zu X?", "¿Qué diferencia hay?", "Qual è la differenza?", "ما الفرق"],
             "curiosity": ["Bonjour, vous êtes où ?", "Hello, where are you?"]}
    for want, msgs in cases.items():
        for m in msgs:
            assert C.analyse(m)["intent"] == want, (want, m, C.analyse(m))


def test_heat_and_temper():
    assert C.analyse("Je veux commander maintenant !")["heat"] == "burning"
    assert C.analyse("Je veux commander")["heat"] == "hot"
    assert C.analyse("C'est inadmissible !! Colis cassé")["temper"] == "annoyed"
    assert C.analyse("Est-ce fiable ? C'est une arnaque ?")["temper"] == "wary"
    assert C.analyse("Bonjour, quelle est la composition ?")["temper"] == "technical"
    assert C.analyse("Prix ?")["heat"] == "warm"


def test_never_invents_price_or_features():
    r = run("Quel est le prix ?")
    assert any("À COMPLÉTER : prix" in o for o in r["options"][:2]) and r["warnings"][0].startswith("missing:")
    assert not re.search(r"\d+\s?(DH|€|MAD|\$)", " ".join(r["options"]))


def test_filled_config_has_no_placeholders_and_uses_values():
    cfg = dict(brand="Nour", offer="crème bio 50 ml", price="149 DH", cross="le sérum", guarantee="Satisfait ou remboursé 14 jours", logistics="Livraison 24 h, paiement à la livraison", alt="le format 30 ml")
    r = run("Quel est le prix ?", **cfg)
    assert "149 DH" in r["options"][0] and "sérum" in r["options"][1] and "⚠️" not in " ".join(r["options"])
    r = run("C'est trop cher", **cfg)
    assert "remise" not in " ".join(r["options"]).lower() and "30 ml" in r["options"][2]


def test_closed_question_in_every_option_and_languages():
    for lang in C.LANGS:
        for m in ("Je veux commander", "trop cher", "problème de livraison", "bonjour", "différence ?"):
            for ch in C.CHANNELS:
                r = run(m, lang=lang, channel=ch)
                assert len(r["options"]) == 3 and r["advice"] and r["analysis"]["intent"]
                for o in r["options"]:
                    assert re.search(r"[?؟]", o), (lang, m, o)


def test_complaint_does_not_sell():
    r = run("Colis cassé, remboursement svp", offer="x", cross="y", limited=True)
    t = " ".join(r["options"])
    assert "y pour" not in t and "stock" not in t.lower()


def test_scarcity_only_when_declared():
    assert "stock" not in " ".join(run("bonjour", offer="a")["options"]).lower()
    assert "stock" in run("bonjour", offer="a", limited=True)["options"][1].lower()


def test_channel_and_errors():
    assert run("bonjour", brand="Nour", channel="messenger")["options"][0].endswith("— Nour")
    assert "— Nour" not in run("bonjour", brand="Nour", channel="whatsapp")["options"][0]
    for bad in ("", "  ", "x" * 2001):
        try: run(bad); raise AssertionError
        except ValueError: pass


def test_master_prompt_filled():
    mp = run("bonjour", brand="Nour", sector="Beauté")["master_prompt"]
    assert "Marque : Nour" in mp and "Secteur / industrie : Beauté" in mp and "À COMPLÉTER" in mp


def test_negations_do_not_trigger():
    assert C.analyse("Pas de problème, merci !")["intent"] == "curiosity"
    assert C.analyse("Ce n'est pas cher du tout, je prends")["intent"] == "buy"
    assert C.analyse("no problem, how much?")["intent"] == "curiosity"


def test_auto_language_and_followup():
    for msg, lang in [("Hello, how much is it please?", "en"), ("Ich möchte bitte bestellen, danke", "de"), ("Hola, quiero comprar, gracias", "es"),
                      ("Ciao, voglio ordinare, grazie", "it"), ("مرحبا كم السعر", "ar"), ("Bonjour, je voudrais un renseignement", "fr")]:
        assert run(msg, lang="auto")["lang"] == lang, msg
    assert run("ok", lang="auto", fallback="de")["lang"] == "de"
    assert "?" in run("bonjour")["followup"] and "oui ou non" in run("colis cassé")["followup"]


def test_fuzz_never_crashes():
    import random
    rnd = random.Random(7); pool = list("abcé !?؟😍\n\t'\"[]{}%$<>") + ["prix", "cher", "problème", "ASAP", "commander", "ص"]
    for _ in range(400):
        m = "".join(rnd.choice(pool) for _ in range(rnd.randint(1, 80))) or "x"
        if not m.strip(): continue
        for lang in ("auto", "fr", "ar"):
            r = C.reply({"message": m, "lang": lang, "channel": rnd.choice(C.CHANNELS), "offer": "{offer} %s {x}", "limited": bool(rnd.getrandbits(1))})
            assert len(r["options"]) == 3 and all(o.strip() for o in r["options"])


def test_conversation_memory():
    r = run("oui ok", history=["Je veux commander la crème", "Parfait, je vous envoie le détail ?"])
    assert r["analysis"]["intent_key"] == "buy" and r["conversation"]["turns"] == 3
    r = run("c'est encore trop cher", history=["trop cher", "Je comprends, voici la valeur"])
    assert r["conversation"]["objections"] == 2 and "repeat_objection" in r["warnings"] and "Deuxième objection" in r["advice"]
    r = run("c'est cher quand même", history=["Je veux commander", "Quel prix ?"])
    assert "rassurez" in r["advice"]
    r = run("Merci, et pour la crème ?", history=["Colis cassé, remboursement !"], offer="a", cross="b", limited=True)
    assert "b pour" not in " ".join(r["options"]) and "stock" not in " ".join(r["options"]).lower()
    assert run("Je veux commander", history=["Quel prix ?"])["conversation"]["trend"] == "up"
    assert run("bonjour")["conversation"]["turns"] == 1 and run("bonjour")["conversation"]["trend"] == "none"
    assert run("x y", history=["a"] * 50 + [""])["conversation"]["turns"] == 11


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"): f(); print("ok", n)
    print("ALL PASS")
